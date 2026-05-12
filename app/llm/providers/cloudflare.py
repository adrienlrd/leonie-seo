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

# Llama tokenizer ≈ 4 chars/token on European languages — used as a coarse
# fallback when the Cloudflare response doesn't include a usage block.
_CHARS_PER_TOKEN = 4


def _estimate_tokens(text: str) -> int:
    """Estimate Llama token count from a string length — ceiling division by 4."""
    if not text:
        return 0
    return (len(text) + _CHARS_PER_TOKEN - 1) // _CHARS_PER_TOKEN


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
        # Cloudflare wraps everything in {"success": bool, "result": {...},
        # "errors": [...]}. Trust HTTP 200 OK but still check the body flag.
        if data.get("success") is False:
            raise LLMError(f"Cloudflare returned success=false: {data.get('errors', data)}")

        result_block = data.get("result", {}) or {}
        text = result_block.get("response", "")
        if not text:
            raise LLMError(f"Cloudflare returned empty response: {data}")

        # Token accounting — Cloudflare started returning a `usage` block in
        # 2024-Q4; older accounts still don't. Use it when present, otherwise
        # estimate from char count so the cost tracker has a non-zero number
        # for budget alerts.
        usage = result_block.get("usage") or {}
        tokens_in = int(usage.get("prompt_tokens") or 0)
        tokens_out = int(usage.get("completion_tokens") or 0)
        if tokens_in == 0:
            tokens_in = _estimate_tokens(system) + _estimate_tokens(prompt)
        if tokens_out == 0:
            tokens_out = _estimate_tokens(text)

        return CompletionResult(
            text=text.strip(),
            provider=self.name,
            model=self.model,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
        )
