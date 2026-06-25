"""Tests for the per-product GEO score (current + potential) on analysis results."""

from __future__ import annotations

from app.geo.readiness import score_product_readiness
from app.market_analysis.engine import _build_product_result


def test_readiness_higher_for_enriched_product() -> None:
    bare = {"id": "1", "title": "Harnais", "handle": "harnais", "seo": {}, "images": [], "variants": []}
    enriched = {
        "id": "1",
        "title": "Harnais Premium pour Chien",
        "handle": "harnais",
        "seo": {
            "title": "Harnais Premium pour Chien de Berger Allemand robuste",
            "description": "Harnais confortable et ajustable pour chien, idéal promenade et dressage au quotidien.",
        },
        "body_html": "<p>" + ("Harnais en nylon résistant, rembourrage doux, sangles réglables. " * 8) + "</p>",
        "images": [{"src": "x"}],
        "variants": [{"price": "29.90", "sku": "HRN-1"}],
    }
    assert (
        score_product_readiness(enriched)["readiness_score"]
        > score_product_readiness(bare)["readiness_score"]
    )


def test_build_product_result_attaches_geo_scores() -> None:
    product = {"id": "1", "title": "Harnais", "handle": "harnais", "seo": {}, "images": [], "variants": []}
    llm_pack = {
        "proposed_meta_title": "Harnais Premium pour Chien de Berger Allemand robuste",
        "proposed_meta_description": "Harnais confortable et ajustable pour chien, idéal promenade et dressage sans tirer.",
        "proposed_product_description": "<p>"
        + ("Harnais premium en nylon résistant, rembourrage doux, sangles réglables. " * 8)
        + "</p>",
    }
    res = _build_product_result(product, {}, llm_pack, "shop.myshopify.com")

    assert "geo_score" in res
    assert "geo_score_potential" in res
    assert 0 <= res["geo_score"] <= 100
    # Applying the proposed meta/description/body can only raise (or hold) readiness.
    assert res["geo_score"] <= res["geo_score_potential"]


def test_geo_score_potential_rises_with_text_proposals() -> None:
    product = {"id": "1", "title": "Harnais", "handle": "harnais", "seo": {}, "images": [], "variants": []}
    # No proposals → potential equals current (nothing to apply).
    res_none = _build_product_result(product, {}, {}, "shop.myshopify.com")
    assert res_none["geo_score_potential"] == res_none["geo_score"]

    # With strong meta + description proposals → potential strictly above current.
    llm_pack = {
        "proposed_meta_title": "Harnais Premium pour Chien de Berger Allemand robuste et ajustable",
        "proposed_meta_description": "Harnais confortable et ajustable pour chien, idéal promenade et dressage au quotidien sans tirer.",
        "proposed_product_description": "<p>" + ("Harnais premium nylon résistant rembourrage sangles réglables anneau renforcé. " * 8) + "</p>",
    }
    res = _build_product_result(product, {}, llm_pack, "shop.myshopify.com")
    assert res["geo_score_potential"] > res["geo_score"]
