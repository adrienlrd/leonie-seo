"""Tests for product facts extraction."""

from __future__ import annotations

from app.geo.facts import analyze_catalog_facts, analyze_product_facts


def test_analyze_product_facts_extracts_confirmed_entities_when_description_contains_them() -> None:
    product = {
        "id": "gid://shopify/Product/1",
        "title": "Harnais chien imperméable",
        "handle": "harnais-chien",
        "description": "Harnais en nylon réglable, lavable et fabriqué en France. Garantie 30 jours.",
        "variants": {"edges": [{"node": {"price": "49.90"}}]},
    }

    result = analyze_product_facts(product)
    keys = {fact["key"] for fact in result["confirmed_facts"]}

    assert "materials" in keys
    assert "origins" in keys
    assert "properties" in keys
    assert "warranty" in keys
    assert "price" in keys
    assert result["completeness_score"] > 0.35


def test_analyze_product_facts_marks_sensitive_missing_facts_when_absent() -> None:
    product = {
        "id": "gid://shopify/Product/1",
        "title": "Bol chat",
        "handle": "bol-chat",
        "description": "Un joli bol pour chat.",
    }

    result = analyze_product_facts(product)
    missing_keys = {fact["key"] for fact in result["missing_facts"]}

    assert "materials" in missing_keys
    assert "origins" in missing_keys
    assert "certifications" in missing_keys
    assert result["suggestions_to_verify"]


def test_analyze_catalog_facts_sorts_low_completeness_first() -> None:
    products = [
        {
            "id": "gid://shopify/Product/1",
            "title": "Produit complet",
            "handle": "produit-complet",
            "description": "Produit en coton lavable fabriqué en France avec garantie et dimensions 40 cm.",
        },
        {
            "id": "gid://shopify/Product/2",
            "title": "Produit pauvre",
            "handle": "produit-pauvre",
            "description": "",
        },
    ]

    result = analyze_catalog_facts(products)

    assert result["total"] == 2
    assert result["products"][0]["handle"] == "produit-pauvre"
    assert result["summary"]["avg_completeness_score"] >= 0
