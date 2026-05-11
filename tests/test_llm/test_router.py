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
        def complete(self, prompt, *, system="", max_tokens=512, temperature=0.3):
            return CompletionResult(text=text, provider=self.name, model=self.model)

    p = _Provider()
    p.name = name
    p.model = "test-model"
    return p


def _failing_provider(name: str, exc: Exception) -> LLMProvider:
    class _Provider(LLMProvider):
        def complete(self, prompt, *, system="", max_tokens=512, temperature=0.3):
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
