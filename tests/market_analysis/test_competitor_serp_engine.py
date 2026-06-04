"""Tests for the competitor profile engine (SERP aggregation + LLM synthesis)."""

from __future__ import annotations

import json
from typing import Any

import app.market_analysis.competitor_serp_engine as engine


def _serp_cache() -> dict[str, Any]:
    return {
        "fontaine chat": {
            "paa": ["Comment nettoyer une fontaine ?"],
            "featured_snippet": "Une fontaine à eau pour chat...",
            "top_competitors": [
                {"domain": "zooplus.fr", "title": "Fontaine chat — Zooplus", "url": "https://zooplus.fr/fontaine", "rank": 1},
                {"domain": "wanimo.com", "title": "Fontaine pour chat", "url": "https://wanimo.com/fontaine", "rank": 4},
            ],
        },
        "gamelle chat": {
            "paa": ["Quelle gamelle choisir ?"],
            "featured_snippet": None,
            "top_competitors": [
                {"domain": "zooplus.fr", "title": "Gamelle chat — Zooplus", "url": "https://zooplus.fr/gamelle", "rank": 2},
            ],
        },
    }


def _market_result() -> dict[str, Any]:
    return {
        "products": [
            {"seo_keywords": [{"query": "fontaine chat"}, {"query": "gamelle chat"}]},
        ],
        "competitor_signals": [],
    }


def test_aggregate_groups_by_domain_and_sorts_by_strength(monkeypatch):
    monkeypatch.setattr(engine, "load_latest_result", lambda shop: _market_result())
    monkeypatch.setattr(
        engine.keyword_cache, "get_many", lambda *a, **k: _serp_cache()
    )

    out = engine.aggregate_competitors_from_serp("demo.myshopify.com")

    assert out["enriched"] is False
    assert out["keywords_used"] == 2
    domains = [c["domain"] for c in out["competitors"]]
    assert domains[0] == "zooplus.fr"  # 2 keywords, best rank 1 → strongest
    zooplus = out["competitors"][0]
    assert zooplus["ranked_keyword_count"] == 2
    assert zooplus["best_rank"] == 1
    assert zooplus["top_page_url"] == "https://zooplus.fr/fontaine"  # best rank
    assert zooplus["synthesis"] is None
    assert "Comment nettoyer une fontaine ?" in zooplus["paa_questions"]


def test_aggregate_excludes_merchant_domain(monkeypatch):
    cache = _serp_cache()
    cache["fontaine chat"]["top_competitors"].append(
        {"domain": "demo.myshopify.com", "title": "Ma fontaine", "url": "https://demo.myshopify.com/x", "rank": 3}
    )
    monkeypatch.setattr(engine, "load_latest_result", lambda shop: _market_result())
    monkeypatch.setattr(engine.keyword_cache, "get_many", lambda *a, **k: cache)

    out = engine.aggregate_competitors_from_serp("demo.myshopify.com")

    assert "demo.myshopify.com" not in [c["domain"] for c in out["competitors"]]


def test_aggregate_no_market_analysis(monkeypatch):
    monkeypatch.setattr(engine, "load_latest_result", lambda shop: None)
    out = engine.aggregate_competitors_from_serp("demo.myshopify.com")
    assert out["error"] == "no_market_analysis"
    assert out["competitors"] == []


def test_synthesize_parses_llm_json():
    class _Router:
        def complete(self, prompt, **kwargs):
            class _R:
                text = json.dumps({
                    "title_style": "Technique et orienté prix",
                    "strengths": ["FAQ systématique", "Schema Product"],
                    "opportunities": ["Peu de contenu éducatif"],
                    "inspiration": ["Ajoute un guide d'achat"],
                })
            return _R()

    competitor = {
        "domain": "zooplus.fr",
        "strength_label": "élevée",
        "ranked_keyword_count": 2,
        "sample_titles": ["Fontaine chat"],
        "ranked_keywords": [{"keyword": "fontaine chat", "rank": 1}],
        "paa_questions": ["Comment nettoyer ?"],
    }
    out = engine._synthesize_competitor(competitor, {"word_count": 800}, None, _Router())

    assert out["title_style"] == "Technique et orienté prix"
    assert out["strengths"] == ["FAQ systématique", "Schema Product"]
    assert out["opportunities"] == ["Peu de contenu éducatif"]
    assert out["inspiration"] == ["Ajoute un guide d'achat"]


def test_synthesize_fail_open_on_bad_json():
    class _Router:
        def complete(self, prompt, **kwargs):
            class _R:
                text = "not json at all"
            return _R()

    competitor = {
        "domain": "zooplus.fr",
        "strength_label": "élevée",
        "ranked_keyword_count": 2,
        "sample_titles": [],
        "ranked_keywords": [],
        "paa_questions": [],
    }
    assert engine._synthesize_competitor(competitor, None, None, _Router()) is None


def test_synthesize_returns_none_without_router():
    competitor = {
        "domain": "zooplus.fr",
        "strength_label": "élevée",
        "ranked_keyword_count": 0,
        "sample_titles": [],
        "ranked_keywords": [],
        "paa_questions": [],
    }
    assert engine._synthesize_competitor(competitor, None, None, None) is None
