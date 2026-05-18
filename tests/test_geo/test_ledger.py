"""Tests for GEO impact ledger storage."""

from __future__ import annotations

from pathlib import Path

from app.db import init_db
from app.geo.ledger import create_geo_event, list_geo_events, summarize_geo_events

SHOP = "store.myshopify.com"


def test_create_geo_event_persists_json_payloads(tmp_path: Path) -> None:
    db = tmp_path / "ledger.db"
    init_db(db)

    event_id = create_geo_event(
        shop=SHOP,
        event_type="planned_optimization",
        resource_type="product",
        resource_id="gid://shopify/Product/1",
        resource_title="Harnais",
        action_type="enrich_product_facts",
        before_snapshot={"readiness_score": 42},
        metrics_before={"impressions": 100},
        estimated_impact={"revenue_estimate": 12.5},
        db_path=db,
    )

    data = list_geo_events(SHOP, db_path=db)

    assert event_id == 1
    assert data["total"] == 1
    assert data["events"][0]["before_snapshot"]["readiness_score"] == 42
    assert data["events"][0]["estimated_impact"]["revenue_estimate"] == 12.5


def test_list_geo_events_filters_by_shop_and_status(tmp_path: Path) -> None:
    db = tmp_path / "ledger.db"
    init_db(db)
    for shop, status in [(SHOP, "planned"), (SHOP, "measured"), ("other.myshopify.com", "planned")]:
        create_geo_event(
            shop=shop,
            event_type="planned_optimization",
            resource_type="product",
            resource_id=f"{shop}:1",
            resource_title="Product",
            action_type="improve_seo_copy",
            status=status,
            before_snapshot={},
            metrics_before={},
            estimated_impact={},
            db_path=db,
        )

    data = list_geo_events(SHOP, status="planned", db_path=db)

    assert data["total"] == 1
    assert data["events"][0]["shop"] == SHOP
    assert data["events"][0]["status"] == "planned"


def test_summarize_geo_events_totals_estimated_and_observed_revenue(tmp_path: Path) -> None:
    db = tmp_path / "ledger.db"
    init_db(db)
    create_geo_event(
        shop=SHOP,
        event_type="applied_optimization",
        resource_type="product",
        resource_id="1",
        resource_title="A",
        action_type="add_answer_blocks",
        status="applied",
        before_snapshot={},
        metrics_before={},
        estimated_impact={"revenue_estimate": 10},
        observed_impact={"revenue": 4},
        db_path=db,
    )
    create_geo_event(
        shop=SHOP,
        event_type="planned_optimization",
        resource_type="product",
        resource_id="2",
        resource_title="B",
        action_type="improve_schema",
        status="planned",
        before_snapshot={},
        metrics_before={},
        estimated_impact={"revenue_estimate": 20},
        db_path=db,
    )

    summary = summarize_geo_events(SHOP, db_path=db)

    assert summary["total_events"] == 2
    assert summary["by_status"] == {"applied": 1, "planned": 1}
    assert summary["estimated_revenue"] == 30
    assert summary["observed_revenue"] == 4
