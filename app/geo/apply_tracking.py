"""Helpers that turn successful live Shopify writes into GEO measurement events."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.api.snapshot_store import load_snapshot_from_file_or_db
from app.db_adapter import DB_PATH, get_conn
from app.geo.ledger import create_geo_event
from app.geo.optimization_snapshots import build_optimization_snapshot, create_optimization_snapshot
from app.paths import data_dir


def _already_recorded(shop: str, resource_id: str, field: str, applied_day: str) -> bool:
    with get_conn(DB_PATH) as conn:
        row = conn.execute(
            """
            SELECT id FROM geo_impact_events
            WHERE shop = ? AND resource_id = ? AND action_type = ? AND date(created_at) = ?
            LIMIT 1
            """,
            (shop, resource_id, field, applied_day),
        ).fetchone()
    return row is not None


def _minimal_snapshot(
    *,
    shop: str,
    resource_type: str,
    resource_id: str,
    resource_title: str,
    field: str,
    old_value: Any,
    new_value: Any,
) -> dict[str, Any]:
    return {
        "shop": shop,
        "resource_type": resource_type,
        "resource_id": resource_id,
        "resource_title": resource_title,
        "field": field,
        "old_value": old_value,
        "new_value": new_value,
        "captured_at": datetime.now(UTC).isoformat(),
    }


def record_live_apply_impact(
    *,
    shop: str,
    resource_type: str,
    resource_id: str,
    resource_title: str = "",
    field: str,
    old_value: Any = None,
    new_value: Any = None,
    source: str = "shopify_apply",
    job_id: str | None = None,
) -> int | None:
    """Create one snapshot and one applied ledger event for a successful live write.

    The helper is intentionally fail-open for callers: if baseline snapshot data is
    unavailable, it still records a minimal event so measurement can start. Duplicate
    writes for the same shop/resource/field/day are ignored.
    """
    applied_day = datetime.now(UTC).date().isoformat()
    if _already_recorded(shop, resource_id, field, applied_day):
        return None

    before_snapshot = _minimal_snapshot(
        shop=shop,
        resource_type=resource_type,
        resource_id=resource_id,
        resource_title=resource_title,
        field=field,
        old_value=old_value,
        new_value=new_value,
    )
    metrics_before: dict[str, Any] = {}
    snapshot_id: int | None = None

    try:
        snapshot_path = data_dir() / shop / "shopify_snapshot.json"
        snapshot = load_snapshot_from_file_or_db(shop, snapshot_path) or {}
        built = build_optimization_snapshot(
            shop=shop,
            snapshot=snapshot,
            resource_type=resource_type,
            resource_id=resource_id,
            action_type=field,
            source=source,
            hypothesis=f"Live write changed {field}",
        )
        built["snapshot"]["change"] = {"field": field, "old_value": old_value, "new_value": new_value}
        snapshot_id = create_optimization_snapshot(shop=shop, snapshot_data=built)
        before_snapshot = built["snapshot"]
        metrics_before = built["metrics"]
    except (OSError, ValueError, KeyError, TypeError):
        metrics_before = {"measurement_note": "Baseline snapshot unavailable; event recorded from live write result."}

    return create_geo_event(
        shop=shop,
        event_type="optimization",
        resource_type=resource_type,
        resource_id=resource_id,
        resource_title=resource_title,
        action_type=field,
        before_snapshot=before_snapshot,
        metrics_before=metrics_before,
        estimated_impact={"source": source, "field": field},
        status="applied",
        source=source,
        job_id=job_id,
        snapshot_id=snapshot_id,
        after_snapshot={"field": field, "value": new_value},
        notes="Automatically created after a confirmed live Shopify write.",
    )
