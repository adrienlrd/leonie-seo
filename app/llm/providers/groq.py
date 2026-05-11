"""Groq provider — Llama 3 70B (free fallback)."""

from __future__ import annotations

from app.llm.provider import (
    CompletionResult,
    LLMError,
    LLMProvider,
    LLMRateLimitError,
    LLMUnavailableError,
)

_DEFAULT_MODEL = "llama3-70b-8192"


class GroqProvider(LLMProvider):
    """Llama 3 70B via the Groq API (free tier, high throughput)."""

    name = "groq"

    def __init__(self, api_key: str, model: str = _DEFAULT_MODEL, timeout: float = 30.0) -> None:
        try:
            import groq as _groq
        except ImportError as exc:
            raise LLMError("groq package not installed — run: pip install groq") from exc

        self.model = model
        self._client = _groq.Groq(api_key=api_key, timeout=timeout)

    def complete(
        self,
        prompt: str,
        *,
        system: str = "",
        max_tokens: int = 512,
        temperature: float = 0.3,
    ) -> CompletionResult:
        try:
            import groq as _groq

            messages: list[dict] = []
            if system:
                messages.append({"role": "system", "content": system})
            messages.append({"role": "user", "content": prompt})

            response = self._client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
            )
            text = response.choices[0].message.content or ""
            return CompletionResult(text=text.strip(), provider=self.name, model=self.model)

        except _groq.RateLimitError as exc:
            raise LLMRateLimitError(f"Groq rate limit: {exc}") from exc
        except (_groq.APIStatusError, _groq.APITimeoutError, _groq.APIConnectionError) as exc:
            raise LLMUnavailableError(f"Groq unavailable: {exc}") from exc
        except _groq.GroqError as exc:
            raise LLMError(f"Groq error: {exc}") from exc
