"""OpenAI provider — GPT-4o mini (primary)."""

from __future__ import annotations

from app.llm.provider import (
    CompletionResult,
    LLMError,
    LLMProvider,
    LLMRateLimitError,
    LLMUnavailableError,
)

_DEFAULT_MODEL = "gpt-4o-mini"


class OpenAIProvider(LLMProvider):
    """GPT-4o mini via the official OpenAI SDK."""

    name = "openai"

    def __init__(self, api_key: str, model: str = _DEFAULT_MODEL, timeout: float = 30.0) -> None:
        try:
            import openai as _openai
        except ImportError as exc:
            raise LLMError("openai package not installed — run: pip install openai") from exc

        self.model = model
        self._client = _openai.OpenAI(api_key=api_key, timeout=timeout)

    def complete(
        self,
        prompt: str,
        *,
        system: str = "",
        max_tokens: int = 512,
        temperature: float = 0.3,
        json_mode: bool = False,
    ) -> CompletionResult:
        try:
            import openai as _openai

            messages: list[dict] = []
            if system:
                messages.append({"role": "system", "content": system})
            messages.append({"role": "user", "content": prompt})

            extra: dict = {}
            if json_mode:
                extra["response_format"] = {"type": "json_object"}

            response = self._client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
                **extra,
            )
            text = response.choices[0].message.content or ""
            usage = response.usage
            return CompletionResult(
                text=text.strip(),
                provider=self.name,
                model=self.model,
                tokens_in=usage.prompt_tokens if usage else 0,
                tokens_out=usage.completion_tokens if usage else 0,
            )

        except _openai.RateLimitError as exc:
            raise LLMRateLimitError(f"OpenAI rate limit: {exc}") from exc
        except (_openai.APIStatusError, _openai.APITimeoutError, _openai.APIConnectionError) as exc:
            raise LLMUnavailableError(f"OpenAI unavailable: {exc}") from exc
        except _openai.OpenAIError as exc:
            raise LLMError(f"OpenAI error: {exc}") from exc
