"""Per-shop app language — one setting drives UI, prompts and keyword market.

Stored in `shop_config` under `app_language`. Default resolution happens
frontend-side (Shopify primaryLocale, persisted on first read); the backend
default is English for a never-configured shop.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.shop_config_store import get_shop_config, set_shop_config

SUPPORTED_LANGUAGES = ("fr", "en", "de", "es")
DEFAULT_LANGUAGE = "en"

_CONFIG_KEY = "app_language"


@dataclass(frozen=True)
class Market:
    """Search-market parameters for one supported language."""

    dataforseo_location_code: int
    dataforseo_language_code: str
    suggest_hl: str
    suggest_gl: str
    trends_geo: str
    trends_hl: str
    trends_tz: int
    country_label: str
    language_label: str


MARKETS: dict[str, Market] = {
    "fr": Market(2250, "fr", "fr", "FR", "FR", "fr-FR", 60, "France", "français"),
    "en": Market(2840, "en", "en", "US", "US", "en-US", -300, "United States", "English"),
    "de": Market(2276, "de", "de", "DE", "DE", "de-DE", 60, "Deutschland", "Deutsch"),
    "es": Market(2724, "es", "es", "ES", "ES", "es-ES", 60, "España", "español"),
}


def get_shop_language(shop: str) -> str:
    """Return the shop's app language, defaulting to English."""
    value = get_shop_config(shop, _CONFIG_KEY)
    return value if value in SUPPORTED_LANGUAGES else DEFAULT_LANGUAGE


def set_shop_language(shop: str, language: str) -> None:
    """Persist the shop's app language (must be one of SUPPORTED_LANGUAGES)."""
    if language not in SUPPORTED_LANGUAGES:
        raise ValueError(f"Unsupported language: {language!r}")
    set_shop_config(shop, _CONFIG_KEY, language)


def get_market(language: str) -> Market:
    """Return the search market for a language (English market as fallback)."""
    return MARKETS.get(language, MARKETS[DEFAULT_LANGUAGE])
