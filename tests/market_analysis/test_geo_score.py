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


def test_geo_score_field_deltas_are_non_negative_and_bounded() -> None:
    product = {"id": "1", "title": "Harnais", "handle": "harnais", "seo": {}, "images": [], "variants": []}
    llm_pack = {
        "proposed_meta_title": "Harnais Premium pour Chien de Berger Allemand robuste et ajustable",
        "proposed_meta_description": "Harnais confortable et ajustable pour chien, idéal promenade et dressage au quotidien sans tirer.",
        "proposed_product_description": "<p>"
        + ("Harnais premium nylon résistant rembourrage sangles réglables anneau renforcé. " * 8)
        + "</p>",
    }
    res = _build_product_result(product, {}, llm_pack, "shop.myshopify.com")
    deltas = res["geo_score_field_deltas"]

    assert set(deltas) == {"meta_title", "meta_description", "description"}
    # No field ever lowers the displayed score.
    assert all(v >= 0 for v in deltas.values())
    # Adding a meta description to a product that has none lifts readiness.
    assert deltas["meta_description"] > 0
    # Each single-field delta stays within the joint current→potential gap.
    gap = res["geo_score_potential"] - res["geo_score"]
    assert all(v <= gap for v in deltas.values())


def test_geo_score_field_deltas_zero_without_proposals() -> None:
    product = {"id": "1", "title": "Harnais", "handle": "harnais", "seo": {}, "images": [], "variants": []}
    res = _build_product_result(product, {}, {}, "shop.myshopify.com")
    assert res["geo_score_field_deltas"] == {"meta_title": 0, "meta_description": 0, "description": 0}


def test_geo_score_components_breakdown_attached() -> None:
    product = {"id": "1", "title": "Harnais", "handle": "harnais", "seo": {}, "images": [], "variants": []}
    res = _build_product_result(product, {}, {}, "shop.myshopify.com")
    comp = res["geo_score_components"]
    assert {"facts", "schema", "answerability", "trust", "seo", "commerce"} <= set(comp)
    # Each pillar exposes a 0-100 score and its weight.
    for pillar in comp.values():
        assert 0 <= pillar["score"] <= 100
        assert 0 < pillar["weight"] <= 1


def test_extra_fact_keys_raise_readiness_score() -> None:
    product = {"id": "1", "title": "Harnais", "handle": "harnais", "seo": {}, "images": [], "variants": []}
    base = score_product_readiness(product)["readiness_score"]
    # Simulating merchant having confirmed all trust + answerability facts via enrichment form
    extra = {"certifications", "origins", "warranty", "delivery", "returns", "targets", "properties"}
    enriched = score_product_readiness(product, extra_fact_keys=extra)["readiness_score"]
    assert enriched > base


def test_build_product_result_reflects_confirmed_facts_in_score() -> None:
    product = {"id": "1", "title": "Harnais", "handle": "harnais", "seo": {}, "images": [], "variants": []}
    bare_res = _build_product_result(product, {}, {}, "shop.myshopify.com")
    # Simulate merchant having confirmed trust facts via the enrichment form.
    # confirmed_facts with source != shopify_snapshot are treated as merchant answers.
    llm_pack_with_facts = {
        "confirmed_facts": [
            {"key": "origins", "label": "Origins", "value": "France", "source": "merchant"},
            {"key": "warranty", "label": "Warranty", "value": "2 ans", "source": "merchant"},
            {"key": "certifications", "label": "Certifications", "value": "Oeko-Tex", "source": "merchant"},
            {"key": "targets", "label": "Targets", "value": "chiens adultes", "source": "merchant"},
            {"key": "properties", "label": "Properties", "value": "lavable en machine", "source": "merchant"},
        ]
    }
    enriched_res = _build_product_result(product, {}, llm_pack_with_facts, "shop.myshopify.com")
    assert enriched_res["geo_score"] > bare_res["geo_score"]


def test_enrichment_questions_include_targets_and_trust_signals() -> None:
    from app.market_analysis.engine import _build_enrichment_questions

    keywords = [{"query": "manteau chien", "paa_questions": []}]
    # All 8 sensitive facts are missing.
    missing = [
        {"key": k}
        for k in ("materials", "origins", "certifications", "warranty", "care", "dimensions", "compatibility", "size_recommendation")
    ]
    questions = _build_enrichment_questions(keywords, missing, {})
    keys = {q["key"] for q in questions}
    # New score-boosting questions must always be present.
    assert "targets" in keys
    assert "properties" in keys
    assert "delivery" in keys
    assert "returns" in keys
