"""Tests for LLMRouter fallback logic and provider abstraction."""

from __future__ import annotations

import pytest

from app.llm.provider import (
    CompletionResult,
    LLMError,
    LLMProvider,
    LLMRateLimitError,
    LLMUnavailableError,
)
from app.llm.router import LLMRouter


def _ok_provider(name: str, text: str = "ok") -> LLMProvider:
    class _Provider(LLMProvider):
        def complete(self, prompt, *, system="", max_tokens=512, temperature=0.3, json_mode=False):  # noqa: ARG002
            return CompletionResult(text=text, provider=self.name, model=self.model)

    p = _Provider()
    p.name = name
    p.model = "test-model"
    return p


def _failing_provider(name: str, exc: Exception) -> LLMProvider:
    class _Provider(LLMProvider):
        def complete(self, prompt, *, system="", max_tokens=512, temperature=0.3, json_mode=False):  # noqa: ARG002
            raise exc

    p = _Provider()
    p.name = name
    p.model = "test-model"
    return p


def test_router_returns_result_from_primary_provider():
    router = LLMRouter([_ok_provider("openai", "hello")])
    result = router.complete("prompt")
    assert result.text == "hello"
    assert result.provider == "openai"


def test_router_falls_back_when_primary_rate_limited():
    primary = _failing_provider("openai", LLMRateLimitError("429"))
    fallback = _ok_provider("groq", "fallback text")
    router = LLMRouter([primary, fallback])
    result = router.complete("prompt")
    assert result.text == "fallback text"
    assert result.provider == "groq"


def test_router_falls_back_when_primary_unavailable():
    primary = _failing_provider("openai", LLMUnavailableError("503"))
    fallback = _ok_provider("cloudflare", "cf result")
    router = LLMRouter([primary, fallback])
    result = router.complete("prompt")
    assert result.provider == "cloudflare"


def test_router_raises_when_all_providers_fail():
    providers = [
        _failing_provider("openai", LLMRateLimitError("429")),
        _failing_provider("groq", LLMUnavailableError("timeout")),
    ]
    router = LLMRouter(providers)
    with pytest.raises(LLMError, match="All LLM providers failed"):
        router.complete("prompt")


def test_router_does_not_swallow_non_retryable_errors():
    """A hard LLMError from the primary must propagate immediately."""
    primary = _failing_provider("openai", LLMError("invalid api key"))
    fallback = _ok_provider("groq", "should not reach")
    router = LLMRouter([primary, fallback])
    with pytest.raises(LLMError, match="invalid api key"):
        router.complete("prompt")


def test_router_requires_at_least_one_provider():
    with pytest.raises(LLMError):
        LLMRouter([])


def test_router_tries_second_fallback_when_first_also_fails():
    providers = [
        _failing_provider("openai", LLMRateLimitError("429")),
        _failing_provider("groq", LLMUnavailableError("timeout")),
        _ok_provider("cloudflare", "third wins"),
    ]
    router = LLMRouter(providers)
    result = router.complete("prompt")
    assert result.provider == "cloudflare"
    assert result.text == "third wins"


# ── get_router shop attribution (added 2026-05-12) ────────────────────────────


def test_get_router_per_shop_returns_distinct_instances(monkeypatch):
    """get_router(shop=A) and get_router(shop=B) must return separate routers
    so each call's metrics are attributed to its own tenant.

    Regression test for the lru_cache(maxsize=1) bug that returned a single
    shared router with shop=None for all callers.
    """
    from app.llm import get_router, reset_router

    reset_router()
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("CF_ACCOUNT_ID", raising=False)
    monkeypatch.delenv("CF_API_TOKEN", raising=False)

    r_a = get_router(shop="shop-a.myshopify.com")
    r_b = get_router(shop="shop-b.myshopify.com")
    r_none = get_router()

    assert r_a is not r_b
    assert r_a._shop == "shop-a.myshopify.com"
    assert r_b._shop == "shop-b.myshopify.com"
    assert r_none._shop is None
    # But the underlying provider list is shared (no rebuild cost per call)
    assert r_a.providers is r_b.providers
    reset_router()
