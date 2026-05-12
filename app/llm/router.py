"""LLM router — tries providers in order, falls back on retryable errors."""

from __future__ import annotations

import logging
import time

from app.llm.provider import (
    CompletionResult,
    LLMError,
    LLMProvider,
    LLMRateLimitError,
    LLMUnavailableError,
)

logger = logging.getLogger(__name__)

_RETRYABLE = (LLMRateLimitError, LLMUnavailableError)


def _record(
    result: CompletionResult,
    latency_ms: float,
    shop: str | None,
    error: str | None = None,
) -> None:
    """Best-effort metrics recording — never raises."""
    try:
        from app.observability.metrics import record_llm_call  # noqa: PLC0415

        record_llm_call(
            shop,
            result.provider,
            result.model,
            result.tokens_in,
            result.tokens_out,
            latency_ms,
            error=error,
        )
    except (OSError, RuntimeError, TypeError, ValueError) as exc:  # pragma: no cover
        logger.debug("Metrics recording failed (non-fatal): %s", exc)


class LLMRouter:
    """Tries providers in order; falls back to the next on retryable errors.

    Args:
        providers: Ordered list — first is primary, rest are fallbacks.
        shop: Optional shop domain for usage metrics attribution.
    """

    def __init__(self, providers: list[LLMProvider], *, shop: str | None = None) -> None:
        if not providers:
            raise LLMError("LLMRouter requires at least one provider")
        self._providers = providers
        self._shop = shop

    @property
    def providers(self) -> list[LLMProvider]:
        """Return the ordered provider list used by this router."""
        return self._providers

    @providers.setter
    def providers(self, value: list[LLMProvider]) -> None:
        """Replace providers for tests or explicit runtime reconfiguration."""
        if not value:
            raise LLMError("LLMRouter requires at least one provider")
        self._providers = value

    def complete(
        self,
        prompt: str,
        *,
        system: str = "",
        max_tokens: int = 512,
        temperature: float = 0.3,
    ) -> CompletionResult:
        """Call providers in order; raise LLMError if all fail.

        Records usage metrics (tokens, cost, latency) after each call.

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
            t0 = time.monotonic()
            try:
                result = provider.complete(
                    prompt, system=system, max_tokens=max_tokens, temperature=temperature
                )
                latency_ms = (time.monotonic() - t0) * 1000
                if provider is not self._providers[0]:
                    logger.info("LLM fallback succeeded via %s", provider.name)
                _record(result, latency_ms, self._shop)
                return result
            except _RETRYABLE as exc:
                latency_ms = (time.monotonic() - t0) * 1000
                logger.warning("LLM provider %s failed (%s), trying next", provider.name, exc)
                _record(
                    CompletionResult(text="", provider=provider.name, model=provider.model),
                    latency_ms,
                    self._shop,
                    error=str(exc),
                )
                last_exc = exc
            except LLMError:
                raise

        raise LLMError(f"All LLM providers failed. Last error: {last_exc}") from last_exc
