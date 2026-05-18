"""Tests for GEO optimization event tracking."""

from __future__ import annotations

from pathlib import Path

from app.db import init_db
from app.geo.event_tracking import (
    create_event_from_optimization_snapshot,
    mark_optimization_event_status,
)
from app.geo.ledger import list_geo_events
from app.geo.optimization_snapshots import create_optimization_snapshot

SHOP = "store.myshopify.com"


def _snapshot_data() -> dict:
    return {
        "shop": SHOP,
        "resource_type": "product",
        "resource_id": "gid://shopify/Product/1",
        "resource_title": "Harnais",
        "action_type": "enrich_product_facts",
        "source": "geo",
        "hypothesis": "Better factual coverage should improve AI answer eligibility.",
        "snapshot": {
            "resource_type": "product",
            "resource_id": "gid://shopify/Product/1",
            "resource_title": "Harnais",
            "scores": {"readiness_score": 64},
            "content": {"title": "Harnais"},
        },
        "metrics": {"gsc": {"clicks": 2, "impressions": 100, "ctr": 0.02, "position": 8.5}},
        "readiness_score": 64,
        "seo_score": 75,
        "content_hash": "abc123",
    }


def test_create_event_from_snapshot_links_baseline_data(tmp_path: Path) -> None:
    db = tmp_path / "tracking.db"
    init_db(db)
    snapshot_id = create_optimization_snapshot(
        shop=SHOP,
        snapshot_data=_snapshot_data(),
        notes="Before facts enrichment",
        db_path=db,
    )

    event_id = create_event_from_optimization_snapshot(
        shop=SHOP,
        snapshot_id=snapshot_id,
        status="applied",
        job_id="job-1",
        estimated_impact={"revenue_estimate": 18},
        db_path=db,
    )

    events = list_geo_events(SHOP, db_path=db)["events"]
    assert event_id == 1
    assert events[0]["snapshot_id"] == snapshot_id
    assert events[0]["event_type"] == "applied_optimization"
    assert events[0]["score_before"] == 64
    assert events[0]["measurement_status"] == "baseline_captured"
    assert events[0]["metrics_before"]["gsc"]["impressions"] == 100


def test_mark_optimization_event_status_appends_history(tmp_path: Path) -> None:
    db = tmp_path / "tracking.db"
    init_db(db)
    snapshot_id = create_optimization_snapshot(shop=SHOP, snapshot_data=_snapshot_data(), db_path=db)
    event_id = create_event_from_optimization_snapshot(shop=SHOP, snapshot_id=snapshot_id, db_path=db)

    updated = mark_optimization_event_status(
        shop=SHOP,
        event_id=event_id,
        status="measured",
        score_after=82,
        measurement_status="j30_measured",
        observed_impact={"revenue": 9},
        notes="J+30 review",
        db_path=db,
    )

    event = list_geo_events(SHOP, db_path=db)["events"][0]
    assert updated is True
    assert event["status"] == "measured"
    assert event["score_after"] == 82
    assert event["measurement_status"] == "j30_measured"
    assert event["observed_impact"]["revenue"] == 9
    assert [entry["status"] for entry in event["status_history"]] == ["planned", "measured"]
