"""Gemini provider — httpx REST, with optional Google Search grounding."""

from __future__ import annotations

import httpx

from app.llm.provider import (
    CompletionResult,
    LLMError,
    LLMProvider,
    LLMRateLimitError,
    LLMUnavailableError,
)

_DEFAULT_MODEL = "gemini-3.1-flash-lite"
_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


class GeminiProvider(LLMProvider):
    """Gemini via the REST API. When ``grounded=True``, enables Google Search
    grounding (the response then carries citations for its factual claims)."""

    name = "gemini"

    def __init__(
        self,
        api_key: str,
        model: str = _DEFAULT_MODEL,
        *,
        grounded: bool = False,
        timeout: float = 30.0,
    ) -> None:
        self.model = model
        self._api_key = api_key
        self._grounded = grounded
        self._timeout = timeout

    def complete(
        self,
        prompt: str,
        *,
        system: str = "",
        max_tokens: int = 512,
        temperature: float = 0.3,
        json_mode: bool = False,
    ) -> CompletionResult:
        url = _BASE_URL.format(model=self.model)
        payload: dict = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"maxOutputTokens": max_tokens, "temperature": temperature},
        }
        if system:
            payload["systemInstruction"] = {"parts": [{"text": system}]}
        if json_mode:
            payload["generationConfig"]["responseMimeType"] = "application/json"
        if self._grounded:
            payload["tools"] = [{"google_search": {}}]

        try:
            response = httpx.post(
                url,
                params={"key": self._api_key},
                json=payload,
                timeout=self._timeout,
            )
        except httpx.TimeoutException as exc:
            raise LLMUnavailableError(f"Gemini timeout: {exc}") from exc
        except httpx.RequestError as exc:
            raise LLMUnavailableError(f"Gemini connection error: {exc}") from exc

        if response.status_code == 429:
            raise LLMRateLimitError(f"Gemini rate limit: {response.text}")
        if response.status_code >= 500:
            raise LLMUnavailableError(f"Gemini server error {response.status_code}: {response.text}")
        if response.status_code == 400 and self._grounded and json_mode:
            # Known API quirk: grounding + forced JSON output can be rejected
            # together on some model versions. Treat as retryable so the
            # router falls back to gpt-4o-mini instead of hard-failing the
            # whole call — a grounded call must never break the feature.
            raise LLMUnavailableError(
                f"Gemini rejected grounded+json_mode combination: {response.text}"
            )
        if not response.is_success:
            raise LLMError(f"Gemini error {response.status_code}: {response.text}")

        data = response.json()
        candidates = data.get("candidates") or []
        if not candidates:
            raise LLMError(f"Gemini returned no candidates: {data}")
        candidate = candidates[0]
        parts = ((candidate.get("content") or {}).get("parts")) or []
        text = "".join(str(p.get("text", "")) for p in parts if isinstance(p, dict))
        if not text:
            raise LLMError(f"Gemini returned empty text: {data}")

        usage = data.get("usageMetadata") or {}
        tokens_in = int(usage.get("promptTokenCount") or 0)
        tokens_out = int(usage.get("candidatesTokenCount") or 0)

        citations, search_queries = _extract_grounding(candidate)

        return CompletionResult(
            text=text.strip(),
            provider=self.name,
            model=self.model,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            citations=citations,
            search_queries=search_queries,
        )


def _extract_grounding(candidate: dict) -> tuple[list[dict], list[str]]:
    """Pull source URLs and executed search queries from groundingMetadata.

    Defensive against schema drift: any missing/malformed field is skipped
    rather than raising, since grounding metadata is supplementary — losing it
    must never fail the completion itself.
    """
    meta = candidate.get("groundingMetadata") or {}
    citations: list[dict] = []
    for chunk in meta.get("groundingChunks") or []:
        web = (chunk or {}).get("web") or {}
        url = web.get("uri")
        if url:
            citations.append({"url": url, "title": web.get("title", "")})
    search_queries = [q for q in (meta.get("webSearchQueries") or []) if isinstance(q, str)]
    return citations, search_queries
