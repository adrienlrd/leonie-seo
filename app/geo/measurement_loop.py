"""Lazy measurement loop — collects post-optimization GSC/GA4 metrics.

Triggered by the measure page loader. For each geo_impact_event that has
reached a measurement window (J+14 or J+28) but still lacks ``metrics_after``,
this module fetches current GSC + GA4 data for the resource URL and writes it
into the event row via ``update_geo_event_status``.

Idempotent and fail-open: safe to call on every page load.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.db_adapter import DB_PATH
from app.geo.ledger import list_geo_events, update_geo_event_status
from app.impact.report import _find_gsc_file, _parse_gsc_csv

logger = logging.getLogger(__name__)

_MEASURABLE_STATUSES = {"applied", "measured"}
_WINDOW_DAYS = {"j14": 14, "j28": 28}


def collect_metrics_for_url(
    resource_path: str,
    gsc_rows: dict[str, dict],
    ga4_page_data: dict[str, dict] | None = None,
) -> dict[str, Any]:
    """Look up current GSC + GA4 metrics for a resource path.

    Args:
        resource_path: Path portion like ``/products/harnais-premium``.
        gsc_rows: Dict keyed by full URL from ``_parse_gsc_csv``.
        ga4_page_data: Dict keyed by page path from ``get_organic_by_page``.

    Returns:
        ``{"gsc": {...}, "ga4": {...}}`` with available metrics.
    """
    empty_gsc = {"clicks": 0, "impressions": 0, "ctr": 0.0, "position": 0.0}
    empty_ga4: dict[str, Any] = {}

    gsc = dict(empty_gsc)
    if resource_path:
        target = resource_path.rstrip("/")
        for url, row in gsc_rows.items():
            if url.rstrip("/").endswith(target):
                gsc = {
                    "clicks": int(row.get("clicks", 0) or 0),
                    "impressions": int(row.get("impressions", 0) or 0),
                    "ctr": float(row.get("ctr", 0.0) or 0.0),
                    "position": float(row.get("position", 0.0) or 0.0),
                }
                break

    ga4 = dict(empty_ga4)
    if ga4_page_data and resource_path:
        target = resource_path.rstrip("/")
        ga4_row = ga4_page_data.get(target) or ga4_page_data.get(target + "/")
        if ga4_row:
            ga4 = {
                "sessions": int(ga4_row.get("sessions", 0) or 0),
                "conversions": int(ga4_row.get("conversions", 0) or 0),
                "revenue": float(ga4_row.get("revenue", 0.0) or 0.0),
            }

    return {"gsc": gsc, "ga4": ga4}


def _compute_observed_impact(
    metrics_before: dict[str, Any],
    metrics_after: dict[str, Any],
) -> dict[str, Any]:
    """Compute percentage deltas between before and after metrics."""
    before_gsc = (metrics_before or {}).get("gsc") or {}
    after_gsc = (metrics_after or {}).get("gsc") or {}

    def _pct_delta(before: float, after: float) -> float | None:
        if before == 0:
            return None
        return round((after - before) / before * 100, 1)

    imp_b = int(before_gsc.get("impressions", 0) or 0)
    imp_a = int(after_gsc.get("impressions", 0) or 0)
    clk_b = int(before_gsc.get("clicks", 0) or 0)
    clk_a = int(after_gsc.get("clicks", 0) or 0)
    pos_b = float(before_gsc.get("position", 0.0) or 0.0)
    pos_a = float(after_gsc.get("position", 0.0) or 0.0)

    return {
        "impressions_delta_pct": _pct_delta(imp_b, imp_a),
        "clicks_delta_pct": _pct_delta(clk_b, clk_a),
        "position_before": pos_b,
        "position_after": pos_a,
        "position_improved": pos_a < pos_b if pos_b > 0 and pos_a > 0 else None,
    }


def _highest_reached_window(
    applied_at: datetime,
    now: datetime,
) -> tuple[str, int] | None:
    """Return the highest measurement window the event has reached."""
    elapsed = (now - applied_at).days
    if elapsed >= 28:
        return "j28", 28
    if elapsed >= 14:
        return "j14", 14
    return None


def _parse_applied_at(event: dict[str, Any]) -> datetime | None:
    for entry in event.get("status_history") or []:
        if entry.get("status") in _MEASURABLE_STATUSES:
            raw = str(entry.get("changed_at") or "")
            if raw:
                try:
                    parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
                    return parsed.astimezone(UTC) if parsed.tzinfo else parsed.replace(tzinfo=UTC)
                except ValueError:
                    pass
    raw = str(event.get("created_at") or "")
    if raw:
        try:
            parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            return parsed.astimezone(UTC) if parsed.tzinfo else parsed.replace(tzinfo=UTC)
        except ValueError:
            pass
    return None


def _already_measured_for_window(event: dict[str, Any], window_key: str) -> bool:
    ms = str(event.get("measurement_status") or "").lower()
    return window_key in ms


def run_measurement_loop(
    shop: str,
    *,
    db_path: Path | None = None,
) -> dict[str, Any]:
    """Collect post-optimization metrics for events that have reached a window.

    Fail-open: any error is logged and skipped, never raised.
    Idempotent: events already measured for a window are skipped.

    Returns:
        Summary dict with counts of checked/updated/skipped events.
    """
    path = db_path if db_path is not None else DB_PATH
    now = datetime.now(UTC)
    summary: dict[str, Any] = {
        "events_checked": 0,
        "events_updated": 0,
        "events_skipped": 0,
        "gsc_status": "not_checked",
        "ga4_available": False,
        "errors": [],
    }

    try:
        data = list_geo_events(shop, limit=200, db_path=path)
    except Exception as exc:
        logger.warning("measurement_loop: failed to load events for %s: %s", shop, exc)
        summary["errors"].append(str(exc))
        return summary

    events = [e for e in data["events"] if e.get("status") in _MEASURABLE_STATUSES]
    summary["events_checked"] = len(events)

    # Filter to events that need measurement
    events_to_measure: list[tuple[dict[str, Any], str, int]] = []
    for event in events:
        applied_at = _parse_applied_at(event)
        if applied_at is None:
            continue
        window = _highest_reached_window(applied_at, now)
        if window is None:
            continue
        window_key, window_days = window
        if _already_measured_for_window(event, window_key):
            summary["events_skipped"] += 1
            continue
        events_to_measure.append((event, window_key, window_days))

    if not events_to_measure:
        return summary

    # Refresh GSC once for all events
    gsc_status = _refresh_gsc_if_needed(shop)
    summary["gsc_status"] = gsc_status.get("status", "unknown")

    # Load GSC data
    gsc_file = _find_gsc_file(shop)
    gsc_rows = _parse_gsc_csv(gsc_file.read_text()) if gsc_file else {}

    # Load GA4 data (fail-open)
    ga4_page_data = _load_ga4_page_data(shop)
    summary["ga4_available"] = ga4_page_data is not None

    for event, window_key, window_days in events_to_measure:
        try:
            _measure_single_event(
                shop=shop,
                event=event,
                window_key=window_key,
                gsc_rows=gsc_rows,
                ga4_page_data=ga4_page_data,
                db_path=path,
            )
            summary["events_updated"] += 1
        except Exception as exc:
            logger.warning(
                "measurement_loop: failed to measure event %s for %s: %s",
                event.get("id"),
                shop,
                exc,
            )
            summary["errors"].append(f"event {event.get('id')}: {exc}")

    return summary


def _measure_single_event(
    *,
    shop: str,
    event: dict[str, Any],
    window_key: str,
    gsc_rows: dict[str, dict],
    ga4_page_data: dict[str, dict] | None,
    db_path: Path,
) -> None:
    before_snapshot = event.get("before_snapshot") or {}
    resource_path = before_snapshot.get("path", "")

    metrics_after = collect_metrics_for_url(resource_path, gsc_rows, ga4_page_data)
    metrics_before = event.get("metrics_before") or {}
    observed_impact = _compute_observed_impact(metrics_before, metrics_after)

    update_geo_event_status(
        shop=shop,
        event_id=int(event["id"]),
        status="measured",
        measurement_status=f"{window_key}_measured",
        metrics_after=metrics_after,
        observed_impact=observed_impact,
        notes=f"Auto-measured at {window_key} window",
        db_path=db_path,
    )


def _refresh_gsc_if_needed(shop: str) -> dict[str, Any]:
    try:
        from app.gsc.client import ensure_fresh_gsc  # noqa: PLC0415

        return ensure_fresh_gsc(shop)
    except Exception as exc:
        logger.warning("measurement_loop: GSC refresh failed for %s: %s", shop, exc)
        return {"status": "failed", "error": str(exc)}


def _load_ga4_page_data(shop: str) -> dict[str, dict] | None:
    try:
        from app.ga4.client import GA4Client  # noqa: PLC0415
        from app.ga4.queries import get_organic_by_page  # noqa: PLC0415

        property_id = _get_ga4_property_id(shop)
        if not property_id:
            return None
        client = GA4Client(property_id=property_id)
        return get_organic_by_page(client, days=30)
    except Exception as exc:
        logger.warning("measurement_loop: GA4 load failed for %s: %s", shop, exc)
        return None


def _get_ga4_property_id(shop: str) -> str | None:
    """Read the GA4 property ID for a shop from the settings store."""
    try:
        from app.ga4.settings import load_ga4_settings  # noqa: PLC0415

        settings = load_ga4_settings(shop)
        return settings.get("property_id") if settings else None
    except Exception:
        return None


def build_verdict_summary(
    report: dict[str, Any],
    locale: str = "fr",
) -> str:
    """Generate a one-liner merchant-facing summary of the impact verdict.

    Args:
        report: Output of ``build_event_report`` from impact_report.py.
        locale: "fr" or "en".
    """
    gsc = report.get("gsc") or {}
    scores = report.get("scores") or {}

    imp_before = gsc.get("impressions_before")
    imp_after = gsc.get("impressions_after")
    clk_before = gsc.get("clicks_before")
    clk_after = gsc.get("clicks_after")
    pos_before = gsc.get("position_before")
    pos_after = gsc.get("position_after")
    geo_delta = scores.get("geo_delta")

    has_after = imp_after is not None

    if not has_after:
        if locale == "en":
            return "Awaiting data — next measurement window coming soon."
        return "En attente de données — prochaine fenêtre de mesure bientôt."

    parts: list[str] = []

    if imp_before and imp_after and imp_before > 0:
        pct = round((imp_after - imp_before) / imp_before * 100)
        sign = "+" if pct > 0 else ""
        label = "Impressions" if locale == "en" else "Impressions"
        parts.append(f"{label} {sign}{pct} %")

    if clk_before and clk_after and clk_before > 0:
        pct = round((clk_after - clk_before) / clk_before * 100)
        sign = "+" if pct > 0 else ""
        label = "Clicks" if locale == "en" else "Clics"
        parts.append(f"{label} {sign}{pct} %")

    if pos_before and pos_after and pos_before > 0 and pos_after > 0:
        if locale == "en":
            parts.append(f"position {pos_before:.1f} → {pos_after:.1f}")
        else:
            parts.append(f"position {pos_before:.1f} → {pos_after:.1f}")

    if geo_delta is not None and geo_delta != 0:
        sign = "+" if geo_delta > 0 else ""
        if locale == "en":
            parts.append(f"GEO score {sign}{geo_delta} pts")
        else:
            parts.append(f"score GEO {sign}{geo_delta} pts")

    if not parts:
        if locale == "en":
            return "No significant change detected yet."
        return "Pas de changement significatif détecté."

    return " — ".join(parts)
