"""Analysis overview — grouped by application date with 28-day window logic.

For each application date:
- If 28 days passed before the next application → show GSC traffic at J+28
- If it's the last application and < 28 days elapsed → show countdown
- If a new application happened before 28 days → "insufficient data (<28 days)"
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


def _parse_date(iso_str: str) -> datetime | None:
    if not iso_str:
        return None
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        return dt.astimezone(UTC) if dt.tzinfo else dt.replace(tzinfo=UTC)
    except (ValueError, AttributeError):
        return None


def _extract_applied_at(event: dict[str, Any]) -> str:
    for entry in event.get("status_history") or []:
        if entry.get("status") in {"applied", "measured"}:
            return entry.get("changed_at") or event.get("created_at", "")
    return event.get("created_at", "")


def _truncate(value: Any, max_len: int = 120) -> str:
    s = str(value or "")
    if len(s) > max_len:
        return s[:max_len] + "…"
    return s


def build_analysis_overview(
    shop: str,
    *,
    db_path: Path | None = None,
) -> dict[str, Any]:
    """Build analysis grouped by application date with 28-day window status.

    Returns:
        Dict with ``application_dates`` list (sorted most recent first) and ``summary``.
    """
    path = db_path or DB_PATH
    now = datetime.now(UTC)

    events_data = list_geo_events(shop, limit=200, status="applied", db_path=path)
    events = events_data["events"]
    measured_data = list_geo_events(shop, limit=200, status="measured", db_path=path)
    events.extend(measured_data["events"])

    gsc_file = _find_gsc_file(shop)
    gsc_rows = _parse_gsc_csv(gsc_file.read_text()) if gsc_file else {}

    # Group events by application date (YYYY-MM-DD)
    by_date: dict[str, list[dict[str, Any]]] = {}
    for event in events:
        applied_at = _extract_applied_at(event)
        date_key = applied_at[:10]
        if not date_key:
            continue
        by_date.setdefault(date_key, []).append(event)

    # Sort dates chronologically to compute window gaps
    sorted_dates = sorted(by_date.keys())

    application_dates: list[dict[str, Any]] = []

    for i, date_key in enumerate(sorted_dates):
        date_events = by_date[date_key]
        applied_dt = _parse_date(date_key)
        if applied_dt is None:
            continue

        j28_dt = applied_dt + timedelta(days=28)
        j28_date = j28_dt.strftime("%Y-%m-%d")

        # Determine window status
        is_last = i == len(sorted_dates) - 1
        next_date_key = sorted_dates[i + 1] if not is_last else None
        next_dt = _parse_date(next_date_key) if next_date_key else None

        if not is_last and next_dt is not None:
            days_to_next = (next_dt - applied_dt).days
            if days_to_next < 28:
                window_status = "insufficient"
                window_message_fr = f"Pas assez de données (nouvelle application après {days_to_next} j < 28 j)"
                window_message_en = f"Insufficient data (new application after {days_to_next} d < 28 d)"
                days_remaining = 0
            else:
                window_status = "complete"
                window_message_fr = "Fenêtre de 28 jours complète"
                window_message_en = "28-day window complete"
                days_remaining = 0
        else:
            # Last application date
            elapsed = (now - applied_dt).days
            if elapsed >= 28:
                window_status = "complete"
                window_message_fr = "Fenêtre de 28 jours complète"
                window_message_en = "28-day window complete"
                days_remaining = 0
            else:
                window_status = "waiting"
                days_remaining = 28 - elapsed
                window_message_fr = f"Encore {days_remaining} jour{'s' if days_remaining > 1 else ''} avant la mesure J+28"
                window_message_en = f"{days_remaining} day{'s' if days_remaining > 1 else ''} remaining until J+28 measurement"

        # Collect products for this date
        products_in_date: dict[str, dict[str, Any]] = {}
        for event in date_events:
            rid = event["resource_id"]
            if rid not in products_in_date:
                before_snapshot = event.get("before_snapshot") or {}
                resource_path = before_snapshot.get("path", "")
                products_in_date[rid] = {
                    "resource_id": rid,
                    "resource_type": event["resource_type"],
                    "resource_title": event["resource_title"],
                    "resource_path": resource_path,
                    "actions": [],
                    "traffic_28d": _gsc_traffic_for_path(resource_path, gsc_rows) if window_status == "complete" else None,
                }

            product = products_in_date[rid]
            before_snapshot = event.get("before_snapshot") or {}
            after_snapshot = event.get("after_snapshot") or {}
            metrics_before = (event.get("metrics_before") or {}).get("gsc") or {}
            metrics_after = (event.get("metrics_after") or {}).get("gsc") or {}

            product["actions"].append({
                "event_id": event["id"],
                "action_type": event["action_type"],
                "field": after_snapshot.get("field", event["action_type"]),
                "old_value": _truncate(
                    before_snapshot.get("content", {}).get(after_snapshot.get("field", ""), "")
                ),
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

        application_dates.append({
            "date": date_key,
            "j28_date": j28_date,
            "window_status": window_status,
            "window_message_fr": window_message_fr,
            "window_message_en": window_message_en,
            "days_remaining": days_remaining,
            "products": list(products_in_date.values()),
            "total_actions": sum(len(p["actions"]) for p in products_in_date.values()),
        })

    # Most recent first for display
    application_dates.reverse()

    return {
        "application_dates": application_dates,
        "summary": {
            "total_dates": len(application_dates),
            "total_products": len({e["resource_id"] for e in events}),
            "total_actions": len(events),
        },
    }
