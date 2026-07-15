"""Tests for individual LLM providers (all mocked — no real API calls)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.llm.provider import LLMError, LLMRateLimitError, LLMUnavailableError

# ── OpenAI ────────────────────────────────────────────────────────────────────


class TestOpenAIProvider:
    def _make_provider(self):
        with patch("openai.OpenAI"):
            from app.llm.providers.openai import OpenAIProvider

            return OpenAIProvider(api_key="sk-test")

    def test_complete_returns_result_on_success(self):
        provider = self._make_provider()
        mock_response = MagicMock()
        mock_response.choices[0].message.content = "  Meta title generated  "
        provider._client.chat.completions.create.return_value = mock_response
        result = provider.complete("write a meta title")
        assert result.text == "Meta title generated"
        assert result.provider == "openai"

    def test_complete_raises_rate_limit_on_429(self):
        import openai

        provider = self._make_provider()
        provider._client.chat.completions.create.side_effect = openai.RateLimitError(
            "rate limit", response=MagicMock(status_code=429), body={}
        )
        with pytest.raises(LLMRateLimitError):
            provider.complete("prompt")

    def test_complete_raises_unavailable_on_timeout(self):
        import openai

        provider = self._make_provider()
        provider._client.chat.completions.create.side_effect = openai.APITimeoutError(
            request=MagicMock()
        )
        with pytest.raises(LLMUnavailableError):
            provider.complete("prompt")


# ── Groq ──────────────────────────────────────────────────────────────────────


class TestGroqProvider:
    def _make_provider(self):
        with patch("groq.Groq"):
            from app.llm.providers.groq import GroqProvider

            return GroqProvider(api_key="gsk-test")

    def test_complete_returns_result_on_success(self):
        provider = self._make_provider()
        mock_response = MagicMock()
        mock_response.choices[0].message.content = "Groq response"
        provider._client.chat.completions.create.return_value = mock_response
        result = provider.complete("prompt", system="You are SEO expert.")
        assert result.text == "Groq response"
        assert result.provider == "groq"

    def test_complete_raises_rate_limit(self):
        import groq

        provider = self._make_provider()
        provider._client.chat.completions.create.side_effect = groq.RateLimitError(
            "rate limit", response=MagicMock(status_code=429), body={}
        )
        with pytest.raises(LLMRateLimitError):
            provider.complete("prompt")


# ── Cloudflare ────────────────────────────────────────────────────────────────


class TestCloudflareProvider:
    def _make_provider(self):
        from app.llm.providers.cloudflare import CloudflareProvider

        return CloudflareProvider(account_id="acc123", api_token="tok456")

    def test_complete_returns_result_on_success(self):
        import httpx

        provider = self._make_provider()
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.is_success = True
        mock_response.json.return_value = {"result": {"response": "CF response"}}
        with patch("httpx.post", return_value=mock_response):
            result = provider.complete("prompt")
        assert result.text == "CF response"
        assert result.provider == "cloudflare"

    def test_complete_raises_rate_limit_on_429(self):
        import httpx

        provider = self._make_provider()
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 429
        mock_response.is_success = False
        mock_response.text = "Too Many Requests"
        with patch("httpx.post", return_value=mock_response):
            with pytest.raises(LLMRateLimitError):
                provider.complete("prompt")

    def test_complete_raises_unavailable_on_5xx(self):
        import httpx

        provider = self._make_provider()
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 503
        mock_response.is_success = False
        mock_response.text = "Service Unavailable"
        with patch("httpx.post", return_value=mock_response):
            with pytest.raises(LLMUnavailableError):
                provider.complete("prompt")

    def test_complete_raises_unavailable_on_timeout(self):
        import httpx

        provider = self._make_provider()
        with patch("httpx.post", side_effect=httpx.TimeoutException("timeout")):
            with pytest.raises(LLMUnavailableError):
                provider.complete("prompt")

    def test_complete_estimates_tokens_when_response_has_no_usage(self):
        """Cost tracker needs non-zero tokens — if Cloudflare omits the
        usage block, we estimate from char count (~4 chars/token)."""
        import httpx

        provider = self._make_provider()
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.is_success = True
        mock_response.json.return_value = {
            "success": True,
            "result": {"response": "OK" * 50},
        }
        with patch("httpx.post", return_value=mock_response):
            result = provider.complete("twelve chars", system="eight ch")
        # 'eight ch' = 8 chars, 'twelve chars' = 12 chars → 5 tokens estimated
        # "OK"*50 = 100 chars → 25 tokens estimated
        assert result.tokens_in > 0
        assert result.tokens_out > 0
        assert result.tokens_in == 5  # (8 + 12 + 3) / 4 ceil = 6 actually: 2 + 3 = 5
        assert result.tokens_out == 25

    def test_complete_uses_provided_usage_block_when_present(self):
        """If Cloudflare's response includes usage, use the real numbers
        rather than the char-based estimate."""
        import httpx

        provider = self._make_provider()
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.is_success = True
        mock_response.json.return_value = {
            "success": True,
            "result": {
                "response": "answer",
                "usage": {"prompt_tokens": 123, "completion_tokens": 45},
            },
        }
        with patch("httpx.post", return_value=mock_response):
            result = provider.complete("anything")
        assert result.tokens_in == 123
        assert result.tokens_out == 45

    def test_complete_rejects_success_false_body(self):
        """Cloudflare can return HTTP 200 with success=false in the body when
        the model is unavailable. That must surface as an error."""
        import httpx

        provider = self._make_provider()
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.is_success = True
        mock_response.json.return_value = {
            "success": False,
            "errors": [{"code": 7003, "message": "model unavailable"}],
        }
        with patch("httpx.post", return_value=mock_response):
            with pytest.raises(LLMError, match="success=false"):
                provider.complete("prompt")


# ── Gemini ────────────────────────────────────────────────────────────────────


class TestGeminiProvider:
    def _make_provider(self, *, grounded: bool = False):
        from app.llm.providers.gemini import GeminiProvider

        return GeminiProvider(api_key="AIza-test", grounded=grounded)

    def test_complete_returns_result_on_success(self):
        import httpx

        provider = self._make_provider()
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.is_success = True
        mock_response.json.return_value = {
            "candidates": [{"content": {"parts": [{"text": "  Gemini response  "}]}}],
            "usageMetadata": {"promptTokenCount": 12, "candidatesTokenCount": 5},
        }
        with patch("httpx.post", return_value=mock_response):
            result = provider.complete("prompt")
        assert result.text == "Gemini response"
        assert result.provider == "gemini"
        assert result.tokens_in == 12
        assert result.tokens_out == 5
        assert result.citations == []
        assert result.search_queries == []

    def test_grounded_request_includes_google_search_tool(self):
        import httpx

        provider = self._make_provider(grounded=True)
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.is_success = True
        mock_response.json.return_value = {
            "candidates": [{"content": {"parts": [{"text": "answer"}]}}],
        }
        with patch("httpx.post", return_value=mock_response) as mock_post:
            provider.complete("prompt")
        sent_payload = mock_post.call_args.kwargs["json"]
        assert sent_payload["tools"] == [{"google_search": {}}]

    def test_ungrounded_request_has_no_tools(self):
        import httpx

        provider = self._make_provider(grounded=False)
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.is_success = True
        mock_response.json.return_value = {
            "candidates": [{"content": {"parts": [{"text": "answer"}]}}],
        }
        with patch("httpx.post", return_value=mock_response) as mock_post:
            provider.complete("prompt")
        assert "tools" not in mock_post.call_args.kwargs["json"]

    def test_json_mode_sets_response_mime_type(self):
        import httpx

        provider = self._make_provider()
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.is_success = True
        mock_response.json.return_value = {
            "candidates": [{"content": {"parts": [{"text": "{}"}]}}],
        }
        with patch("httpx.post", return_value=mock_response) as mock_post:
            provider.complete("prompt", json_mode=True)
        config = mock_post.call_args.kwargs["json"]["generationConfig"]
        assert config["responseMimeType"] == "application/json"

    def test_grounding_metadata_populates_citations_and_queries(self):
        import httpx

        provider = self._make_provider(grounded=True)
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.is_success = True
        mock_response.json.return_value = {
            "candidates": [
                {
                    "content": {"parts": [{"text": "canicule cette semaine"}]},
                    "groundingMetadata": {
                        "webSearchQueries": ["canicule france juillet 2026"],
                        "groundingChunks": [
                            {"web": {"uri": "https://meteo-france.fr/canicule", "title": "Météo France"}}
                        ],
                    },
                }
            ],
        }
        with patch("httpx.post", return_value=mock_response):
            result = provider.complete("prompt")
        assert result.search_queries == ["canicule france juillet 2026"]
        assert result.citations == [
            {"url": "https://meteo-france.fr/canicule", "title": "Météo France"}
        ]

    def test_malformed_grounding_metadata_does_not_raise(self):
        """Grounding metadata is supplementary — a malformed chunk must never
        break the completion itself."""
        import httpx

        provider = self._make_provider(grounded=True)
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.is_success = True
        mock_response.json.return_value = {
            "candidates": [
                {
                    "content": {"parts": [{"text": "answer"}]},
                    "groundingMetadata": {"groundingChunks": [{"web": {}}, None, {}]},
                }
            ],
        }
        with patch("httpx.post", return_value=mock_response):
            result = provider.complete("prompt")
        assert result.text == "answer"
        assert result.citations == []

    def test_complete_raises_rate_limit_on_429(self):
        import httpx

        provider = self._make_provider()
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 429
        mock_response.is_success = False
        mock_response.text = "Too Many Requests"
        with patch("httpx.post", return_value=mock_response):
            with pytest.raises(LLMRateLimitError):
                provider.complete("prompt")

    def test_complete_raises_unavailable_on_5xx(self):
        import httpx

        provider = self._make_provider()
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 503
        mock_response.is_success = False
        mock_response.text = "Service Unavailable"
        with patch("httpx.post", return_value=mock_response):
            with pytest.raises(LLMUnavailableError):
                provider.complete("prompt")

    def test_complete_raises_unavailable_on_timeout(self):
        import httpx

        provider = self._make_provider()
        with patch("httpx.post", side_effect=httpx.TimeoutException("timeout")):
            with pytest.raises(LLMUnavailableError):
                provider.complete("prompt")

    def test_complete_raises_on_empty_candidates(self):
        import httpx

        provider = self._make_provider()
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.is_success = True
        mock_response.json.return_value = {"candidates": []}
        with patch("httpx.post", return_value=mock_response):
            with pytest.raises(LLMError, match="no candidates"):
                provider.complete("prompt")


# ── get_router ────────────────────────────────────────────────────────────────


class TestGetRouter:
    def test_get_router_raises_when_no_env_vars_set(self):
        from app.llm import reset_router

        reset_router()
        with patch.dict("os.environ", {}, clear=True):
            # Remove all provider keys
            import os

            for k in ["OPENAI_API_KEY", "GROQ_API_KEY", "CF_ACCOUNT_ID", "CF_API_TOKEN"]:
                os.environ.pop(k, None)
            from app.llm import get_router
            from app.llm.provider import LLMError

            with pytest.raises(LLMError, match="No LLM provider configured"):
                get_router()
        reset_router()

    def test_get_router_builds_openai_provider_when_key_set(self):
        from app.llm import reset_router

        reset_router()
        env = {"OPENAI_API_KEY": "sk-test"}
        with patch.dict("os.environ", env, clear=False), patch("openai.OpenAI"):
            from app.llm import get_router

            router = get_router()
        assert any(p.name == "openai" for p in router.providers)
        reset_router()

    def test_get_router_builds_groq_provider_when_key_set(self):
        from app.llm import reset_router

        reset_router()
        env = {"GROQ_API_KEY": "gsk-test"}
        # Remove OpenAI key so only Groq is configured
        import os

        os.environ.pop("OPENAI_API_KEY", None)
        with patch.dict("os.environ", env, clear=False), patch("groq.Groq"):
            from app.llm import get_router

            router = get_router()
        assert any(p.name == "groq" for p in router.providers)
        reset_router()

    def test_grounded_tier_puts_gemini_first_when_key_set(self):
        from app.llm import reset_router

        reset_router()
        env = {"OPENAI_API_KEY": "sk-test", "GEMINI_API_KEY": "AIza-test"}
        with patch.dict("os.environ", env, clear=False), patch("openai.OpenAI"):
            from app.llm import get_router

            router = get_router(tier="grounded")
        assert [p.name for p in router.providers[:2]] == ["gemini", "openai"]
        reset_router()

    def test_grounded_tier_falls_back_to_default_chain_without_gemini_key(self):
        """No GEMINI_API_KEY → tier='grounded' behaves exactly like 'default',
        never raises, never silently drops to zero providers."""
        from app.llm import reset_router

        reset_router()
        import os

        for k in ["GEMINI_API_KEY", "GROQ_API_KEY", "CF_ACCOUNT_ID", "CF_API_TOKEN"]:
            os.environ.pop(k, None)
        env = {"OPENAI_API_KEY": "sk-test"}
        with patch.dict("os.environ", env, clear=False), patch("openai.OpenAI"):
            from app.llm import get_router

            router = get_router(tier="grounded")
        assert [p.name for p in router.providers] == ["openai"]
        reset_router()

    def test_default_and_grounded_tiers_are_cached_separately(self):
        from app.llm import reset_router

        reset_router()
        import os

        for k in ["GROQ_API_KEY", "CF_ACCOUNT_ID", "CF_API_TOKEN"]:
            os.environ.pop(k, None)
        env = {"OPENAI_API_KEY": "sk-test", "GEMINI_API_KEY": "AIza-test"}
        with patch.dict("os.environ", env, clear=False), patch("openai.OpenAI"):
            from app.llm import get_router

            default_router = get_router()
            grounded_router = get_router(tier="grounded")
        assert [p.name for p in default_router.providers] == ["openai"]
        assert [p.name for p in grounded_router.providers] == ["gemini", "openai"]
        reset_router()
