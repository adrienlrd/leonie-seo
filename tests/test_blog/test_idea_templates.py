"""Blog idea suggestions must follow the shop language and stay niche-neutral."""

from __future__ import annotations

import re
from datetime import datetime

import pytest

from app.blog.idea_generator import build_blog_idea_suggestions
from app.blog.idea_templates import (
    IDEA_TEMPLATES,
    SEASON_BY_MONTH,
    SEASON_LABELS,
    SEASON_TRIGGERS,
    season_for,
)
from app.language import SUPPORTED_LANGUAGES

_JANUARY = datetime(2026, 1, 15)

_PRODUCTS = {
    "fr": [{"product_id": "1", "product_title": "Manteau d'hiver", "seo_keywords": [{"query": "manteau hiver"}]}],
    "en": [{"product_id": "1", "product_title": "Winter jacket", "seo_keywords": [{"query": "winter jacket"}]}],
    "de": [{"product_id": "1", "product_title": "Wintermantel", "seo_keywords": [{"query": "winter mantel"}]}],
    "es": [{"product_id": "1", "product_title": "Abrigo de invierno", "seo_keywords": [{"query": "abrigo invierno"}]}],
}


@pytest.mark.parametrize("language", SUPPORTED_LANGUAGES)
def test_seasonal_ideas_fire_in_every_language(language: str) -> None:
    """The triggers used to be French pet words, so this angle never fired abroad."""
    ideas = build_blog_idea_suggestions(
        products=_PRODUCTS[language], now=_JANUARY, language=language
    )

    assert any(idea["angle"] == "seasonal" for idea in ideas)


@pytest.mark.parametrize(
    ("language", "needle"),
    [
        ("fr", "Froid de l'hiver"),
        ("en", "Winter cold"),
        ("de", "Winterkälte"),
        ("es", "Frío del invierno"),
    ],
)
def test_seasonal_wording_follows_the_shop_language(language: str, needle: str) -> None:
    seasonal = next(
        idea
        for idea in build_blog_idea_suggestions(
            products=_PRODUCTS[language], now=_JANUARY, language=language
        )
        if idea["angle"] == "seasonal"
    )

    assert needle in seasonal["title"]


def test_default_language_is_english() -> None:
    seasonal = next(
        idea
        for idea in build_blog_idea_suggestions(products=_PRODUCTS["en"], now=_JANUARY)
        if idea["angle"] == "seasonal"
    )

    assert "Winter cold" in seasonal["title"]


def test_unknown_language_falls_back_to_english() -> None:
    assert season_for("it", 1) == season_for("en", 1)


@pytest.mark.parametrize("language", SUPPORTED_LANGUAGES)
def test_every_language_covers_every_season_and_angle(language: str) -> None:
    keys = set(SEASON_BY_MONTH.values())

    assert set(SEASON_LABELS[language]) == keys
    assert set(SEASON_TRIGGERS[language]) == keys
    assert set(IDEA_TEMPLATES[language]) == set(IDEA_TEMPLATES["en"])


@pytest.mark.parametrize("language", SUPPORTED_LANGUAGES)
def test_wording_stays_niche_neutral(language: str) -> None:
    """The seasonal calendar and idea copy were written for a pet shop."""
    corpus = " ".join(
        [
            *(" ".join(t) for t in SEASON_TRIGGERS[language].values()),
            *SEASON_LABELS[language].values(),
            *(
                f"{angle['title']} {angle['intro']} {' '.join(angle['outline'])}"
                for angle in IDEA_TEMPLATES[language].values()
            ),
        ]
    ).lower()
    banned = ("chien", "chat", "lapin", "animal", "compagnon", "dog", "cat", "pet", "hund", "katze", "perro", "gato")
    found = re.findall(rf"\b(?:{'|'.join(banned)})s?\b", corpus)

    assert found == [], f"{language}: niche-specific words {found} are back"
