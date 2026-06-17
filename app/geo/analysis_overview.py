"""Analysis overview — grouped by product, then by validation date.

For each product, lists validation dates chronologically. For each date:
- "complete": 28 days passed before the next validation on this product → show GSC traffic
- "waiting": last validation on this product and < 28 days elapsed → show countdown
- "insufficient": new validation on this product happened before 28 days → flag
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from app.db_adapter import DB_PATH
from app.geo.ledger import list_geo_events
from app.impact.report import _find_gsc_file, _parse_gsc_csv

logger = logging.getLogger(__name__)


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


def _window_status_for_date(
    applied_dt: datetime,
    next_dt: datetime | None,
    now: datetime,
) -> dict[str, Any]:
    """Compute the 28-day window status for a single validation date on one product."""
    j28_dt = applied_dt + timedelta(days=28)
    j28_date = j28_dt.strftime("%Y-%m-%d")

    if next_dt is not None:
        days_to_next = (next_dt - applied_dt).days
        if days_to_next < 28:
            return {
                "j28_date": j28_date,
                "window_status": "insufficient",
                "days_remaining": 0,
                "days_to_next": days_to_next,
                "window_message_fr": "Modifié à nouveau en moins de 28 j — pas assez de recul pour mesurer l'impact",
                "window_message_en": "Modified again within 28 d — not enough time to measure impact",
            }
        return {
            "j28_date": j28_date,
            "window_status": "complete",
            "days_remaining": 0,
            "days_to_next": days_to_next,
            "window_message_fr": "Fenêtre de 28 jours complète",
            "window_message_en": "28-day window complete",
        }

    elapsed = (now - applied_dt).days
    if elapsed >= 28:
        return {
            "j28_date": j28_date,
            "window_status": "complete",
            "days_remaining": 0,
            "days_to_next": None,
            "window_message_fr": "Fenêtre de 28 jours complète",
            "window_message_en": "28-day window complete",
        }
    days_remaining = 28 - elapsed
    return {
        "j28_date": j28_date,
        "window_status": "waiting",
        "days_remaining": days_remaining,
        "days_to_next": None,
        "window_message_fr": f"Encore {days_remaining} jour{'s' if days_remaining > 1 else ''} avant la mesure J+28",
        "window_message_en": f"{days_remaining} day{'s' if days_remaining > 1 else ''} remaining until J+28 measurement",
    }


def build_analysis_overview(
    shop: str,
    *,
    db_path: Path | None = None,
) -> dict[str, Any]:
    """Build analysis grouped by product, then by validation date.

    Returns:
        Dict with ``products`` list and ``summary``.
    """
    path = db_path or DB_PATH
    now = datetime.now(UTC)

    events_data = list_geo_events(shop, limit=200, status="applied", db_path=path)
    events = events_data["events"]
    measured_data = list_geo_events(shop, limit=200, status="measured", db_path=path)
    events.extend(measured_data["events"])

    gsc_file = _find_gsc_file(shop)
    gsc_rows = _parse_gsc_csv(gsc_file.read_text()) if gsc_file else {}

    # Group events by product, then by date
    products_map: dict[str, dict[str, Any]] = {}

    for event in events:
        rid = event["resource_id"]
        if rid not in products_map:
            before_snapshot = event.get("before_snapshot") or {}
            resource_path = before_snapshot.get("path", "")
            products_map[rid] = {
                "resource_id": rid,
                "resource_type": event["resource_type"],
                "resource_title": event["resource_title"],
                "resource_path": resource_path,
                "dates_map": {},
                "latest_applied_at": "",
            }

        product = products_map[rid]
        applied_at = _extract_applied_at(event)
        date_key = applied_at[:10]
        if not date_key:
            continue

        if date_key > product["latest_applied_at"]:
            product["latest_applied_at"] = date_key

        if date_key not in product["dates_map"]:
            product["dates_map"][date_key] = []

        before_snapshot = event.get("before_snapshot") or {}
        after_snapshot = event.get("after_snapshot") or {}
        metrics_before = (event.get("metrics_before") or {}).get("gsc") or {}
        metrics_after = (event.get("metrics_after") or {}).get("gsc") or {}

        product["dates_map"][date_key].append({
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

    # Build final product list with dated validation entries
    product_list: list[dict[str, Any]] = []

    for product in products_map.values():
        dates_map = product.pop("dates_map")
        sorted_date_keys = sorted(dates_map.keys())

        validation_dates: list[dict[str, Any]] = []
        for i, date_key in enumerate(sorted_date_keys):
            applied_dt = _parse_date(date_key)
            if applied_dt is None:
                continue

            is_last = i == len(sorted_date_keys) - 1
            next_date_key = sorted_date_keys[i + 1] if not is_last else None
            next_dt = _parse_date(next_date_key) if next_date_key else None

            window = _window_status_for_date(applied_dt, next_dt, now)

            show_traffic = window["window_status"] == "complete"
            traffic_28d = _gsc_traffic_for_path(product["resource_path"], gsc_rows) if show_traffic else None

            validation_dates.append({
                "date": date_key,
                "actions": dates_map[date_key],
                "traffic_28d": traffic_28d,
                **window,
            })

        # Most recent date first within each product
        validation_dates.reverse()

        product_list.append({
            "resource_id": product["resource_id"],
            "resource_type": product["resource_type"],
            "resource_title": product["resource_title"],
            "resource_path": product["resource_path"],
            "latest_applied_at": product["latest_applied_at"],
            "validation_dates": validation_dates,
            "total_actions": sum(len(d["actions"]) for d in validation_dates),
        })

    # Most recently optimized product first
    product_list.sort(key=lambda p: p["latest_applied_at"], reverse=True)

    return {
        "products": product_list,
        "summary": {
            "total_products": len(product_list),
            "total_actions": len(events),
        },
    }
