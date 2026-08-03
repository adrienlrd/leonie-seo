"""Merchant enrichment questions must follow the shop's app language."""

from __future__ import annotations

import re

import pytest

from app.language import SUPPORTED_LANGUAGES
from app.market_analysis.engine import _build_enrichment_questions
from app.market_analysis.enrichment_templates import (
    QUESTION_TEMPLATES,
    WHY_TEMPLATES,
    questions_for,
    why_for,
)

_KEYWORDS = [{"query": "snowboard boots", "paa_questions": []}]
_MISSING = [{"key": "warranty", "label": "Warranty"}]


def _questions(language: str) -> list[dict]:
    return _build_enrichment_questions(_KEYWORDS, _MISSING, {}, language)


@pytest.mark.parametrize(
    ("language", "needle"),
    [
        ("fr", "Quelle garantie"),
        ("en", "What warranty"),
        ("de", "Welche Garantie"),
        ("es", "¿Qué garantía"),
    ],
)
def test_questions_are_written_in_the_shop_language(language: str, needle: str) -> None:
    warranty = next(q for q in _questions(language) if q["key"] == "warranty")

    assert warranty["question"].startswith(needle)
    assert "snowboard boots" in warranty["question"]


def test_unknown_language_falls_back_to_english() -> None:
    assert questions_for("it") == QUESTION_TEMPLATES["en"]
    assert why_for("it") == WHY_TEMPLATES["en"]


def test_default_language_is_english_not_french() -> None:
    """A silent French fallback is what hid the untranslated questions."""
    warranty = next(q for q in _build_enrichment_questions(_KEYWORDS, _MISSING, {}) if q["key"] == "warranty")

    assert warranty["question"].startswith("What warranty")


@pytest.mark.parametrize("language", SUPPORTED_LANGUAGES)
def test_every_language_covers_every_key(language: str) -> None:
    assert set(QUESTION_TEMPLATES[language]) == set(QUESTION_TEMPLATES["en"])
    assert set(WHY_TEMPLATES[language]) == set(WHY_TEMPLATES["en"])


@pytest.mark.parametrize("language", SUPPORTED_LANGUAGES)
def test_examples_stay_niche_neutral(language: str) -> None:
    """The templates shipped with pet-food examples, absurd on any other store."""
    corpus = " ".join(
        f"{question} {placeholder}"
        for question, placeholder in QUESTION_TEMPLATES[language].values()
    ).lower()

    banned = ("chien", "chat", "lapin", "animal", "dog", "cat", "pet", "hund", "katze", "perro", "gato")
    # Whole words only — "cat" is a substring of "certification".
    found = re.findall(rf"\b(?:{'|'.join(banned)})s?\b", corpus)

    assert found == [], f"{language}: niche-specific words {found} are back"


@pytest.mark.parametrize("language", SUPPORTED_LANGUAGES)
def test_why_it_matters_is_localized_too(language: str) -> None:
    targets = next(q for q in _questions(language) if q["key"] == "targets")

    assert targets["why_it_matters"] == WHY_TEMPLATES[language]["answerability"]
