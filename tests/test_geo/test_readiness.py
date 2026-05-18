"""Tests for AI Search readiness scoring."""

from __future__ import annotations

from app.geo.readiness import score_catalog_readiness, score_product_readiness


def test_score_product_readiness_returns_components_and_recommendations() -> None:
    product = {
        "id": "gid://shopify/Product/1",
        "title": "Harnais chien nylon réglable",
        "handle": "harnais-chien",
        "status": "ACTIVE",
        "seo": {
            "title": "Harnais chien nylon réglable pour promenade",
            "description": "Harnais chien réglable, lavable et confortable pour promenade quotidienne.",
        },
        "description": (
            "Harnais en nylon réglable, lavable et confortable. Fabriqué en France, "
            "compatible petit chien et grand chien. Garantie 30 jours avec livraison rapide."
        ),
        "images": {"edges": [{"node": {"url": "https://example.com/img.jpg"}}]},
        "variants": {"edges": [{"node": {"price": "49.90", "sku": "HAR-001"}}]},
    }

    result = score_product_readiness(product)

    assert 0 <= result["readiness_score"] <= 100
    assert result["components"]["facts"] > 0
    assert result["components"]["schema"] > 0
    assert result["level"] in {"ready", "partial", "weak"}
    assert isinstance(result["recommendations"], list)


def test_score_product_readiness_weak_product_scores_lower() -> None:
    weak = {
        "id": "gid://shopify/Product/1",
        "title": "Bol",
        "handle": "bol",
        "description": "",
        "seo": {"title": "", "description": ""},
    }
    strong = {
        "id": "gid://shopify/Product/2",
        "title": "Fontaine chat céramique",
        "handle": "fontaine-chat",
        "status": "ACTIVE",
        "seo": {
            "title": "Fontaine chat céramique silencieuse et lavable",
            "description": "Fontaine pour chat en céramique lavable, garantie et adaptée au quotidien.",
        },
        "description": (
            "Fontaine chat en céramique lavable, silencieuse et compatible avec un usage quotidien. "
            "Dimensions 20 cm, garantie 30 jours, livraison rapide et retours possibles."
        ),
        "images": {"edges": [{"node": {"url": "https://example.com/img.jpg"}}]},
        "variants": {"edges": [{"node": {"price": "69.90", "sku": "FON-001"}}]},
    }

    assert score_product_readiness(weak)["readiness_score"] < score_product_readiness(strong)["readiness_score"]


def test_score_catalog_readiness_sorts_lowest_first() -> None:
    products = [
        {
            "id": "gid://shopify/Product/1",
            "title": "Produit fort",
            "handle": "produit-fort",
            "description": "Produit en coton lavable, dimensions 40 cm, garantie 30 jours.",
            "images": {"edges": [{"node": {"url": "https://example.com/img.jpg"}}]},
            "variants": {"edges": [{"node": {"price": "39.90"}}]},
        },
        {
            "id": "gid://shopify/Product/2",
            "title": "Produit faible",
            "handle": "produit-faible",
            "description": "",
        },
    ]

    result = score_catalog_readiness(products)

    assert result["total"] == 2
    assert result["products"][0]["handle"] == "produit-faible"
    assert "avg_readiness_score" in result["summary"]
