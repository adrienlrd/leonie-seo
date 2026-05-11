"""Cloudflare Workers AI provider — free fallback via httpx."""

from __future__ import annotations

import httpx

from app.llm.provider import (
    CompletionResult,
    LLMError,
    LLMProvider,
    LLMRateLimitError,
    LLMUnavailableError,
)

_DEFAULT_MODEL = "@cf/meta/llama-3-8b-instruct"
_BASE_URL = "https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run/{model}"


class CloudflareProvider(LLMProvider):
    """Llama 3 8B via Cloudflare Workers AI (free tier)."""

    name = "cloudflare"

    def __init__(
        self,
        account_id: str,
        api_token: str,
        model: str = _DEFAULT_MODEL,
        timeout: float = 30.0,
    ) -> None:
        self.model = model
        self._account_id = account_id
        self._api_token = api_token
        self._timeout = timeout

    def complete(
        self,
        prompt: str,
        *,
        system: str = "",
        max_tokens: int = 512,
        temperature: float = 0.3,
    ) -> CompletionResult:
        url = _BASE_URL.format(account_id=self._account_id, model=self.model)
        messages: list[dict] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        try:
            response = httpx.post(
                url,
                headers={"Authorization": f"Bearer {self._api_token}"},
                json={"messages": messages, "max_tokens": max_tokens, "temperature": temperature},
                timeout=self._timeout,
            )
        except httpx.TimeoutException as exc:
            raise LLMUnavailableError(f"Cloudflare timeout: {exc}") from exc
        except httpx.RequestError as exc:
            raise LLMUnavailableError(f"Cloudflare connection error: {exc}") from exc

        if response.status_code == 429:
            raise LLMRateLimitError(f"Cloudflare rate limit: {response.text}")
        if response.status_code >= 500:
            raise LLMUnavailableError(
                f"Cloudflare server error {response.status_code}: {response.text}"
            )
        if not response.is_success:
            raise LLMError(f"Cloudflare error {response.status_code}: {response.text}")

        data = response.json()
        text = data.get("result", {}).get("response", "")
        if not text:
            raise LLMError(f"Cloudflare returned empty response: {data}")
        return CompletionResult(text=text.strip(), provider=self.name, model=self.model)
