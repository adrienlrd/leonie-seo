"""Tests for app.niche.engine — the niche-first orchestrator.

Covers the lot 4 wave 2 wiring that adds GSC intent clusters and aggregate
NER entity counts to the NicheReport, so the engine actually delivers the
"niche-first concret" differentiator promised in CLAUDE.md rule 14 instead
of returning only product clusters + keyword gaps.
"""

from __future__ import annotations

from app.niche.engine import run_niche_analysis


def _products() -> list[dict]:
    return [
        {
            "id": "1",
            "title": "Pardessus pour chien fabriqué en France",
            "product_type": "Vêtements chien",
            "body_html": "Manteau en laine mérinos imperméable, taille réglable, made in France.",
        },
        {
            "id": "2",
            "title": "Harnais chien cuir naturel",
            "product_type": "Vêtements chien",
            "body_html": "Harnais en cuir véritable pour chien moyen, fabriqué artisanalement en France.",
        },
        {
            "id": "3",
            "title": "Fontaine eau chat inox",
            "product_type": "Abreuvoir chat",
            "body_html": "Fontaine en inox filtrante, lavable au lave-vaisselle.",
        },
    ]


def _gsc() -> list[dict]:
    return [
        {"query": "acheter harnais chien", "impressions": 1200, "clicks": 30, "position": 8.0},
        {
            "query": "comment choisir harnais chien",
            "impressions": 800,
            "clicks": 12,
            "position": 14.0,
        },
        {"query": "harnais chien pas cher", "impressions": 600, "clicks": 18, "position": 6.0},
        {"query": "leoniedelacroix harnais", "impressions": 400, "clicks": 35, "position": 1.2},
        # Below the impressions threshold — must be filtered
        {"query": "rare query", "impressions": 2, "clicks": 0, "position": 95.0},
    ]


def test_run_niche_analysis_returns_full_report():
    report = run_niche_analysis(_products(), _gsc(), shop="store.myshopify.com")
    assert report.shop == "store.myshopify.com"
    assert report.total_products == 3
    assert report.total_queries == 5
    assert report.generated_at  # ISO timestamp


def test_run_niche_analysis_includes_product_clusters():
    report = run_niche_analysis(_products(), _gsc(), shop="store.myshopify.com")
    assert len(report.clusters) >= 1


def test_run_niche_analysis_includes_keyword_gaps():
    report = run_niche_analysis(_products(), _gsc(), shop="store.myshopify.com")
    assert isinstance(report.keyword_gaps, list)


def test_run_niche_analysis_now_wires_intent_clusters():
    """Lot 4 wave 2: GSC queries must be clustered by search intent and
    surfaced on the report (was previously empty / not wired)."""
    report = run_niche_analysis(_products(), _gsc(), shop="store.myshopify.com")
    assert len(report.intent_clusters) >= 1
    # Every cluster has an intent label
    for cluster in report.intent_clusters:
        assert cluster.intent is not None


def test_run_niche_analysis_now_wires_entity_summary():
    """Lot 4 wave 2: NER entities must be aggregated across the catalogue."""
    report = run_niche_analysis(_products(), _gsc(), shop="store.myshopify.com")
    # Origin "france" appears in 2 products
    assert "origins" in report.entity_summary
    origins_lower = {k.lower(): v for k, v in report.entity_summary["origins"].items()}
    assert any("france" in key for key in origins_lower)


def test_run_niche_analysis_intent_threshold_filters_low_impressions():
    """min_impressions must apply to both keyword gaps AND intent clusters."""
    report = run_niche_analysis(_products(), _gsc(), shop="s", min_impressions=500)
    # 3 queries above 500 impressions: 1200, 800, 600
    for cluster in report.intent_clusters:
        assert cluster.total_impressions >= 500


def test_run_niche_analysis_handles_empty_inputs():
    """Engine must not crash when products or queries are empty."""
    report = run_niche_analysis([], [], shop="empty.myshopify.com")
    assert report.total_products == 0
    assert report.total_queries == 0
    assert report.clusters == []
    assert report.keyword_gaps == []
    assert report.intent_clusters == []
    assert report.entity_summary == {}
