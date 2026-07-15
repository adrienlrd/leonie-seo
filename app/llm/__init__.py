"""LLM module — provider abstraction + router.

Usage:
    from app.llm import get_router
    router = get_router(shop="store.myshopify.com")  # for metrics attribution
    result = router.complete("Write a meta title for...", system="You are an SEO expert.")
"""

from __future__ import annotations

import os

from app.llm.provider import CompletionResult, LLMError, LLMProvider
from app.llm.router import LLMRouter

__all__ = ["CompletionResult", "LLMError", "LLMProvider", "LLMRouter", "get_router", "reset_router"]


# Module-level cache for provider lists, keyed by tier. Each list is expensive
# to build (env reads, API client initialisation), so it is constructed once
# per tier and reused across every per-shop router instance. A fresh LLMRouter
# is built per call so each call carries its own `shop` for metrics attribution
# — preventing the cross-tenant leak that an `@lru_cache` on `get_router` itself
# would create.
_PROVIDERS_CACHE: dict[str, list[LLMProvider]] = {}


def _build_providers() -> list[LLMProvider]:
    """Build the provider list from environment variables.

    Provider order:
      1. OpenAI GPT-4o mini  (if OPENAI_API_KEY set)
      2. Groq Llama 3 70B    (if GROQ_API_KEY set)
      3. Cloudflare Workers  (if CF_ACCOUNT_ID + CF_API_TOKEN set)
    """
    from app.llm.providers.cloudflare import CloudflareProvider  # noqa: PLC0415
    from app.llm.providers.groq import GroqProvider  # noqa: PLC0415
    from app.llm.providers.openai import OpenAIProvider  # noqa: PLC0415

    providers: list[LLMProvider] = []

    if key := os.getenv("OPENAI_API_KEY"):
        # 90s — gpt-4o-mini generates ~70 tok/s; 4096 output tokens can take 60s+
        providers.append(OpenAIProvider(api_key=key, timeout=90.0))

    if key := os.getenv("GROQ_API_KEY"):
        providers.append(GroqProvider(api_key=key, timeout=90.0))

    account_id = os.getenv("CF_ACCOUNT_ID")
    api_token = os.getenv("CF_API_TOKEN")
    if account_id and api_token:
        providers.append(CloudflareProvider(account_id=account_id, api_token=api_token))

    if not providers:
        raise LLMError(
            "No LLM provider configured. Set at least one of: "
            "OPENAI_API_KEY, GROQ_API_KEY, or CF_ACCOUNT_ID+CF_API_TOKEN"
        )
    return providers


def _build_grounded_providers() -> list[LLMProvider]:
    """Build the "grounded" provider list: Gemini (Google Search grounding)
    first, falling back to the default chain (gpt-4o-mini, etc.) so a
    grounded call degrades gracefully if Gemini is unavailable or unconfigured.
    """
    from app.llm.providers.gemini import GeminiProvider  # noqa: PLC0415

    providers: list[LLMProvider] = []
    if key := os.getenv("GEMINI_API_KEY"):
        model = os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite")
        providers.append(GeminiProvider(api_key=key, model=model, grounded=True, timeout=60.0))
    providers.extend(_build_providers())
    return providers


def get_router(*, shop: str | None = None, tier: str = "default") -> LLMRouter:
    """Return an LLMRouter scoped to `shop` for metrics attribution.

    The provider list is cached at module level per `tier` (built once); only
    the thin LLMRouter wrapper is constructed per call. Passing `shop` ensures
    every LLM call this router makes is attributed to that tenant in
    `llm_metrics`. Always pass `shop` in production code — `shop=None` is only
    acceptable in tests or shopless admin tasks.

    Args:
        shop: Shopify shop domain (default None for shopless calls).
        tier: "default" (gpt-4o-mini first) or "grounded" (Gemini + Google
            Search grounding first, falling back to the default chain — e.g.
            when GEMINI_API_KEY is unset, "grounded" behaves exactly like
            "default"). Callers must gate "grounded" to the intended plan
            themselves; this function does not check billing.

    Raises:
        LLMError: If no provider can be configured.
    """
    global _PROVIDERS_CACHE
    if tier not in _PROVIDERS_CACHE:
        builder = _build_grounded_providers if tier == "grounded" else _build_providers
        _PROVIDERS_CACHE[tier] = builder()
    return LLMRouter(_PROVIDERS_CACHE[tier], shop=shop)


def reset_router() -> None:
    """Clear the cached provider lists (useful in tests)."""
    global _PROVIDERS_CACHE
    _PROVIDERS_CACHE = {}
