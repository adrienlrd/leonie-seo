"""Cost-control behaviour for the DataForSEO provider.

The Google Ads search-volume endpoint costs ~10x the Labs endpoints and is
redundant with keyword_ideas, so it must be OFF unless explicitly enabled.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from app.market_analysis.providers.dataforseo_provider import DataForSEOProvider


def _enabled_provider(monkeypatch):
    monkeypatch.setenv("DATAFORSEO_LOGIN", "x@example.com")
    monkeypatch.setenv("DATAFORSEO_PASSWORD", "secret")
    monkeypatch.setenv("DATAFORSEO_ENABLED", "true")
    return DataForSEOProvider()


def test_search_volume_endpoint_skipped_by_default(monkeypatch):
    monkeypatch.delenv("DATAFORSEO_SEARCH_VOLUME_ENABLED", raising=False)
    provider = _enabled_provider(monkeypatch)
    vol = MagicMock(return_value={})
    diff = MagicMock(return_value={"fontaine eau chat": 40})
    monkeypatch.setattr(provider, "_fetch_search_volumes", vol)
    monkeypatch.setattr(provider, "_fetch_keyword_difficulty", diff)

    out = provider.enrich([{"keyword": "fontaine eau chat"}], shop="s.myshopify.com")

    vol.assert_not_called()  # costly Google Ads call avoided
    diff.assert_called_once()  # cheap Labs difficulty still applied
    assert out[0]["difficulty_score"] == 40
    assert out[0]["source"] == "dataforseo"


def test_search_volume_endpoint_used_when_enabled(monkeypatch):
    monkeypatch.setenv("DATAFORSEO_SEARCH_VOLUME_ENABLED", "true")
    provider = _enabled_provider(monkeypatch)
    vol = MagicMock(
        return_value={
            "fontaine eau chat": {"search_volume": 880, "cpc": 1.2, "competition_index": 30}
        }
    )
    monkeypatch.setattr(provider, "_fetch_search_volumes", vol)
    monkeypatch.setattr(provider, "_fetch_keyword_difficulty", MagicMock(return_value={}))

    out = provider.enrich([{"keyword": "fontaine eau chat"}], shop="s.myshopify.com")

    vol.assert_called_once()
    assert out[0]["search_volume"] == 880
