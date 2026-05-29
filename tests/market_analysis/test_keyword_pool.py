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
        "difficulty_source": "dataforseo",
    }
    specific = {
        "query": "harnais en cuir pour chien",
        "demand_score": 35,
        "competition_score": 30,
        "product_fit_score": 80,
        "data_source": "dataforseo",
        "difficulty_source": "dataforseo",
    }
    # A small store should target the winnable, product-specific mid-tail, not the
    # 27k-volume head term it cannot realistically rank for.
    assert engine._keyword_priority_score(specific) > engine._keyword_priority_score(head)


def test_unknown_difficulty_treated_as_neutral_not_winnable():
    # A non-zero ESTIMATED difficulty must be treated as neutral (50), not trusted as
    # a winnability signal — only a real DataForSEO difficulty earns the bonus.
    real_low_diff = {
        "query": "abc def",
        "demand_score": 55,
        "competition_score": 20,
        "product_fit_score": 80,
        "data_source": "dataforseo",
        "difficulty_source": "dataforseo",
    }
    estimated = {**real_low_diff, "difficulty_source": "free_estimated"}
    assert engine._keyword_priority_score(real_low_diff) > engine._keyword_priority_score(estimated)


def test_accessory_keyword_penalized_when_product_is_not_the_accessory():
    product_words = engine._content_words("fontaine à eau sans fil pour chat inox")
    accessory = {
        "query": "filtre fontaine a eau chat",
        "demand_score": 55,
        "competition_score": 50,
        "product_fit_score": 80,
        "data_source": "dataforseo",
        "difficulty_source": "dataforseo",
    }
    product = {**accessory, "query": "fontaine eau chat sans fil"}
    score_acc = engine._keyword_priority_score(accessory, product_words)
    score_prod = engine._keyword_priority_score(product, product_words)
    assert score_prod > score_acc  # the fountain term beats the spare-filter term
    # Penalty only applies with product context.
    assert engine._keyword_priority_score(accessory) > score_acc


def test_identifier_calls_llm_deterministically():
    from unittest.mock import patch

    from app.market_analysis import identifier

    router = MagicMock()
    router.complete.return_value = CompletionResult(
        text='{"gid://shopify/Product/1": "Fontaine chat"}', provider="openai", model="m"
    )
    with patch.object(identifier, "get_router", return_value=router):
        identifier.generate_product_labels(
            [{"id": "gid://shopify/Product/1", "title": "Fontaine"}], "s.myshopify.com"
        )
    kwargs = router.complete.call_args.kwargs
    assert kwargs["temperature"] == 0.0
    assert kwargs["json_mode"] is True


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


def test_high_volume_unknown_difficulty_is_penalized():
    # Head term with huge volume but NO real difficulty must not beat a winnable
    # mid-tail — low ads competition is not a proxy for organic difficulty.
    head = {
        "query": "harnais chien",
        "demand_score": 90,
        "competition_score": 0,
        "product_fit_score": 90,
        "data_source": "dataforseo",
        "difficulty_source": "free_estimated",
    }
    mid = {
        "query": "harnais chien cuir",
        "demand_score": 55,
        "competition_score": 0,
        "product_fit_score": 75,
        "data_source": "dataforseo",
        "difficulty_source": "free_estimated",
    }
    assert engine._keyword_priority_score(mid) > engine._keyword_priority_score(head)


def test_real_traffic_keyword_outranks_equivalent_ai_estimate():
    # A keyword with real GSC traffic evidence must outrank an identical AI estimate.
    gsc = {
        "query": "fontaine eau chat",
        "demand_score": 65,
        "competition_score": 50,
        "product_fit_score": 80,
        "data_source": "gsc",
        "difficulty_source": "free_estimated",
        "gsc_impressions": 300,
    }
    llm = {**gsc, "data_source": "llm_estimated", "gsc_impressions": None}
    assert engine._keyword_priority_score(gsc) > engine._keyword_priority_score(llm)


def test_assign_targets_primary_is_real_not_ai_proposed():
    keywords = [
        {
            "query": "gadget chat",
            "data_source": "llm_proposed",
            "difficulty_source": "free_estimated",
            "demand_score": 40,
            "competition_score": 50,
            "product_fit_score": 90,
        },
        {
            "query": "fontaine eau chat",
            "data_source": "dataforseo",
            "difficulty_source": "dataforseo",
            "demand_score": 75,
            "competition_score": 40,
            "product_fit_score": 80,
            "search_volume": 1500,
        },
    ]
    ranked = engine._assign_keyword_targets(keywords, engine._content_words("fontaine eau chat"))
    assert ranked[0]["query"] == "fontaine eau chat"
    assert ranked[0]["target_role"] == "primary"


def test_keyword_query_prefix_is_cleaned():
    assert engine._clean_keyword_query("new: fontaine d'eau pour chat") == (
        "fontaine d'eau pour chat"
    )
    assert engine._clean_keyword_query("Nouveau - harnais chien cuir") == "harnais chien cuir"
    assert engine._clean_keyword_query("  harnais   chien  ") == "harnais chien"
    assert engine._clean_keyword_query("fontaine eau chat") == "fontaine eau chat"


def test_merge_cleans_added_keyword_query():
    pool = [{"query": "fontaine eau chat", "data_source": "dataforseo", "search_volume": 800}]
    llm = [{"query": "new: fontaine inox sans fil", "product_fit_score": 85}]
    out = engine._merge_pass1_selection(llm, pool, min_real_floor=1)
    added = next(k for k in out if k.get("data_source") == "llm_proposed")
    assert added["query"] == "fontaine inox sans fil"


def test_coerce_seo_keywords_strips_prefix():
    out = engine._coerce_seo_keywords([{"query": "new: pull cachemire chien", "intent_type": "x"}])
    assert out[0]["query"] == "pull cachemire chien"


def test_complete_json_uses_deterministic_json_mode_by_default():
    router = MagicMock()
    router.complete.return_value = CompletionResult(
        text='{"seo_keywords": []}', provider="openai", model="gpt-4o-mini"
    )
    engine._complete_json(router, "prompt", ("seo_keywords",), {"seo_keywords": []}, "Produit")
    kwargs = router.complete.call_args.kwargs
    assert kwargs["json_mode"] is True
