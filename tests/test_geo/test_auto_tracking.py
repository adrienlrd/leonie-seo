"""Tests for automatic GEO impact tracking on live applies."""

from __future__ import annotations

from pathlib import Path

from app.db import init_db
from app.geo.auto_tracking import record_applied_change
from app.geo.ledger import list_geo_events
from app.geo.optimization_snapshots import list_optimization_snapshots

SHOP = "store.myshopify.com"


def test_record_applied_change_creates_snapshot_and_event(tmp_path: Path) -> None:
    db = tmp_path / "tracking.db"
    init_db(db)

    event_id = record_applied_change(
        shop=SHOP,
        resource_type="product",
        resource_id="gid://shopify/Product/1",
        resource_title="Harnais",
        resource_handle="harnais",
        action_type="meta_title",
        field="meta_title",
        old_value="Harnais pour chien",
        new_value="Harnais pour chien confortable et résistant",
        db_path=db,
    )

    assert event_id is not None
    events = list_geo_events(SHOP, db_path=db)["events"]
    assert len(events) == 1
    assert events[0]["status"] == "applied"
    assert events[0]["event_type"] == "applied_optimization"
    assert events[0]["resource_id"] == "gid://shopify/Product/1"
    assert events[0]["action_type"] == "meta_title"
    assert events[0]["after_snapshot"]["field"] == "meta_title"
    assert events[0]["after_snapshot"]["value"] == "Harnais pour chien confortable et résistant"
    assert events[0]["before_snapshot"]["content"]["meta_title"] == "Harnais pour chien"

    snapshots = list_optimization_snapshots(SHOP, db_path=db)["snapshots"]
    assert len(snapshots) == 1
    assert snapshots[0]["resource_id"] == "gid://shopify/Product/1"
    assert snapshots[0]["action_type"] == "meta_title"
    assert events[0]["snapshot_id"] == snapshots[0]["id"]


def test_record_applied_change_is_idempotent_same_day(tmp_path: Path) -> None:
    db = tmp_path / "tracking.db"
    init_db(db)

    first = record_applied_change(
        shop=SHOP,
        resource_type="product",
        resource_id="gid://shopify/Product/1",
        resource_title="Harnais",
        action_type="meta_title",
        field="meta_title",
        old_value="Old title",
        new_value="New title",
        db_path=db,
    )
    second = record_applied_change(
        shop=SHOP,
        resource_type="product",
        resource_id="gid://shopify/Product/1",
        resource_title="Harnais",
        action_type="meta_title",
        field="meta_title",
        old_value="New title",
        new_value="Newer title",
        db_path=db,
    )

    assert first is not None
    assert second is None
    events = list_geo_events(SHOP, db_path=db)["events"]
    assert len(events) == 1


def test_record_applied_change_distinct_fields_create_separate_events(tmp_path: Path) -> None:
    db = tmp_path / "tracking.db"
    init_db(db)

    title_event = record_applied_change(
        shop=SHOP,
        resource_type="product",
        resource_id="gid://shopify/Product/1",
        resource_title="Harnais",
        action_type="meta_title",
        field="meta_title",
        old_value="Old title",
        new_value="New title",
        db_path=db,
    )
    description_event = record_applied_change(
        shop=SHOP,
        resource_type="product",
        resource_id="gid://shopify/Product/1",
        resource_title="Harnais",
        action_type="meta_description",
        field="meta_description",
        old_value="Old description",
        new_value="New description",
        db_path=db,
    )

    assert title_event is not None
    assert description_event is not None
    assert title_event != description_event
    events = list_geo_events(SHOP, db_path=db)["events"]
    assert len(events) == 2
