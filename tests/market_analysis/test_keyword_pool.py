"""Tests for the real-data-first keyword candidate pool and Pass 1 selection merge.

These cover the core of the reliability refactor: keyword candidates are sourced
from real data (GSC, DataForSEO, Google Suggest, Trends) BEFORE the LLM, and the
LLM only selects/qualifies — it can never silently drop observed demand.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from app.llm.provider import CompletionResult
from app.market_analysis import engine


class _FakeDataForSEO:
    available = True

    def __init__(self, ideas=None):
        self._ideas = ideas or []

    def fetch_keyword_ideas(self, seeds, *, limit=25):  # noqa: ARG002
        return list(self._ideas)


def _fields(**overrides):
    base = {
        "product_title": "Fontaine à chat",
        "merchant_label": "",
        "handle": "fontaine-chat",
        "source_product_text": "Fontaine à chat fontaine eau filtrée",
        "trend_top": [],
        "trend_rising": [],
    }
    base.update(overrides)
    return base


def test_pool_includes_gsc_matched_queries_with_real_metrics():
    gsc_rows = [
        {"query": "fontaine à chat", "impressions": 500, "clicks": 20, "position": 5.0},
        {"query": "accessoire jardin", "impressions": 999, "clicks": 1, "position": 50.0},
    ]
    pool = engine._build_keyword_candidate_pool(
        _fields(), gsc_rows, dataforseo=None, suggest_fetcher=lambda _s: []
    )
    by_query = {c["query"]: c for c in pool}
    assert "fontaine à chat" in by_query
    assert by_query["fontaine à chat"]["data_source"] == "gsc"
    assert by_query["fontaine à chat"]["gsc_impressions"] == 500
    # Unrelated GSC query (no shared content word) is excluded.
    assert "accessoire jardin" not in by_query


def test_pool_includes_suggest_and_trends_candidates():
    pool = engine._build_keyword_candidate_pool(
        _fields(trend_top=["fontaine chat design"]),
        [],
        dataforseo=None,
        suggest_fetcher=lambda _s: [{"keyword": "fontaine chat silencieuse"}],
    )
    by_query = {c["query"]: c for c in pool}
    assert by_query["fontaine chat silencieuse"]["data_source"] == "google_suggest"
    assert by_query["fontaine chat design"]["data_source"] == "trends"


def test_pool_includes_dataforseo_ideas_and_ranks_them_first():
    idea = {
        "query": "fontaine chat silencieuse",
        "intent_type": "commercial",
        "demand_score": 80,
        "competition_score": 20,
        "product_fit_score": 0,
        "reason": "idée",
        "data_source": "dataforseo",
        "difficulty_source": "dataforseo",
        "search_volume": 2400,
        "cpc": 1.1,
        "ads_competition": 0.3,
        "notes": [],
    }
    pool = engine._build_keyword_candidate_pool(
        _fields(),
        [{"query": "fontaine à chat", "impressions": 50, "clicks": 2, "position": 8.0}],
        dataforseo=_FakeDataForSEO(ideas=[idea]),
        suggest_fetcher=lambda _s: [],
    )
    # DataForSEO (real volume) ranks above the lower-priority GSC candidate.
    assert pool[0]["query"] == "fontaine chat silencieuse"
    assert pool[0]["data_source"] == "dataforseo"
    assert pool[0]["search_volume"] == 2400


def test_pool_dedup_keeps_dataforseo_base_but_preserves_gsc_metrics():
    idea = {
        "query": "fontaine chat",
        "intent_type": "commercial",
        "demand_score": 70,
        "competition_score": 30,
        "product_fit_score": 0,
        "reason": "idée",
        "data_source": "dataforseo",
        "difficulty_source": "dataforseo",
        "search_volume": 1800,
        "cpc": 0.9,
        "ads_competition": 0.4,
        "notes": [],
    }
    pool = engine._build_keyword_candidate_pool(
        _fields(),
        [{"query": "fontaine chat", "impressions": 320, "clicks": 12, "position": 6.0}],
        dataforseo=_FakeDataForSEO(ideas=[idea]),
        suggest_fetcher=lambda _s: [],
    )
    merged = next(c for c in pool if c["query"] == "fontaine chat")
    assert merged["data_source"] == "dataforseo"  # higher-priority base wins
    assert merged["search_volume"] == 1800
    assert merged["gsc_impressions"] == 320  # observed GSC metrics preserved


def test_merge_pass1_selection_inherits_real_metrics_and_flags_added():
    pool = [
        {"query": "fontaine chat", "data_source": "dataforseo", "search_volume": 1000},
        {"query": "fontaine eau chat", "data_source": "gsc", "gsc_impressions": 300},
    ]
    llm = [
        {
            "query": "fontaine chat",
            "intent_type": "commercial",
            "product_fit_score": 88,
            "reason": "r",
        },
        {"query": "fontaine chat extérieur", "product_fit_score": 40, "reason": "gap"},
    ]
    out = engine._merge_pass1_selection(llm, pool, min_real_floor=1)
    by_query = {c["query"]: c for c in out}
    # Selected real keyword keeps its real metrics + gains the LLM's labels.
    assert by_query["fontaine chat"]["search_volume"] == 1000
    assert by_query["fontaine chat"]["intent_type"] == "commercial"
    assert by_query["fontaine chat"]["product_fit_score"] == 88
    # LLM-added keyword is clearly flagged, never confused with real demand.
    assert by_query["fontaine chat extérieur"]["data_source"] == "llm_proposed"


def test_merge_pass1_selection_floor_readds_skipped_real_keywords():
    pool = [
        {"query": "fontaine chat", "data_source": "dataforseo", "search_volume": 1000},
        {"query": "fontaine eau chat", "data_source": "gsc", "gsc_impressions": 300},
        {"query": "abreuvoir chat", "data_source": "dataforseo", "search_volume": 500},
    ]
    # LLM only returns a brand-new keyword and ignores the whole real pool.
    llm = [{"query": "gadget chat inutile", "product_fit_score": 10}]
    out = engine._merge_pass1_selection(llm, pool, min_real_floor=2)
    queries = {c["query"] for c in out}
    # The floor guarantees the strongest real candidates are kept regardless.
    assert "fontaine chat" in queries
    real_count = sum(1 for c in out if engine._is_real_keyword(c))
    assert real_count >= 2


def test_priority_prefers_winnable_specific_over_hard_head_term():
    head = {
        "query": "harnais chien",
        "demand_score": 95,
        "competition_score": 90,
        "product_fit_score": 90,
        "data_source": "dataforseo",
    }
    specific = {
        "query": "harnais en cuir pour chien",
        "demand_score": 35,
        "competition_score": 30,
        "product_fit_score": 80,
        "data_source": "dataforseo",
    }
    # A small store should target the winnable, product-specific mid-tail, not the
    # 27k-volume head term it cannot realistically rank for.
    assert engine._keyword_priority_score(specific) > engine._keyword_priority_score(head)


def test_normalize_confidence_maps_french_and_variants():
    assert engine._normalize_confidence("élevée") == "high"
    assert engine._normalize_confidence("HIGH") == "high"
    assert engine._normalize_confidence("moyenne") == "medium"
    assert engine._normalize_confidence("faible") == "low"
    assert engine._normalize_confidence("") == ""
    assert engine._normalize_confidence("inattendu") == "medium"


def test_coerce_geo_questions_normalizes_french_confidence():
    out = engine._coerce_geo_questions(
        [
            {
                "question": "Quelle fontaine ?",
                "answer_angle": "guide",
                "content_block_type": "faq",
                "confidence": "élevée",
            }
        ]
    )
    assert out[0]["confidence"] == "high"


def test_complete_json_uses_deterministic_json_mode_by_default():
    router = MagicMock()
    router.complete.return_value = CompletionResult(
        text='{"seo_keywords": []}', provider="openai", model="gpt-4o-mini"
    )
    engine._complete_json(router, "prompt", ("seo_keywords",), {"seo_keywords": []}, "Produit")
    kwargs = router.complete.call_args.kwargs
    assert kwargs["json_mode"] is True
