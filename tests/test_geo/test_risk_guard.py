"""Tests for GEO Risk Guard."""

from __future__ import annotations

from app.geo.risk_guard import assess_catalog_risk, assess_product_risk


def test_assess_product_risk_protects_high_visibility_ready_page() -> None:
    product = {
        "id": "gid://shopify/Product/1",
        "title": "Fontaine chat céramique",
        "handle": "fontaine-chat",
        "status": "ACTIVE",
        "seo": {
            "title": "Fontaine chat céramique silencieuse et lavable",
            "description": "Fontaine pour chat en céramique lavable, garantie et adaptée au quotidien.",
        },
        "description": (
            "Fontaine chat en céramique lavable, silencieuse, compatible avec un usage quotidien. "
            "Dimensions 20 cm, garantie 30 jours, livraison rapide, retours possibles, fabriqué en France."
        ),
        "images": {"edges": [{"node": {"url": "https://example.com/img.jpg"}}]},
        "variants": {"edges": [{"node": {"price": "69.90", "sku": "FON-001", "inventoryQuantity": 10}}]},
    }
    gsc = {
        "https://example.com/products/fontaine-chat": {
            "impressions": 1200,
            "clicks": 180,
            "ctr": 0.15,
            "position": 3.0,
        }
    }

    row = assess_product_risk(product, "example.com", gsc)

    assert row["guard_status"] == "protected"
    assert row["confirmation_required"] is True
    assert row["risk_score"] >= 75


def test_assess_product_risk_marks_low_signal_page_safe() -> None:
    product = {
        "id": "gid://shopify/Product/1",
        "title": "Bol chat",
        "handle": "bol-chat",
        "description": "",
    }

    row = assess_product_risk(product, "example.com", {})

    assert row["guard_status"] == "safe"
    assert row["confirmation_required"] is False


def test_assess_catalog_risk_returns_summary_counts() -> None:
    products = [
        {
            "id": "gid://shopify/Product/1",
            "title": "Top product",
            "handle": "top-product",
            "description": "Produit en coton lavable, dimensions 40 cm, garantie 30 jours.",
            "seo": {
                "title": "Top product coton lavable pour chat",
                "description": "Produit coton lavable avec garantie et livraison rapide pour chat.",
            },
            "images": {"edges": [{"node": {"url": "https://example.com/img.jpg"}}]},
            "variants": {"edges": [{"node": {"price": "50", "inventoryQuantity": 10}}]},
        },
        {"id": "gid://shopify/Product/2", "title": "Low product", "handle": "low-product", "description": ""},
    ]
    gsc = {
        "https://example.com/products/top-product": {
            "impressions": 1000,
            "clicks": 100,
            "ctr": 0.1,
            "position": 4.0,
        }
    }

    result = assess_catalog_risk(products, "example.com", gsc)

    assert result["total"] == 2
    assert result["summary"]["confirmation_required"] >= 1
    assert result["rows"][0]["risk_score"] >= result["rows"][1]["risk_score"]
