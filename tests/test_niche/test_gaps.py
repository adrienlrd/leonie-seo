"""Tests for keyword gap analysis and saturation scoring."""

from __future__ import annotations

from app.niche.clustering import cluster_products
from app.niche.gaps import (
    _normalize_query,
    _opportunity_score,
    _saturation,
    analyze_keyword_gaps,
)
from app.niche.models import KeywordGap

# ── Fixtures ──────────────────────────────────────────────────────────────────

_CLUSTERS = cluster_products(
    [
        {
            "id": "1",
            "title": "Pardessus chien imperméable",
            "product_type": "Vêtements chien",
            "tags": [],
        },
        {"id": "2", "title": "Pull chien laine", "product_type": "Vêtements chien", "tags": []},
        {
            "id": "3",
            "title": "Fontaine eau chat céramique",
            "product_type": "Fontaines",
            "tags": [],
        },
        {"id": "4", "title": "Griffoir chat sisal", "product_type": "Griffoirs", "tags": []},
    ]
)


def _gsc_row(query: str, impressions: int = 100, clicks: int = 5, position: float = 25.0) -> dict:
    return {"query": query, "impressions": impressions, "clicks": clicks, "position": position}


# ── _normalize_query ──────────────────────────────────────────────────────────


def test_normalize_query_removes_accents():
    tokens = _normalize_query("harnais chien été")
    assert "ete" in tokens


def test_normalize_query_returns_set():
    assert isinstance(_normalize_query("chien chat"), set)


def test_normalize_query_filters_short_tokens():
    tokens = _normalize_query("un beau chien")
    assert "un" not in tokens  # 2 chars < min 3


# ── _saturation ───────────────────────────────────────────────────────────────


def test_saturation_low_for_top_10():
    assert _saturation(5.0) == "low"


def test_saturation_medium_for_position_11_to_20():
    assert _saturation(15.0) == "medium"


def test_saturation_high_for_position_above_20():
    assert _saturation(35.0) == "high"


def test_saturation_unknown_for_zero_position():
    assert _saturation(0.0) == "unknown"


# ── _opportunity_score ────────────────────────────────────────────────────────


def test_opportunity_score_high_when_poor_ranking_and_no_cluster():
    score = _opportunity_score(500, 30.0, has_cluster=False, max_impressions=500)
    assert score > 0.7


def test_opportunity_score_low_when_already_ranked():
    # position <= 10 → pos_score = 0; only impression score counts.
    # Top-3 queries are excluded at the analyze_keyword_gaps level, not here.
    score = _opportunity_score(500, 2.0, has_cluster=True, max_impressions=500)
    assert score <= 0.5  # impression score only (0.5 weight), no position or gap bonus


def test_opportunity_score_bounded_0_to_1():
    score = _opportunity_score(9999, 99.0, has_cluster=False, max_impressions=100)
    assert 0.0 <= score <= 1.0


def test_opportunity_score_content_gap_bonus_applied():
    score_with_cluster = _opportunity_score(200, 25.0, has_cluster=True, max_impressions=200)
    score_without_cluster = _opportunity_score(200, 25.0, has_cluster=False, max_impressions=200)
    assert score_without_cluster > score_with_cluster


# ── analyze_keyword_gaps ──────────────────────────────────────────────────────


def test_analyze_keyword_gaps_returns_keyword_gaps():
    queries = [_gsc_row("manteau chien imperméable", impressions=200, position=22)]
    gaps = analyze_keyword_gaps(queries, _CLUSTERS)
    assert all(isinstance(g, KeywordGap) for g in gaps)


def test_analyze_keyword_gaps_sorted_by_opportunity_score():
    queries = [
        _gsc_row("manteau chien imperméable", impressions=500, position=30),
        _gsc_row("fontaine eau ceramique", impressions=50, position=12),
    ]
    gaps = analyze_keyword_gaps(queries, _CLUSTERS)
    scores = [g.opportunity_score for g in gaps]
    assert scores == sorted(scores, reverse=True)


def test_analyze_keyword_gaps_excludes_top_3_queries():
    queries = [_gsc_row("pardessus chien", impressions=300, position=2.0)]
    gaps = analyze_keyword_gaps(queries, _CLUSTERS)
    assert len(gaps) == 0


def test_analyze_keyword_gaps_filters_low_impressions():
    queries = [_gsc_row("harnais chat", impressions=3, position=25)]
    gaps = analyze_keyword_gaps(queries, _CLUSTERS, min_impressions=10)
    assert len(gaps) == 0


def test_analyze_keyword_gaps_detects_content_gap():
    """A query with no cluster match is a content gap."""
    # Use a query with no tokens present anywhere in the catalog
    queries = [_gsc_row("aquarium poisson tropical", impressions=200, position=28)]
    gaps = analyze_keyword_gaps(queries, _CLUSTERS)
    content_gaps = [g for g in gaps if g.cluster_name is None]
    assert len(content_gaps) >= 1


def test_analyze_keyword_gaps_matches_cluster_for_known_category():
    queries = [_gsc_row("pardessus chien hiver imperméable", impressions=150, position=18)]
    gaps = analyze_keyword_gaps(queries, _CLUSTERS)
    matched = [g for g in gaps if g.cluster_name is not None]
    assert len(matched) >= 1


def test_analyze_keyword_gaps_empty_queries_returns_empty():
    assert analyze_keyword_gaps([], _CLUSTERS) == []


def test_analyze_keyword_gaps_empty_clusters_still_runs():
    queries = [_gsc_row("chien chat", impressions=100, position=20)]
    gaps = analyze_keyword_gaps(queries, [])
    assert len(gaps) == 1
    assert gaps[0].cluster_name is None


# ── engine integration ────────────────────────────────────────────────────────


def test_run_niche_analysis_returns_complete_report():
    from app.niche.engine import run_niche_analysis

    products = [
        {"id": "1", "title": "Pardessus chien", "product_type": "Vêtements chien", "tags": []},
        {"id": "2", "title": "Fontaine chat", "product_type": "Fontaines", "tags": []},
    ]
    queries = [
        _gsc_row("manteau chien imperméable", impressions=300, position=25),
        _gsc_row("fontaine eau silencieuse", impressions=80, position=14),
    ]
    report = run_niche_analysis(products, queries, shop="test.myshopify.com")
    assert report.shop == "test.myshopify.com"
    assert report.total_products == 2
    assert report.total_queries == 2
    assert len(report.clusters) >= 1
    assert report.generated_at  # non-empty ISO timestamp
