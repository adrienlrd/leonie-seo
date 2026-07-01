"""Clicks (Google organic + AI referral) per validated resource since its last validation.

Feeds the Analyse page: under each validated product/blog title, show the number
of Google + AI clicks accumulated since ``latest_applied_at``. GA4 is the primary,
near-real-time source (organic channel + AI referral hosts). When GA4 is not
connected we fall back to the aggregated GSC cache (Google only, ~28 d, delayed).

Results are cached to disk with a short TTL so the frontend can poll cheaply.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

from app.ga4.queries import get_ai_referrals_by_page_daily, get_organic_by_page_daily
from app.geo.ledger import list_geo_events
from app.impact.report import _find_gsc_file, _parse_gsc_csv

logger = logging.getLogger(__name__)

_CACHE_TTL_SECONDS = 300
_WINDOW_DAYS = 28


def _cache_path(shop: str) -> Path:
    root = Path(__file__).resolve().parents[2] / "data" / "raw" / shop
    return root / "clicks_since_validation.json"


def _extract_applied_at(event: dict[str, Any]) -> str:
    for entry in event.get("status_history") or []:
        if entry.get("status") in {"applied", "measured"}:
            return entry.get("changed_at") or event.get("created_at", "")
    return event.get("created_at", "")


def _normalise_path(value: str) -> str:
    """Strip query string + trailing slash so GA4 pagePath and ledger path compare."""
    path = (value or "").split("?", 1)[0].split("#", 1)[0]
    return path.rstrip("/")


def _resource_validation_index(shop: str, db_path: Path | None) -> dict[str, dict[str, Any]]:
    """Per-resource latest validation date + path, from the applied/measured ledger."""
    events = list_geo_events(shop, limit=200, status="applied", db_path=db_path)["events"]
    events.extend(list_geo_events(shop, limit=200, status="measured", db_path=db_path)["events"])

    index: dict[str, dict[str, Any]] = {}
    for event in events:
        rid = event["resource_id"]
        date_key = _extract_applied_at(event)[:10]
        if not date_key:
            continue
        entry = index.get(rid)
        if entry is None:
            before = event.get("before_snapshot") or {}
            entry = index[rid] = {
                "resource_id": rid,
                "resource_type": event["resource_type"],
                "resource_title": event["resource_title"],
                "resource_path": before.get("path", ""),
                "latest_applied_at": date_key,
            }
        elif date_key > entry["latest_applied_at"]:
            entry["latest_applied_at"] = date_key
    return index


def _sum_since(daily_by_path: dict[str, dict[str, int]], resource_path: str, since: str) -> int:
    """Sum a {path: {date: value}} map for one resource, counting dates >= since."""
    target = _normalise_path(resource_path)
    if not target:
        return 0
    total = 0
    for path, by_date in daily_by_path.items():
        if _normalise_path(path) != target:
            continue
        total += sum(v for d, v in by_date.items() if d >= since)
    return total


def _merged_daily_for_path(
    organic: dict[str, dict[str, int]],
    ai: dict[str, dict[str, int]],
    resource_path: str,
) -> dict[str, int]:
    """Merge organic + AI daily maps into a single {date: total} for one resource path."""
    target = _normalise_path(resource_path)
    merged: dict[str, int] = {}
    if not target:
        return merged
    for source in (organic, ai):
        for path, by_date in source.items():
            if _normalise_path(path) != target:
                continue
            for d, v in by_date.items():
                merged[d] = merged.get(d, 0) + v
    return merged


def _build_series(
    organic: dict[str, dict[str, int]],
    ai: dict[str, dict[str, int]],
    resource_path: str,
    since: str,
    today: date,
) -> list[dict[str, Any]]:
    """28-day daily Google+AI series from ``since``; future days carry total=None."""
    merged = _merged_daily_for_path(organic, ai, resource_path)
    start = date.fromisoformat(since)
    series: list[dict[str, Any]] = []
    for i in range(_WINDOW_DAYS):
        day_date = start + timedelta(days=i)
        iso = day_date.isoformat()
        future = day_date > today
        series.append(
            {
                "day": i + 1,
                "date": iso,
                "total": None if future else merged.get(iso, 0),
                "future": future,
            }
        )
    return series


def _build_ga4_client(shop: str):
    """Return an authenticated GA4Client or None when GA4 is not usable for this shop."""
    from app.ga4.client import GA4Client  # noqa: PLC0415
    from app.ga4.oauth import get_credentials  # noqa: PLC0415
    from app.shop_config_store import get_shop_config  # noqa: PLC0415

    creds = get_credentials(shop)
    if creds is not None:
        property_id = get_shop_config(shop, "ga4_property_id")
        return GA4Client(property_id, token=creds.token) if property_id else None

    import os  # noqa: PLC0415

    property_id = os.getenv("GA4_PROPERTY_ID")
    return GA4Client(property_id) if property_id else None


def _gsc_clicks_by_url(shop: str) -> dict[str, dict]:
    gsc_file = _find_gsc_file(shop)
    return _parse_gsc_csv(gsc_file.read_text()) if gsc_file else {}


def _gsc_clicks_for_path(gsc_rows: dict[str, dict], resource_path: str) -> int:
    target = _normalise_path(resource_path)
    if not target:
        return 0
    for url, row in gsc_rows.items():
        if _normalise_path(url).endswith(target):
            return int(row.get("clicks", 0) or 0)
    return 0


def compute_clicks_since_validation(
    shop: str,
    *,
    db_path: Path | None = None,
    force: bool = False,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Clicks (Google + AI) per validated resource since its last validation.

    Returns::

        {"ga4_ready": bool, "computed_at": iso, "resources": {rid: {...}}}

    where each resource entry is
    ``{google, ai, total, since, source}`` (``ai`` is None in GSC fallback).
    """
    now = now or datetime.now(UTC)

    if not force:
        cached = _read_cache(shop, now)
        if cached is not None:
            return cached

    index = _resource_validation_index(shop, db_path)
    if not index:
        return _finalize(shop, {"ga4_ready": False, "computed_at": now.isoformat(), "resources": {}})

    lookback_start = min(e["latest_applied_at"] for e in index.values())

    client = _build_ga4_client(shop)
    if client is not None:
        try:
            organic = get_organic_by_page_daily(client, start_date=lookback_start)
            ai = get_ai_referrals_by_page_daily(client, start_date=lookback_start)
        except Exception as exc:  # GA4 transient/auth error — degrade to GSC, do not fail the page
            logger.warning("GA4 clicks-since-validation failed for %s: %s", shop, exc)
            client = None
        else:
            resources = {}
            for rid, e in index.items():
                since = e["latest_applied_at"]
                g = _sum_since(organic, e["resource_path"], since)
                a = _sum_since(ai, e["resource_path"], since)
                resources[rid] = {
                    "google": g,
                    "ai": a,
                    "total": g + a,
                    "since": since,
                    "source": "ga4",
                    "series": _build_series(organic, ai, e["resource_path"], since, now.date()),
                }
            return _finalize(
                shop,
                {"ga4_ready": True, "computed_at": now.isoformat(), "resources": resources},
            )

    # Fallback: aggregated GSC cache (Google only, delayed, no per-date window).
    gsc_rows = _gsc_clicks_by_url(shop)
    resources = {}
    for rid, e in index.items():
        g = _gsc_clicks_for_path(gsc_rows, e["resource_path"])
        resources[rid] = {
            "google": g,
            "ai": None,
            "total": g,
            "since": e["latest_applied_at"],
            "source": "gsc",
            "series": [],
        }
    return _finalize(
        shop,
        {"ga4_ready": False, "computed_at": now.isoformat(), "resources": resources},
    )


def _read_cache(shop: str, now: datetime) -> dict[str, Any] | None:
    path = _cache_path(shop)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text())
        computed_at = datetime.fromisoformat(data["computed_at"])
    except (ValueError, KeyError, OSError):
        return None
    if (now - computed_at).total_seconds() > _CACHE_TTL_SECONDS:
        return None
    return data


def _finalize(shop: str, payload: dict[str, Any]) -> dict[str, Any]:
    path = _cache_path(shop)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload))
    except OSError as exc:  # cache is best-effort; never block the response on disk
        logger.warning("Could not write clicks cache for %s: %s", shop, exc)
    return payload
