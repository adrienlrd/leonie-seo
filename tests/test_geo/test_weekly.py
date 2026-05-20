"""Tests for weekly GEO action assistant."""

from __future__ import annotations

from app.geo.weekly import build_weekly_actions


def test_build_weekly_actions_returns_three_actions_when_candidates_exist() -> None:
    products = [
        {
            "id": f"gid://shopify/Product/{idx}",
            "title": f"Produit {idx}",
            "handle": f"produit-{idx}",
            "description": "",
            "seo": {"title": "", "description": ""},
            "variants": {"edges": [{"node": {"price": "50.0", "inventoryQuantity": 5}}]},
        }
        for idx in range(1, 5)
    ]
    gsc = {
        f"https://example.com/products/produit-{idx}": {
            "impressions": 1000 - idx * 100,
            "clicks": 10,
            "ctr": 0.01,
            "position": 12.0,
        }
        for idx in range(1, 5)
    }

    result = build_weekly_actions(products, "example.com", gsc)

    assert result["summary"]["weekly_actions"] == 3
    assert len(result["actions"]) == 3
    assert result["actions"][0]["weekly_message"]
    assert result["actions"][0]["next_steps"]


def test_build_weekly_actions_respects_limit() -> None:
    products = [
        {"id": "1", "title": "A", "handle": "a", "description": ""},
        {"id": "2", "title": "B", "handle": "b", "description": ""},
    ]

    result = build_weekly_actions(products, "example.com", {}, limit=1)

    assert result["summary"]["weekly_actions"] == 1
    assert len(result["actions"]) == 1


def test_build_weekly_actions_filters_drafts_when_scope_is_active() -> None:
    products = [
        {
            "id": "1",
            "title": "Active",
            "handle": "active",
            "status": "ACTIVE",
            "onlineStoreUrl": "https://example.com/products/active",
            "description": "",
        },
        {
            "id": "2",
            "title": "Draft",
            "handle": "draft",
            "status": "DRAFT",
            "onlineStoreUrl": None,
            "description": "",
        },
    ]

    result = build_weekly_actions(products, "example.com", {}, limit=3)

    assert result["total_candidates"] == 1
    assert result["scope"]["counts"]["draft"] == 1
    assert result["actions"][0]["handle"] == "active"
