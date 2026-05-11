"""LLM module — provider abstraction + router.

Usage:
    from app.llm import get_router
    router = get_router()
    result = router.complete("Write a meta title for...", system="You are an SEO expert.")
"""

from __future__ import annotations

import os
from functools import lru_cache

from app.llm.provider import CompletionResult, LLMError, LLMProvider
from app.llm.router import LLMRouter

__all__ = ["CompletionResult", "LLMError", "LLMProvider", "LLMRouter", "get_router"]


@lru_cache(maxsize=1)
def get_router() -> LLMRouter:
    """Build the LLMRouter from environment variables.

    Provider order:
      1. OpenAI GPT-4o mini  (if OPENAI_API_KEY set)
      2. Groq Llama 3 70B    (if GROQ_API_KEY set)
      3. Cloudflare Workers  (if CF_ACCOUNT_ID + CF_API_TOKEN set)

    Raises:
        LLMError: If no provider can be configured.
    """
    from app.llm.providers.cloudflare import CloudflareProvider
    from app.llm.providers.groq import GroqProvider
    from app.llm.providers.openai import OpenAIProvider

    providers: list[LLMProvider] = []

    if key := os.getenv("OPENAI_API_KEY"):
        providers.append(OpenAIProvider(api_key=key))

    if key := os.getenv("GROQ_API_KEY"):
        providers.append(GroqProvider(api_key=key))

    account_id = os.getenv("CF_ACCOUNT_ID")
    api_token = os.getenv("CF_API_TOKEN")
    if account_id and api_token:
        providers.append(CloudflareProvider(account_id=account_id, api_token=api_token))

    if not providers:
        raise LLMError(
            "No LLM provider configured. Set at least one of: "
            "OPENAI_API_KEY, GROQ_API_KEY, or CF_ACCOUNT_ID+CF_API_TOKEN"
        )

    return LLMRouter(providers)


def reset_router() -> None:
    """Clear the cached router (useful in tests)."""
    get_router.cache_clear()
