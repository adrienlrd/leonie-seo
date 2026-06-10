"""Automatic GEO impact tracking for live Shopify writes.

Every time a proposal is applied live (not dry-run), this module records a
before-state optimization snapshot and an "applied" GEO impact event so the
measurement pages (`/geo/progress-curve`, `/geo/impact-report`, ...) and the
analysis engine's optimization history (Task 6) can see what changed and when,
without requiring the merchant to manually create a ledger entry.
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.db_adapter import DB_PATH, get_conn
from app.geo.ledger import create_geo_event
from app.geo.optimization_snapshots import create_optimization_snapshot
from app.impact.report import _find_gsc_file, _parse_gsc_csv

logger = logging.getLogger(__name__)


def _content_hash(payload: dict[str, Any]) -> str:
    digest = hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()
    return digest[:16]


def _resource_path(resource_type: str, resource_handle: str) -> str:
    if not resource_handle:
        return ""
    if resource_type == "collection":
        return f"/collections/{resource_handle}"
    if resource_type == "product":
        return f"/products/{resource_handle}"
    return ""


def _gsc_metrics_for_path(shop: str, path: str) -> dict[str, Any]:
    empty = {"clicks": 0, "impressions": 0, "ctr": 0.0, "position": 0.0}
    if not path:
        return empty
    gsc_file = _find_gsc_file(shop)
    if gsc_file is None:
        return empty
    rows = _parse_gsc_csv(gsc_file.read_text())
    target = path.rstrip("/")
    for url, row in rows.items():
        if url.rstrip("/").endswith(target):
            return {
                "clicks": int(row.get("clicks", 0) or 0),
                "impressions": int(row.get("impressions", 0) or 0),
                "ctr": float(row.get("ctr", 0.0) or 0.0),
                "position": float(row.get("position", 0.0) or 0.0),
            }
    return empty


def _already_applied_today(
    *,
    shop: str,
    resource_type: str,
    resource_id: str,
    action_type: str,
    field: str,
    db_path: Path | None,
) -> bool:
    """Return True if this (resource, action, field) was applied earlier today."""
    path = db_path if db_path is not None else DB_PATH
    today = datetime.now(UTC).date().isoformat()
    with get_conn(path) as conn:
        rows = conn.execute(
            """
            SELECT after_snapshot
            FROM geo_impact_events
            WHERE shop = ? AND resource_type = ? AND resource_id = ?
              AND action_type = ? AND status = 'applied'
              AND created_at LIKE ?
            """,
            (shop, resource_type, resource_id, action_type, f"{today}%"),
        ).fetchall()
    for row in rows:
        after_raw = row["after_snapshot"]
        try:
            after = json.loads(after_raw) if after_raw else {}
        except json.JSONDecodeError:
            after = {}
        if isinstance(after, dict) and after.get("field") == field:
            return True
    return False


def record_applied_change(
    *,
    shop: str,
    resource_type: str,
    resource_id: str,
    resource_title: str,
    action_type: str,
    field: str,
    old_value: Any,
    new_value: Any,
    resource_handle: str = "",
    db_path: Path | None = None,
) -> int | None:
    """Record one live Shopify write as a GEO snapshot + "applied" impact event.

    Idempotent: returns None without writing anything if the same
    (resource, action_type, field) was already recorded as applied earlier
    on the same calendar day (UTC).

    The Shopify write this records has already succeeded by the time this
    function is called. Any failure here is a local bookkeeping problem, not
    a Shopify-side one, so errors are logged and swallowed (returning None)
    rather than bubbling up as a 500 to the merchant for a write that already
    went through.
    """
    path = db_path if db_path is not None else DB_PATH
    try:
        if _already_applied_today(
            shop=shop,
            resource_type=resource_type,
            resource_id=resource_id,
            action_type=action_type,
            field=field,
            db_path=path,
        ):
            return None

        resource_path = _resource_path(resource_type, resource_handle)
        gsc_metrics = _gsc_metrics_for_path(shop, resource_path)

        snapshot_payload = {
            "shop": shop,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "resource_title": resource_title,
            "path": resource_path,
            "action_type": action_type,
            "source": "auto_apply",
            "hypothesis": None,
            "captured_at": datetime.now(UTC).isoformat(),
            "field": field,
            "content": {field: old_value},
        }
        metrics_payload = {
            "gsc": gsc_metrics,
            "measurement_note": (
                "Baseline metrics captured at apply time; learning compares J+14/J+28 "
                "windows and keeps J+60 as long-term history."
            ),
        }
        snapshot_data = {
            "resource_type": resource_type,
            "resource_id": resource_id,
            "resource_title": resource_title,
            "action_type": action_type,
            "source": "auto_apply",
            "hypothesis": None,
            "snapshot": snapshot_payload,
            "metrics": metrics_payload,
            "readiness_score": 0,
            "seo_score": 0,
            "content_hash": _content_hash(snapshot_payload),
        }
        snapshot_id = create_optimization_snapshot(
            shop=shop, snapshot_data=snapshot_data, db_path=path
        )

        return create_geo_event(
            shop=shop,
            event_type="applied_optimization",
            resource_type=resource_type,
            resource_id=resource_id,
            resource_title=resource_title,
            action_type=action_type,
            before_snapshot=snapshot_payload,
            metrics_before=metrics_payload,
            estimated_impact={},
            status="applied",
            source="auto_apply",
            snapshot_id=snapshot_id,
            measurement_status="baseline_captured",
            after_snapshot={"field": field, "value": new_value},
            db_path=path,
        )
    except Exception:
        logger.exception(
            "Failed to record GEO impact tracking for shop=%s resource_id=%s field=%s",
            shop,
            resource_id,
            field,
        )
        return None
