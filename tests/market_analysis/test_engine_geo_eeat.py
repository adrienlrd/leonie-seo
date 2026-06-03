"""Integration tests for Chantier A wiring (JSON-LD + GEO fields + E-E-A-T)."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from app.market_analysis import engine

_SHOP = "boutique.myshopify.com"

_PASS1_JSON = json.dumps(
    {
        "product_summary": "Croquettes chien sans céréales premium.",
        "target_customer": "Propriétaires de chiens adultes.",
        "buying_intents": ["alimentation premium"],
        "seo_keywords": [
            {
                "query": "croquettes chien sans cereales",
                "intent_type": "commercial",
                "demand_score": 70,
                "competition_score": 40,
                "product_fit_score": 95,
                "reason": "produit principal",
            }
        ],
        "geo_questions": [],
    }
)

_PASS2_JSON = json.dumps(
    {
        "proposed_meta_title": "Croquettes chien sans céréales — Ecocert",
        "proposed_meta_description": "Croquettes premium pour chien, certifiées Ecocert et fabriquées en France.",
        "proposed_product_title_if_different": "Croquettes chien sans céréales",
        "proposed_product_description": "Nos croquettes chien sans céréales fournissent des protéines de qualité.",
        "proposed_faq": [
            {"q": "Comment doser ?", "a": "Référez-vous au tableau de poids."},
            {"q": "Sont-elles sans céréales ?", "a": "Oui, formule 100% sans céréales."},
        ],
        "proposed_geo_answer_block": "Les croquettes chien sans céréales offrent une alimentation premium.",
        "proposed_geo_definition_block": "Croquettes chien est un aliment complet sans céréales certifié Ecocert.",
        "proposed_geo_quick_facts": [
            "Certifiées Ecocert",
            "Fabriquées en France",
            "Sans céréales",
        ],
        "proposed_geo_comparison_table": [
            {"critère": "Origine", "valeur": "France"},
            {"critère": "Certification", "valeur": "Ecocert"},
            {"critère": "Composition", "valeur": "Sans céréales"},
        ],
        "proposed_blog_title": "",
        "proposed_blog_outline": [],
        "proposed_blog_intro": "",
        "recommended_content_actions": [],
        "facts_used": ["certifications", "origins"],
        "facts_missing": [],
        "claims_used": [
            {"claim": "certifiées Ecocert", "fact_keys": ["certifications"]},
            {"claim": "fabriquées en France", "fact_keys": ["origins"]},
        ],
        "confidence": "high",
    }
)


class _FakeDataForSEO:
    available = True

    def enrich(self, signals, *, shop):  # noqa: ARG002
        for sig in signals:
            sig["source"] = "dataforseo"
            sig["search_volume"] = 800
            sig["difficulty_score"] = 30
            sig["difficulty_source"] = "dataforseo"
        return signals

    def fetch_serp_intelligence(self, keywords):  # noqa: ARG002
        return {}

    def fetch_serp_competitors(self, keywords):  # noqa: ARG002
        return []

    def fetch_keyword_ideas(self, seeds, *, limit=15):  # noqa: ARG002
        return []

    def fetch_domain_competitors(self, domain, *, limit=20):  # noqa: ARG002
        return []


def _product() -> dict:
    return {
        "id": "gid://shopify/Product/42",
        "title": "Croquettes chien sans céréales",
        "handle": "croquettes-chien-sans-cereales",
        "status": "ACTIVE",
        "body_html": "<p>Aliment complet pour chien adulte.</p>",
        "seo": {"title": "Croquettes chien sans céréales", "description": ""},
        "variants": [{"price": "39.90", "inventory_quantity": 8}],
        "vendor": "Léonie",
        "images": [{"src": "https://cdn.shopify.com/img.jpg"}],
    }


def _merchant_facts() -> dict:
    return {
        "gid://shopify/Product/42": {
            "certifications": "Ecocert",
            "origins": "Fabriqué en France",
        }
    }


def _router(*texts):
    from app.llm.provider import CompletionResult  # noqa: PLC0415

    router = MagicMock()
    router.complete.side_effect = [
        CompletionResult(text=t, provider="openai", model="gpt-4o-mini") for t in texts
    ]
    return router


def _run(router):
    budget = {
        "over_budget": False,
        "budget_usd": 20.0,
        "spent_usd": 0.0,
        "remaining_usd": 20.0,
        "usage_pct": 0.0,
        "alert": None,
    }
    with (
        patch.object(engine, "get_router", return_value=router),
        patch.object(engine, "check_budget", return_value=budget),
        patch.object(engine, "_fetch_trends_once", return_value=[]),
        patch.object(engine, "fetch_suggestions_bulk", return_value=[]),
        patch.object(engine, "DataForSEOProvider", return_value=_FakeDataForSEO()),
    ):
        return engine.run_market_analysis(
            [_product()],
            _SHOP,
            {},
            [],
            merchant_facts_by_product=_merchant_facts(),
        )


def test_product_schema_jsonld_is_built_from_confirmed_facts():
    router = _router(_PASS1_JSON, _PASS2_JSON)
    result = _run(router)
    pack = result["products"][0]["content_test_pack"]

    schema = pack["proposed_schema_jsonld"]
    product_schema = schema["product"]
    assert product_schema["@type"] == "Product"
    assert product_schema["name"] == "Croquettes chien sans céréales"
    assert product_schema["offers"]["price"] == "39.90"
    # `materials` was not provided → omitted (no hallucinated structured data).
    assert "material" not in product_schema
    assert product_schema["countryOfOrigin"] == "Fabriqué en France"


def test_jsonld_failure_does_not_block_product_analysis():
    """Schema generation is diagnostic and must never block analysis completion."""
    router = _router(_PASS1_JSON, _PASS2_JSON)
    with patch(
        "app.market_analysis.schema_builder.build_product_schema",
        side_effect=ValueError("bad snapshot"),
    ):
        result = _run(router)

    pack = result["products"][0]["content_test_pack"]
    assert pack["proposed_schema_jsonld"] == {}
    assert pack["proposed_meta_title"]


def test_faq_schema_jsonld_is_built_from_proposed_faq():
    router = _router(_PASS1_JSON, _PASS2_JSON)
    result = _run(router)
    pack = result["products"][0]["content_test_pack"]

    faq_schema = pack["proposed_schema_jsonld"]["faq"]
    assert faq_schema["@type"] == "FAQPage"
    assert len(faq_schema["mainEntity"]) == 2


def test_product_schema_jsonld_supports_shopify_edge_shapes():
    from app.market_analysis.schema_builder import build_product_schema

    schema = build_product_schema(
        product={
            "title": "Harnais chien",
            "handle": "harnais-chien",
            "vendor": "Léonie",
            "images": {"edges": [{"node": {"url": "https://cdn.test/harnais.jpg"}}]},
            "variants": {"edges": [{"node": {"price": "88.00", "inventoryQuantity": 3}}]},
        },
        confirmed_facts=[
            {"key": "materials", "value": ["cuir"], "confidence": "confirmed"},
        ],
        shop="example.com",
        meta_description="Harnais confortable pour chien.",
    )

    assert schema["offers"]["price"] == "88.00"
    assert schema["image"] == ["https://cdn.test/harnais.jpg"]
    assert schema["material"] == "cuir"


def test_geo_blocks_are_emitted_in_content_pack():
    router = _router(_PASS1_JSON, _PASS2_JSON)
    result = _run(router)
    pack = result["products"][0]["content_test_pack"]

    assert pack["proposed_geo_definition_block"].startswith("Croquettes chien")
    assert len(pack["proposed_geo_quick_facts"]) == 3
    assert len(pack["proposed_geo_comparison_table"]) == 3
    first_row = pack["proposed_geo_comparison_table"][0]
    assert "critère" in first_row
    assert "valeur" in first_row


def test_eeat_signals_are_emitted_when_certifications_confirmed():
    router = _router(_PASS1_JSON, _PASS2_JSON)
    result = _run(router)
    pack = result["products"][0]["content_test_pack"]

    eeat_signals = pack["eeat_signals"]
    kinds = {s["kind"] for s in eeat_signals}
    assert "certification" in kinds
    assert "origin" in kinds
