"""LLM router — tries providers in order, falls back on retryable errors."""

from __future__ import annotations

import logging

from app.llm.provider import (
    CompletionResult,
    LLMError,
    LLMProvider,
    LLMRateLimitError,
    LLMUnavailableError,
)

logger = logging.getLogger(__name__)

_RETRYABLE = (LLMRateLimitError, LLMUnavailableError)


class LLMRouter:
    """Tries providers in order; falls back to the next on retryable errors.

    Args:
        providers: Ordered list — first is primary, rest are fallbacks.
    """

    def __init__(self, providers: list[LLMProvider]) -> None:
        if not providers:
            raise LLMError("LLMRouter requires at least one provider")
        self._providers = providers

    def complete(
        self,
        prompt: str,
        *,
        system: str = "",
        max_tokens: int = 512,
        temperature: float = 0.3,
    ) -> CompletionResult:
        """Call providers in order; raise LLMError if all fail.

        Args:
            prompt: User prompt.
            system: System instruction (optional).
            max_tokens: Maximum tokens in the response.
            temperature: Sampling temperature.

        Returns:
            CompletionResult from the first provider that succeeds.

        Raises:
            LLMError: If all providers fail.
        """
        last_exc: Exception | None = None
        for provider in self._providers:
            try:
                result = provider.complete(
                    prompt, system=system, max_tokens=max_tokens, temperature=temperature
                )
                if provider is not self._providers[0]:
                    logger.info("LLM fallback succeeded via %s", provider.name)
                return result
            except _RETRYABLE as exc:
                logger.warning("LLM provider %s failed (%s), trying next", provider.name, exc)
                last_exc = exc
            except LLMError:
                raise

        raise LLMError(f"All LLM providers failed. Last error: {last_exc}") from last_exc
