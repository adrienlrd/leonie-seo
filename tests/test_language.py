"""Tests for the per-shop app language setting and market mapping."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.language import (
    MARKETS,
    SUPPORTED_LANGUAGES,
    get_market,
    get_shop_language,
    set_shop_language,
)

SHOP = "test.myshopify.com"


@pytest.fixture(autouse=True)
def _use_tmp_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db = tmp_path / "test.db"
    monkeypatch.setattr("app.shop_config_store.DB_PATH", db)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    from app.db import init_db

    init_db(db_path=db)


def test_default_language_is_english() -> None:
    assert get_shop_language(SHOP) == "en"


def test_set_and_get_roundtrip() -> None:
    set_shop_language(SHOP, "de")
    assert get_shop_language(SHOP) == "de"


def test_set_rejects_unsupported_language() -> None:
    with pytest.raises(ValueError):
        set_shop_language(SHOP, "nl")


def test_every_supported_language_has_a_market() -> None:
    assert set(MARKETS) == set(SUPPORTED_LANGUAGES)
    for market in MARKETS.values():
        assert market.dataforseo_location_code > 0
        assert market.dataforseo_language_code
        assert market.suggest_hl and market.suggest_gl
        assert market.trends_geo and market.trends_hl


def test_market_specifics() -> None:
    assert MARKETS["fr"].dataforseo_location_code == 2250
    assert MARKETS["en"].suggest_gl == "US"  # English market = United States
    assert MARKETS["de"].country_label == "Deutschland"
    assert get_market("zz") is MARKETS["en"]  # unknown → English market
