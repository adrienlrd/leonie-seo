"""Abstract LLM provider interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class CompletionResult:
    text: str
    provider: str
    model: str
    tokens_in: int = 0
    tokens_out: int = 0


class LLMProvider(ABC):
    """Base class for all LLM providers."""

    name: str
    model: str

    @abstractmethod
    def complete(
        self,
        prompt: str,
        *,
        system: str = "",
        max_tokens: int = 512,
        temperature: float = 0.3,
        json_mode: bool = False,
    ) -> CompletionResult:
        """Send a completion request and return the result.

        Args:
            prompt: User prompt.
            system: System instruction (optional).
            max_tokens: Maximum tokens in the response.
            temperature: Sampling temperature (0 = deterministic).
            json_mode: When True, ask the provider to constrain output to valid
                JSON (response_format json_object). Providers that do not support
                it ignore the flag.

        Returns:
            CompletionResult with the generated text, provider name, and model.

        Raises:
            LLMError: On any non-retryable failure.
            LLMRateLimitError: On 429 / quota exceeded.
            LLMUnavailableError: On 5xx / timeout.
        """


class LLMError(Exception):
    """Non-retryable LLM error."""


class LLMRateLimitError(LLMError):
    """Provider rate limit exceeded — retryable by switching provider."""


class LLMUnavailableError(LLMError):
    """Provider temporarily unavailable (5xx / timeout) — retryable."""
