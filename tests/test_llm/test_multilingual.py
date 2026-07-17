"""Tests for multilingual meta generation."""

from __future__ import annotations

import pytest

from app.llm.multilingual import (
    SUPPORTED_LOCALES,
    MultilingualMetaResult,
    _parse_response,
    _primary_keyword,
    generate_meta_all_locales,
    generate_meta_locale,
)
from app.llm.provider import CompletionResult, LLMError, LLMProvider
from app.llm.router import LLMRouter

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_router(text: str = "", *, raises: Exception | None = None) -> LLMRouter:
    class _FakeProvider(LLMProvider):
        name = "fake"
        model = "fake-model"

        def complete(self, prompt, *, system="", max_tokens=512, temperature=0.3, json_mode=False):  # noqa: ARG002
            if raises is not None:
                raise raises
            return CompletionResult(text=text, provider="fake", model="fake-model")

    router = object.__new__(LLMRouter)
    router.providers = [_FakeProvider()]
    router._shop = None
    return router


_PRODUCT = {
    "id": "123",
    "title": "Harnais Premium Chien",
    "product_type": "Harnais",
    "body_html": "<p>Harnais confort fabriqué en France.</p>",
}


# ---------------------------------------------------------------------------
# _parse_response
# ---------------------------------------------------------------------------


def test_parse_response_extracts_title_and_description():
    text = (
        "TITLE: Premium Dog Harness | Léonie\nDESCRIPTION: Comfortable dog harness made in France."
    )
    title, desc = _parse_response(text)
    assert title == "Premium Dog Harness | Léonie"
    assert "Comfortable" in desc


def test_parse_response_case_insensitive():
    text = "title: My Title\ndescription: My Desc"
    title, desc = _parse_response(text)
    assert title == "My Title"
    assert desc == "My Desc"


def test_parse_response_strips_quotes():
    text = "TITLE: \"Quoted Title\"\nDESCRIPTION: 'Quoted desc'"
    title, desc = _parse_response(text)
    assert title == "Quoted Title"
    assert desc == "Quoted desc"


def test_parse_response_missing_description_returns_empty():
    text = "TITLE: Only a title here"
    title, desc = _parse_response(text)
    assert title == "Only a title here"
    assert desc == ""


def test_parse_response_missing_title_returns_empty_strings():
    text = "No recognisable fields here"
    title, desc = _parse_response(text)
    assert title == ""
    assert desc == ""


# ---------------------------------------------------------------------------
# _primary_keyword
# ---------------------------------------------------------------------------


def test_primary_keyword_strips_brand():
    kw = _primary_keyword("Harnais Léonie Delacroix Premium", brand="Léonie Delacroix")
    assert "léonie" not in kw
    assert "delacroix" not in kw
    assert "harnais" in kw


def test_primary_keyword_fallback_to_full_title():
    assert _primary_keyword("Léonie", brand="Léonie Delacroix") == "léonie"


def test_primary_keyword_no_brand_returns_lowercased_title():
    """When brand is None/empty, the title passes through unchanged."""
    assert _primary_keyword("Harnais Léonie", brand=None) == "harnais léonie"


# ---------------------------------------------------------------------------
# MultilingualMetaResult.success
# ---------------------------------------------------------------------------


def test_result_success_when_title_set():
    r = MultilingualMetaResult(locale="en", locale_name="English", title="A", provider="fake")
    assert r.success is True


def test_result_not_success_when_error():
    r = MultilingualMetaResult(locale="en", locale_name="English", error="API down")
    assert r.success is False


def test_result_not_success_when_empty_title():
    r = MultilingualMetaResult(locale="en", locale_name="English", title="")
    assert r.success is False


# ---------------------------------------------------------------------------
# generate_meta_locale
# ---------------------------------------------------------------------------


def test_generate_meta_locale_success():
    response = "TITLE: Premium Dog Harness | Léonie\nDESCRIPTION: Quality harness for dogs, made in France."
    router = _make_router(response)
    result = generate_meta_locale(_PRODUCT, "en", router)

    assert result.success is True
    assert result.locale == "en"
    assert result.locale_name == "English"
    assert result.title == "Premium Dog Harness | Léonie"
    assert result.provider == "fake"


def test_generate_meta_locale_invalid_locale_raises():
    router = _make_router("response")
    with pytest.raises(ValueError, match="Unsupported locale"):
        generate_meta_locale(_PRODUCT, "it", router)


def test_generate_meta_locale_llm_error_sets_error_field():
    router = _make_router(raises=LLMError("rate limited"))
    result = generate_meta_locale(_PRODUCT, "de", router)

    assert result.success is False
    assert "rate limited" in result.error


def test_generate_meta_locale_missing_title_sets_error():
    router = _make_router("DESCRIPTION: Just a description, no title")
    result = generate_meta_locale(_PRODUCT, "nl", router)

    assert result.success is False
    assert result.error is not None


def test_generate_meta_locale_all_supported_locales():
    for locale in SUPPORTED_LOCALES:
        response = f"TITLE: Test title\nDESCRIPTION: Test description for {locale}."
        router = _make_router(response)
        result = generate_meta_locale(_PRODUCT, locale, router)
        assert result.locale == locale
        assert result.success is True


# ---------------------------------------------------------------------------
# generate_meta_all_locales
# ---------------------------------------------------------------------------


def test_generate_meta_all_locales_returns_one_per_locale():
    response = "TITLE: Title\nDESCRIPTION: Description."
    router = _make_router(response)
    results = generate_meta_all_locales(_PRODUCT, ["en", "de"], router)

    assert len(results) == 2
    assert results[0].locale == "en"
    assert results[1].locale == "de"


def test_generate_meta_all_locales_preserves_order():
    response = "TITLE: T\nDESCRIPTION: D."
    router = _make_router(response)
    locales = ["nl", "fr", "en"]
    results = generate_meta_all_locales(_PRODUCT, locales, router)
    assert [r.locale for r in results] == locales


def test_generate_meta_all_locales_invalid_locale_raises():
    router = _make_router("TITLE: T\nDESCRIPTION: D.")
    with pytest.raises(ValueError, match="Unsupported locales"):
        generate_meta_all_locales(_PRODUCT, ["en", "zh"], router)


def test_generate_meta_all_locales_partial_failure_does_not_stop():
    call_count = [0]

    class _FlakyProvider(LLMProvider):
        name = "flaky"
        model = "m"

        def complete(self, prompt, *, system="", max_tokens=512, temperature=0.3, json_mode=False):  # noqa: ARG002
            call_count[0] += 1
            if call_count[0] % 2 == 0:
                raise LLMError("quota exceeded")
            return CompletionResult(text="TITLE: T\nDESCRIPTION: D.", provider="flaky", model="m")

    router = object.__new__(LLMRouter)
    router.providers = [_FlakyProvider()]
    router._shop = None

    results = generate_meta_all_locales(_PRODUCT, ["en", "de", "nl"], router, max_workers=1)
    assert len(results) == 3
    successes = [r for r in results if r.success]
    assert len(successes) >= 1
