"""Tests for synthetic learning control groups."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.db import init_db
from app.db_adapter import get_conn
from app.learning.control_group import build_control_metrics_for_event

SHOP = "store.myshopify.com"
TARGET_ID = "gid://shopify/Product/1"


def _event(*, age_days: int = 28) -> dict:
    applied_at = (datetime.now(UTC) - timedelta(days=age_days)).isoformat()
    return {
        "id": 1,
        "status": "applied",
        "resource_type": "product",
        "resource_id": TARGET_ID,
        "action_type": "meta_title",
        "status_history": [{"status": "applied", "changed_at": applied_at}],
    }


def _product(
    product_id: str,
    *,
    before_impressions: int | None = None,
    after_impressions: int | None = None,
) -> dict:
    product = {
        "product_id": product_id,
        "product_title": f"Product {product_id}",
        "product_type": "Harnais",
        "target_customer": "Chien sensible",
        "opportunity_score": 70,
        "seo_keywords": [
            {
                "query": "harnais chien",
                "target_role": "primary",
                "data_source": "gsc",
                "gsc_impressions": 1000,
                "gsc_clicks": 50,
                "gsc_position": 8,
            }
        ],
        "collections": [{"title": "Harnais"}],
    }
    if before_impressions is not None and after_impressions is not None:
        product["learning_metrics"] = {
            "J+28": {
                "before": {
                    "gsc": {
                        "impressions": before_impressions,
                        "clicks": before_impressions // 10,
                        "position": 8,
                    }
                },
                "after": {
                    "gsc": {
                        "impressions": after_impressions,
                        "clicks": after_impressions // 10,
                        "position": 7,
                    }
                },
            }
        }
    return product


def test_build_control_metrics_uses_similar_unmodified_products(tmp_path: Path) -> None:
    db = tmp_path / "history.db"
    init_db(db)
    applied_at = (datetime.now(UTC) - timedelta(days=10)).isoformat()
    with get_conn(db) as conn:
        conn.execute(
            """INSERT INTO seo_changes
               (shop, applied_at, resource_type, resource_id, field, old_value, new_value, status)
               VALUES (?, ?, 'product', ?, 'seo.title', 'Old', 'New', 'applied')""",
            (SHOP, applied_at, "gid://shopify/Product/5"),
        )
    products = {
        TARGET_ID: _product(TARGET_ID),
        "gid://shopify/Product/2": _product(
            "gid://shopify/Product/2", before_impressions=100, after_impressions=110
        ),
        "gid://shopify/Product/3": _product(
            "gid://shopify/Product/3", before_impressions=200, after_impressions=220
        ),
        "gid://shopify/Product/4": _product(
            "gid://shopify/Product/4", before_impressions=300, after_impressions=330
        ),
        "gid://shopify/Product/5": _product(
            "gid://shopify/Product/5", before_impressions=900, after_impressions=1800
        ),
        "gid://shopify/Product/6": _product("gid://shopify/Product/6"),
    }

    metrics = build_control_metrics_for_event(
        shop=SHOP,
        event=_event(age_days=28),
        products=products,
        events=[],
        window_days=28,
        db_path=db,
    )

    assert metrics["control_size"] == 3
    assert metrics["control_quality"] == "fair"
    assert metrics["impressions_before"] == 200
    assert metrics["impressions_after"] == 220
    assert "gid://shopify/Product/5" not in metrics["control_product_ids"]
    assert metrics["candidates_excluded_modified"] == 1
    assert metrics["candidates_missing_metrics"] == 1


def test_build_control_metrics_returns_empty_when_too_few_controls(tmp_path: Path) -> None:
    db = tmp_path / "history.db"
    init_db(db)
    products = {
        TARGET_ID: _product(TARGET_ID),
        "gid://shopify/Product/2": _product(
            "gid://shopify/Product/2", before_impressions=100, after_impressions=110
        ),
    }

    metrics = build_control_metrics_for_event(
        shop=SHOP,
        event=_event(age_days=28),
        products=products,
        events=[],
        window_days=28,
        db_path=db,
    )

    assert metrics == {}
