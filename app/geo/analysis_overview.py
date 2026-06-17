"""Analysis overview — per-product summary of applied changes + GSC traffic.

Groups applied geo_impact_events and seo_changes by resource, enriches each
with 28-day GSC traffic, and returns a product-level summary suitable for the
"Analyse" page.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from app.db_adapter import DB_PATH, get_conn
from app.geo.ledger import list_geo_events
from app.impact.report import _find_gsc_file, _parse_gsc_csv

logger = logging.getLogger(__name__)


def _load_recent_seo_changes(
    shop: str,
    days: int = 90,
    *,
    db_path: Path | None = None,
) -> list[dict[str, Any]]:
    path = db_path or DB_PATH
    cutoff = (datetime.now(UTC) - timedelta(days=days)).isoformat()
    with get_conn(path) as conn:
        rows = conn.execute(
            """SELECT resource_type, resource_id, field, old_value, new_value, applied_at
               FROM seo_changes
               WHERE status = 'applied' AND shop = ? AND applied_at >= ?
               ORDER BY applied_at DESC""",
            (shop, cutoff),
        ).fetchall()
    return [dict(r) for r in rows]


def _gsc_traffic_for_path(
    resource_path: str,
    gsc_rows: dict[str, dict],
) -> dict[str, Any]:
    empty = {"clicks": 0, "impressions": 0, "ctr": 0.0, "position": 0.0}
    if not resource_path:
        return empty
    target = resource_path.rstrip("/")
    for url, row in gsc_rows.items():
        if url.rstrip("/").endswith(target):
            return {
                "clicks": int(row.get("clicks", 0) or 0),
                "impressions": int(row.get("impressions", 0) or 0),
                "ctr": round(float(row.get("ctr", 0.0) or 0.0), 4),
                "position": round(float(row.get("position", 0.0) or 0.0), 1),
            }
    return empty


def _add_28_days(iso_date: str) -> str:
    try:
        dt = datetime.fromisoformat(iso_date.replace("Z", "+00:00"))
        return (dt + timedelta(days=28)).strftime("%Y-%m-%d")
    except (ValueError, AttributeError):
        return ""


def build_analysis_overview(
    shop: str,
    *,
    db_path: Path | None = None,
) -> dict[str, Any]:
    """Build per-product analysis overview with changes, before/after, and traffic.

    Returns:
        Dict with ``products`` list and ``summary``.
    """
    path = db_path or DB_PATH

    events_data = list_geo_events(shop, limit=200, status="applied", db_path=path)
    events = events_data["events"]
    # Also include measured events
    measured_data = list_geo_events(shop, limit=200, status="measured", db_path=path)
    events.extend(measured_data["events"])

    seo_changes = _load_recent_seo_changes(shop, days=90, db_path=path)

    gsc_file = _find_gsc_file(shop)
    gsc_rows = _parse_gsc_csv(gsc_file.read_text()) if gsc_file else {}

    products: dict[str, dict[str, Any]] = {}

    for event in events:
        rid = event["resource_id"]
        if rid not in products:
            before_snapshot = event.get("before_snapshot") or {}
            resource_path = before_snapshot.get("path", "")
            products[rid] = {
                "resource_id": rid,
                "resource_type": event["resource_type"],
                "resource_title": event["resource_title"],
                "resource_path": resource_path,
                "events": [],
                "changes": [],
                "traffic_28d": {},
                "latest_applied_at": "",
                "j28_date": "",
            }
        product = products[rid]

        applied_at = ""
        for entry in event.get("status_history") or []:
            if entry.get("status") in {"applied", "measured"}:
                applied_at = entry.get("changed_at") or event.get("created_at", "")
        if not applied_at:
            applied_at = event.get("created_at", "")

        metrics_before = (event.get("metrics_before") or {}).get("gsc") or {}
        metrics_after = (event.get("metrics_after") or {}).get("gsc") or {}
        before_snapshot = event.get("before_snapshot") or {}
        after_snapshot = event.get("after_snapshot") or {}

        product["events"].append({
            "event_id": event["id"],
            "action_type": event["action_type"],
            "applied_at": applied_at[:10],
            "status": event["status"],
            "measurement_status": event.get("measurement_status", ""),
            "field": after_snapshot.get("field", event["action_type"]),
            "old_value": _truncate(before_snapshot.get("content", {}).get(
                after_snapshot.get("field", ""), ""
            )),
            "new_value": _truncate(after_snapshot.get("value", "")),
            "gsc_before": {
                "clicks": int(metrics_before.get("clicks", 0) or 0),
                "impressions": int(metrics_before.get("impressions", 0) or 0),
                "position": round(float(metrics_before.get("position", 0.0) or 0.0), 1),
            },
            "gsc_after": {
                "clicks": int(metrics_after.get("clicks", 0) or 0),
                "impressions": int(metrics_after.get("impressions", 0) or 0),
                "position": round(float(metrics_after.get("position", 0.0) or 0.0), 1),
            } if metrics_after else None,
        })

        if applied_at > product["latest_applied_at"]:
            product["latest_applied_at"] = applied_at[:10]
            product["j28_date"] = _add_28_days(applied_at)

    for change in seo_changes:
        rid = change["resource_id"]
        if rid in products:
            products[rid]["changes"].append({
                "field": change["field"],
                "old_value": _truncate(change.get("old_value", "")),
                "new_value": _truncate(change.get("new_value", "")),
                "applied_at": (change.get("applied_at") or "")[:10],
            })

    for product in products.values():
        resource_path = product["resource_path"]
        product["traffic_28d"] = _gsc_traffic_for_path(resource_path, gsc_rows)

    product_list = sorted(
        products.values(),
        key=lambda p: p["latest_applied_at"],
        reverse=True,
    )

    return {
        "products": product_list,
        "summary": {
            "total_products": len(product_list),
            "total_events": sum(len(p["events"]) for p in product_list),
        },
    }


def _truncate(value: Any, max_len: int = 120) -> str:
    s = str(value or "")
    if len(s) > max_len:
        return s[:max_len] + "…"
    return s
