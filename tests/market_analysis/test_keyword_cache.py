"""Shared keyword cache: cost dedup, cross-shop sharing, TTL, and reliability.

These tests target the multi-tenant cost lever and the user's priorities: keyword
data must be consistent between two analyses and between two products (same keyword
→ same metrics, fetched once and shared), and the cache must never break enrichment.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from app.db import init_db
from app.market_analysis import keyword_cache
from app.market_analysis.providers.dataforseo_provider import DataForSEOProvider


def _provider(monkeypatch, tmp_path, *, with_volume=True, init=True):
    monkeypatch.setenv("DATAFORSEO_LOGIN", "x@example.com")
    monkeypatch.setenv("DATAFORSEO_PASSWORD", "secret")
    monkeypatch.setenv("DATAFORSEO_ENABLED", "true")
    if with_volume:
        monkeypatch.setenv("DATAFORSEO_SEARCH_VOLUME_ENABLED", "true")
    else:
        monkeypatch.delenv("DATAFORSEO_SEARCH_VOLUME_ENABLED", raising=False)
    cache_db = tmp_path / "cache.db"
    if init:
        init_db(cache_db)
    return DataForSEOProvider(cache_db_path=cache_db)


def _patch_metrics(monkeypatch, provider, volume=880, cpc=1.0, comp=30, difficulty=55):
    vol = MagicMock(
        return_value={
            "fontaine eau chat": {"search_volume": volume, "cpc": cpc, "competition_index": comp}
        }
    )
    diff = MagicMock(return_value={"fontaine eau chat": difficulty})
    monkeypatch.setattr(provider, "_fetch_search_volumes", vol)
    monkeypatch.setattr(provider, "_fetch_keyword_difficulty", diff)
    return vol, diff


def test_second_analysis_served_from_cache(monkeypatch, tmp_path):
    provider = _provider(monkeypatch, tmp_path)
    vol, diff = _patch_metrics(monkeypatch, provider)

    r1 = provider.enrich([{"keyword": "fontaine eau chat"}], shop="a.myshopify.com")
    r2 = provider.enrich([{"keyword": "fontaine eau chat"}], shop="a.myshopify.com")

    # Reliability between two analyses: identical metrics, and the API was hit once.
    assert vol.call_count == 1
    assert diff.call_count == 1
    assert r1[0]["search_volume"] == r2[0]["search_volume"] == 880
    assert r1[0]["difficulty_score"] == r2[0]["difficulty_score"] == 55
    assert r2[0]["source"] == "dataforseo"


def test_cache_is_shared_across_shops(monkeypatch, tmp_path):
    provider = _provider(monkeypatch, tmp_path)
    vol, diff = _patch_metrics(monkeypatch, provider)

    provider.enrich([{"keyword": "fontaine eau chat"}], shop="shop-a.myshopify.com")
    out_b = provider.enrich([{"keyword": "fontaine eau chat"}], shop="shop-b.myshopify.com")

    # A different shop reuses the cached market data — the lever that flattens cost.
    assert vol.call_count == 1
    assert out_b[0]["search_volume"] == 880


def test_shared_keyword_fetched_once_across_products(monkeypatch, tmp_path):
    provider = _provider(monkeypatch, tmp_path)
    diff = MagicMock(return_value={})
    vol = MagicMock(
        side_effect=lambda kws: {
            k.lower(): {"search_volume": 500, "cpc": None, "competition_index": None} for k in kws
        }
    )
    monkeypatch.setattr(provider, "_fetch_search_volumes", vol)
    monkeypatch.setattr(provider, "_fetch_keyword_difficulty", diff)

    provider.enrich([{"keyword": "produit a"}, {"keyword": "fontaine eau chat"}], shop="s")
    provider.enrich([{"keyword": "produit b"}, {"keyword": "fontaine eau chat"}], shop="s")

    # The shared keyword is only ever sent to the API on the first product.
    first_call_kws = vol.call_args_list[0].args[0]
    second_call_kws = vol.call_args_list[1].args[0]
    assert "fontaine eau chat" in first_call_kws
    assert "fontaine eau chat" not in second_call_kws


def test_expired_entry_is_not_returned(tmp_path):
    cache_db = tmp_path / "cache.db"
    init_db(cache_db)
    keyword_cache.set_many(
        keyword_cache.METRICS,
        {"fontaine eau chat": {"search_volume": 10, "difficulty": 20}},
        location_code=2250,
        language_code="fr",
        ttl_days=-1,  # already expired
        db_path=cache_db,
    )
    got = keyword_cache.get_many(
        keyword_cache.METRICS,
        ["fontaine eau chat"],
        location_code=2250,
        language_code="fr",
        db_path=cache_db,
    )
    assert got == {}


def test_enrich_is_fail_open_when_cache_unavailable(monkeypatch, tmp_path):
    # Cache DB file exists but the table was never created → cache reads/writes raise
    # internally; enrichment must still succeed (best-effort cache).
    provider = _provider(monkeypatch, tmp_path, init=False)
    _, diff = _patch_metrics(monkeypatch, provider)

    out = provider.enrich([{"keyword": "fontaine eau chat"}], shop="s")

    assert out[0]["difficulty_score"] == 55
    assert out[0]["source"] == "dataforseo"


def test_serp_intelligence_is_cached(monkeypatch, tmp_path):
    provider = _provider(monkeypatch, tmp_path)
    serp = MagicMock(
        return_value={
            "fontaine eau chat": [
                {"type": "people_also_ask", "title": "Comment nettoyer ?"},
            ]
        }
    )
    monkeypatch.setattr(provider, "_fetch_serp", serp)

    first = provider.fetch_serp_intelligence(["fontaine eau chat"])
    second = provider.fetch_serp_intelligence(["fontaine eau chat"])

    assert serp.call_count == 1  # second served from cache
    assert first["fontaine eau chat"]["paa"] == ["Comment nettoyer ?"]
    assert second["fontaine eau chat"]["paa"] == ["Comment nettoyer ?"]
