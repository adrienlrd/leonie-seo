"""Tests for GEO control group builder."""

from __future__ import annotations

from app.geo.control_groups import build_control_groups


def _product(product_id: str, title: str, handle: str, price: str, impressions: int) -> dict:
    return {
        "id": product_id,
        "title": title,
        "handle": handle,
        "productType": "Harnais",
        "tags": ["chien", "nylon"],
        "description": "Harnais nylon réglable confortable pour chien avec boucle solide.",
        "variants": {"edges": [{"node": {"price": price, "inventoryQuantity": 12}}]},
        "status": "ACTIVE",
        "_impressions": impressions,
    }


def test_build_control_groups_selects_similar_unmodified_pages() -> None:
    snapshot = {
        "products": [
            _product("p1", "Harnais noir", "harnais-noir", "49.90", 300),
            _product("p2", "Harnais rouge", "harnais-rouge", "52.00", 280),
            _product("p3", "Gamelle chat", "gamelle-chat", "18.00", 20),
        ],
        "collections": [],
    }
    events = [
        {
            "id": 1,
            "snapshot_id": 10,
            "resource_type": "product",
            "resource_id": "p1",
            "resource_title": "Harnais noir",
            "action_type": "enrich_product_facts",
            "status": "applied",
            "score_before": 60,
            "before_snapshot": {
                "path": "/products/harnais-noir",
                "content": {"handle": "harnais-noir"},
                "commerce": {"price": "49.90", "inventory_quantity": 12},
                "scores": {"readiness_score": 60},
            },
            "metrics_before": {"gsc": {"impressions": 300, "position": 8.0}},
        }
    ]
    gsc_rows = {
        "https://example.com/products/harnais-noir": {"impressions": 300, "position": 8.0},
        "https://example.com/products/harnais-rouge": {"impressions": 280, "position": 8.5},
        "https://example.com/products/gamelle-chat": {"impressions": 20, "position": 30.0},
    }

    result = build_control_groups(snapshot=snapshot, events=events, gsc_rows=gsc_rows)

    group = result["groups"][0]
    assert result["summary"]["groups_with_controls"] == 1
    assert group["target"]["resource_id"] == "p1"
    assert group["controls"][0]["resource_id"] == "p2"
    assert group["controls"][0]["quality"] == "strong"
    assert "same_category" in group["controls"][0]["match_reasons"]


def test_build_control_groups_excludes_already_optimized_pages() -> None:
    snapshot = {
        "products": [
            _product("p1", "Harnais noir", "harnais-noir", "49.90", 300),
            _product("p2", "Harnais rouge", "harnais-rouge", "52.00", 280),
        ],
        "collections": [],
    }
    events = [
        {
            "id": 1,
            "snapshot_id": 10,
            "resource_type": "product",
            "resource_id": "p1",
            "resource_title": "Harnais noir",
            "action_type": "enrich_product_facts",
            "status": "applied",
            "score_before": 60,
            "before_snapshot": {"path": "/products/harnais-noir", "scores": {"readiness_score": 60}},
            "metrics_before": {"gsc": {"impressions": 300, "position": 8.0}},
        },
        {
            "id": 2,
            "resource_type": "product",
            "resource_id": "p2",
            "resource_title": "Harnais rouge",
            "action_type": "add_answer_blocks",
            "status": "measured",
            "before_snapshot": {},
            "metrics_before": {},
        },
    ]

    result = build_control_groups(snapshot=snapshot, events=events)

    assert result["groups"][0]["controls"] == []
    assert result["groups"][0]["quality"] == "missing"
    assert result["groups"][0]["warnings"]
