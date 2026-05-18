"""Tests for revenue-aware GEO prioritization."""

from __future__ import annotations

from app.geo.prioritization import prioritize_catalog, prioritize_product


def test_prioritize_product_combines_readiness_gap_and_gsc_revenue_estimate() -> None:
    product = {
        "id": "gid://shopify/Product/1",
        "title": "Harnais chien",
        "handle": "harnais-chien",
        "description": "",
        "seo": {"title": "", "description": ""},
        "variants": {"edges": [{"node": {"price": "80.0", "inventoryQuantity": 8}}]},
    }
    gsc = {
        "https://example.com/products/harnais-chien": {
            "impressions": 1000,
            "clicks": 20,
            "ctr": 0.02,
            "position": 12.0,
        }
    }

    row = prioritize_product(product, "example.com", gsc, conversion_rate=0.05, average_order_value=50)

    assert row["priority_score"] > 0
    assert row["revenue_estimate"] > 0
    assert row["confidence"] == "high"
    assert row["action_type"]


def test_prioritize_product_uses_average_order_value_when_price_missing() -> None:
    product = {
        "id": "gid://shopify/Product/1",
        "title": "Bol chat",
        "handle": "bol-chat",
        "description": "",
    }
    gsc = {
        "https://example.com/products/bol-chat": {
            "impressions": 500,
            "clicks": 5,
            "ctr": 0.01,
            "position": 15.0,
        }
    }

    row = prioritize_product(product, "example.com", gsc, conversion_rate=0.02, average_order_value=100)

    assert row["price"] is None
    assert row["revenue_estimate"] > 0
    assert row["confidence"] == "medium"


def test_prioritize_catalog_sorts_highest_priority_first() -> None:
    products = [
        {
            "id": "gid://shopify/Product/1",
            "title": "Low traffic",
            "handle": "low-traffic",
            "description": "",
        },
        {
            "id": "gid://shopify/Product/2",
            "title": "High traffic",
            "handle": "high-traffic",
            "description": "",
        },
    ]
    gsc = {
        "https://example.com/products/low-traffic": {"impressions": 10, "clicks": 1, "ctr": 0.1, "position": 8.0},
        "https://example.com/products/high-traffic": {"impressions": 2000, "clicks": 20, "ctr": 0.01, "position": 12.0},
    }

    result = prioritize_catalog(products, "example.com", gsc)

    assert result["total"] == 2
    assert result["rows"][0]["handle"] == "high-traffic"
    assert result["summary"]["gsc_connected"] is True
