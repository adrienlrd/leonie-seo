"""Product identification labels must follow the shop language."""

from __future__ import annotations

import pytest

from app.language import SUPPORTED_LANGUAGES
from app.market_analysis.identifier import _build_label_prompt

_ITEMS = [{"id": "1", "title": "The Videographer Snowboard", "description": "", "collections": "", "tags": ""}]


@pytest.mark.parametrize(
    ("language", "needle"),
    [("fr", "français"), ("en", "anglais"), ("de", "allemand"), ("es", "espagnol")],
)
def test_prompt_names_the_shop_language(language: str, needle: str) -> None:
    assert needle in _build_label_prompt(_ITEMS, "", language)


def test_prompt_no_longer_hardcodes_french_output() -> None:
    """It used to demand "un label court en français", so an English catalog
    came back with French labels like "snowboard léger et réactif"."""
    prompt = _build_label_prompt(_ITEMS, "", "en")

    assert "label court (3 à 6 mots)" in prompt
    assert "en français (3 à 6 mots)" not in prompt


@pytest.mark.parametrize("language", SUPPORTED_LANGUAGES)
def test_examples_stay_niche_neutral(language: str) -> None:
    prompt = _build_label_prompt(_ITEMS, "", language).lower()

    for word in ("chat", "chien", "pour chat", "pour chien"):
        assert word not in prompt
