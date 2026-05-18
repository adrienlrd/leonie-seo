"""Aggregate snapshots, optimization events, GSC and GA4 daily data into time-series.

The progress curve dashboard (task 120) reads from the GEO impact validation
ledger (task 116/117) and live analytics integrations to render a 90-day view
of optimization impact. This module is pure: it takes already-loaded data and
emits the dashboard payload, so the FastAPI route stays thin.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

ImpressionLowVolumeThreshold = 1000


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed


def _day_key(value: str | None) -> str | None:
    parsed = _parse_iso(value)
    return parsed.date().isoformat() if parsed else None


def _coerce_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _coerce_int(value: Any) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def _within_window(
    created_at: str, window_start: datetime
) -> bool:
    parsed = _parse_iso(created_at)
    return parsed is not None and parsed >= window_start


def _latest_per_day(
    snapshots: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Keep only the latest snapshot per day, ordered ascending by date."""
    by_day: dict[str, dict[str, Any]] = {}
    for snap in snapshots:
        day = _day_key(snap.get("created_at"))
        if not day:
            continue
        previous = by_day.get(day)
        if previous is None or (snap.get("created_at") or "") > (previous.get("created_at") or ""):
            by_day[day] = snap
    return [by_day[day] for day in sorted(by_day)]


def _score_series(
    snapshots: list[dict[str, Any]], score_key: str
) -> list[dict[str, Any]]:
    series: list[dict[str, Any]] = []
    for snap in snapshots:
        day = _day_key(snap.get("created_at"))
        if not day:
            continue
        value = snap.get(score_key)
        if value is None:
            continue
        series.append({"date": day, "value": int(value)})
    return series


def _gsc_metric_series(
    snapshots: list[dict[str, Any]], metric: str, coerce: str = "int"
) -> list[dict[str, Any]]:
    series: list[dict[str, Any]] = []
    for snap in snapshots:
        day = _day_key(snap.get("created_at"))
        if not day:
            continue
        gsc = (snap.get("metrics") or {}).get("gsc") or {}
        if metric not in gsc:
            continue
        raw = gsc.get(metric)
        value = _coerce_int(raw) if coerce == "int" else round(_coerce_float(raw), 4)
        series.append({"date": day, "value": value})
    return series


def _ga4_series(
    ga4_daily: dict[str, dict[str, Any]], field: str, coerce: str = "int"
) -> list[dict[str, Any]]:
    series: list[dict[str, Any]] = []
    for day in sorted(ga4_daily):
        row = ga4_daily[day] or {}
        if field not in row:
            continue
        raw = row.get(field)
        value = _coerce_int(raw) if coerce == "int" else round(_coerce_float(raw), 2)
        series.append({"date": day, "value": value})
    return series


def _impact_series(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_day: dict[str, dict[str, float]] = {}
    for event in events:
        day = _day_key(event.get("created_at"))
        if not day:
            continue
        bucket = by_day.setdefault(day, {"estimated": 0.0, "observed": 0.0})
        estimated = (event.get("estimated_impact") or {}).get("revenue_estimate")
        observed = (event.get("observed_impact") or {}).get("revenue") if event.get("observed_impact") else None
        bucket["estimated"] += _coerce_float(estimated)
        if observed is not None:
            bucket["observed"] += _coerce_float(observed)
    return [
        {
            "date": day,
            "estimated": round(by_day[day]["estimated"], 2),
            "observed": round(by_day[day]["observed"], 2),
        }
        for day in sorted(by_day)
    ]


def _optimization_summary(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    summary: list[dict[str, Any]] = []
    for event in events:
        summary.append(
            {
                "event_id": event.get("id"),
                "resource_type": event.get("resource_type"),
                "resource_id": event.get("resource_id"),
                "resource_title": event.get("resource_title"),
                "applied_at": event.get("created_at"),
                "status": event.get("status"),
                "measurement_status": event.get("measurement_status"),
            }
        )
    return summary


def _commerce_flags(snapshots: list[dict[str, Any]]) -> tuple[int, int]:
    """Count resource_ids with out-of-stock observations or price changes."""
    by_resource: dict[str, list[dict[str, Any]]] = {}
    for snap in snapshots:
        rid = str(snap.get("resource_id") or "")
        if not rid:
            continue
        by_resource.setdefault(rid, []).append(snap)

    oos_pages = 0
    price_changed_pages = 0
    for resource_snaps in by_resource.values():
        ordered = sorted(resource_snaps, key=lambda s: s.get("created_at") or "")
        inventories: list[int] = []
        prices: list[str] = []
        for snap in ordered:
            commerce = ((snap.get("snapshot") or {}).get("commerce")) or {}
            inv = commerce.get("inventory_quantity")
            if inv is not None:
                inventories.append(_coerce_int(inv))
            price = commerce.get("price")
            if price is not None:
                prices.append(str(price))
        if any(qty <= 0 for qty in inventories):
            oos_pages += 1
        unique_prices = {p for p in prices if p not in ("", "None")}
        if len(unique_prices) >= 2:
            price_changed_pages += 1
    return oos_pages, price_changed_pages


def build_progress_curve(
    *,
    shop: str,
    snapshots: list[dict[str, Any]],
    events: list[dict[str, Any]],
    ga4_daily: dict[str, dict[str, Any]] | None,
    gsc_available: bool,
    ga4_connected: bool,
    window_days: int = 90,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Aggregate snapshots, events and analytics into dashboard time-series.

    Args:
        shop: Shopify domain.
        snapshots: Items from ``list_optimization_snapshots`` (already filtered).
        events: Items from ``list_geo_events`` (already filtered).
        ga4_daily: Daily organic GA4 rows keyed by ISO date (``YYYY-MM-DD``).
            Each value can include ``sessions``, ``conversions``, ``revenue``.
            ``None`` or empty when GA4 is not connected.
        gsc_available: True when a per-shop GSC export was located.
        ga4_connected: True when the GA4 client could be built for the shop.
        window_days: Curve window in days (capped to 1–365 by caller).
        now: Reference time for window cutoff (testability).

    Returns:
        Payload consumed by ``GET /api/shops/{shop}/geo/progress-curve``.
    """
    reference = now or datetime.now(UTC)
    if reference.tzinfo is None:
        reference = reference.replace(tzinfo=UTC)
    window_start = reference - timedelta(days=window_days)

    in_window_snapshots = [s for s in snapshots if _within_window(s.get("created_at") or "", window_start)]
    in_window_events = [e for e in events if _within_window(e.get("created_at") or "", window_start)]
    ordered_snapshots = _latest_per_day(in_window_snapshots)
    daily = ga4_daily or {}

    series = {
        "geo_score": _score_series(ordered_snapshots, "readiness_score"),
        "seo_score": _score_series(ordered_snapshots, "seo_score"),
        "impressions": _gsc_metric_series(ordered_snapshots, "impressions"),
        "clicks": _gsc_metric_series(ordered_snapshots, "clicks"),
        "ctr": _gsc_metric_series(ordered_snapshots, "ctr", coerce="float"),
        "position": _gsc_metric_series(ordered_snapshots, "position", coerce="float"),
        "sessions": _ga4_series(daily, "sessions"),
        "conversions": _ga4_series(daily, "conversions"),
        "revenue": _ga4_series(daily, "revenue", coerce="float"),
        "impact_estimated_vs_observed": _impact_series(in_window_events),
    }

    total_impressions = sum(point["value"] for point in series["impressions"])
    oos_pages, price_changed_pages = _commerce_flags(in_window_snapshots)

    flags = {
        "low_volume": total_impressions < ImpressionLowVolumeThreshold,
        "incomplete_tracking": (not ga4_connected) or (not gsc_available),
        "out_of_stock_pages": oos_pages,
        "price_changed_pages": price_changed_pages,
    }

    return {
        "shop": shop,
        "window_days": window_days,
        "generated_at": reference.isoformat(),
        "series": series,
        "optimizations_in_validation": _optimization_summary(in_window_events),
        "flags": flags,
        "totals": {
            "snapshots_in_window": len(in_window_snapshots),
            "events_in_window": len(in_window_events),
            "total_impressions": total_impressions,
        },
    }
