"""Tests for GEO optimization snapshots."""

from __future__ import annotations

from app.db import init_db
from app.geo.optimization_snapshots import (
    build_optimization_snapshot,
    create_optimization_snapshot,
    list_optimization_snapshots,
)


def test_build_optimization_snapshot_captures_scores_content_and_metrics() -> None:
    snapshot = {
        "products": [
            {
                "id": "gid://shopify/Product/1",
                "title": "Harnais chien nylon",
                "handle": "harnais-chien",
                "description": "Harnais en nylon réglable, lavable, fabriqué en France. Garantie 30 jours.",
                "variants": {"edges": [{"node": {"price": "49.90", "inventoryQuantity": 7}}]},
            }
        ]
    }
    gsc_rows = {"https://example.com/products/harnais-chien": {"clicks": 12, "impressions": 300, "ctr": 0.04, "position": 9}}

    data = build_optimization_snapshot(
        shop="example.myshopify.com",
        snapshot=snapshot,
        resource_type="product",
        resource_id="gid://shopify/Product/1",
        action_type="add_answer_blocks",
        gsc_rows=gsc_rows,
        hypothesis="Answer blocks should improve long-tail clarity.",
    )

    assert data["readiness_score"] > 0
    assert data["seo_score"] > 0
    assert data["metrics"]["gsc"]["impressions"] == 300
    assert data["snapshot"]["facts"]["confirmed_count"] > 0
    assert data["content_hash"]


def test_create_and_list_optimization_snapshot_persists_payload(tmp_path) -> None:
    db = tmp_path / "snapshots.db"
    init_db(db)
    snapshot_data = {
        "resource_type": "product",
        "resource_id": "gid://shopify/Product/1",
        "resource_title": "Harnais",
        "action_type": "add_answer_blocks",
        "source": "geo",
        "hypothesis": "Improve answerability.",
        "snapshot": {"scores": {"readiness_score": 42}},
        "metrics": {"gsc": {"impressions": 100}},
        "readiness_score": 42,
        "seo_score": 50,
        "content_hash": "abc123",
    }

    snapshot_id = create_optimization_snapshot(
        shop="shop.myshopify.com",
        snapshot_data=snapshot_data,
        notes="Before optimization.",
        db_path=db,
    )
    data = list_optimization_snapshots("shop.myshopify.com", db_path=db)

    assert snapshot_id > 0
    assert data["total"] == 1
    assert data["snapshots"][0]["snapshot"]["scores"]["readiness_score"] == 42
    assert data["snapshots"][0]["metrics"]["gsc"]["impressions"] == 100
    assert data["snapshots"][0]["notes"] == "Before optimization."
