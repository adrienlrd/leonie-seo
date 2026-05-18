"""GEO impact ledger storage and summaries."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.db_adapter import DB_PATH, get_conn


def _json_dumps(value: dict[str, Any] | None) -> str | None:
    if value is None:
        return None
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _json_loads(value: str | None) -> dict[str, Any] | None:
    if not value:
        return None
    try:
        loaded = json.loads(value)
    except json.JSONDecodeError:
        return None
    return loaded if isinstance(loaded, dict) else None


def create_geo_event(
    *,
    shop: str,
    event_type: str,
    resource_type: str,
    resource_id: str,
    resource_title: str,
    action_type: str,
    before_snapshot: dict[str, Any],
    metrics_before: dict[str, Any],
    estimated_impact: dict[str, Any],
    status: str = "planned",
    source: str = "geo",
    job_id: str | None = None,
    hypothesis: str | None = None,
    after_snapshot: dict[str, Any] | None = None,
    metrics_after: dict[str, Any] | None = None,
    observed_impact: dict[str, Any] | None = None,
    notes: str | None = None,
    db_path: Path | None = None,
) -> int:
    """Create one GEO impact ledger event and return its ID."""
    path = db_path if db_path is not None else DB_PATH
    now = datetime.now(UTC).isoformat()
    with get_conn(path) as conn:
        conn.execute(
            """
            INSERT INTO geo_impact_events (
                shop, created_at, event_type, resource_type, resource_id, resource_title,
                action_type, status, source, job_id, hypothesis, before_snapshot,
                after_snapshot, metrics_before, metrics_after, estimated_impact,
                observed_impact, notes
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                shop,
                now,
                event_type,
                resource_type,
                resource_id,
                resource_title,
                action_type,
                status,
                source,
                job_id,
                hypothesis,
                _json_dumps(before_snapshot) or "{}",
                _json_dumps(after_snapshot),
                _json_dumps(metrics_before) or "{}",
                _json_dumps(metrics_after),
                _json_dumps(estimated_impact) or "{}",
                _json_dumps(observed_impact),
                notes,
            ),
        )
        row = conn.execute(
            """
            SELECT id
            FROM geo_impact_events
            WHERE shop = ? AND created_at = ? AND resource_id = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (shop, now, resource_id),
        ).fetchone()
        return int((row or {}).get("id", 0))


def list_geo_events(
    shop: str,
    *,
    limit: int = 50,
    offset: int = 0,
    status: str | None = None,
    db_path: Path | None = None,
) -> dict[str, Any]:
    """List GEO impact events for one shop."""
    path = db_path if db_path is not None else DB_PATH
    where = "WHERE shop = ?"
    params: list[Any] = [shop]
    if status:
        where += " AND status = ?"
        params.append(status)

    with get_conn(path) as conn:
        total_row = conn.execute(
            f"SELECT COUNT(*) AS total FROM geo_impact_events {where}",
            params,
        ).fetchone()
        rows = conn.execute(
            f"""
            SELECT *
            FROM geo_impact_events
            {where}
            ORDER BY created_at DESC, id DESC
            LIMIT ? OFFSET ?
            """,
            params + [limit, offset],
        ).fetchall()

    events = []
    for row in rows:
        events.append(
            {
                "id": row["id"],
                "shop": row["shop"],
                "created_at": row["created_at"],
                "event_type": row["event_type"],
                "resource_type": row["resource_type"],
                "resource_id": row["resource_id"],
                "resource_title": row["resource_title"],
                "action_type": row["action_type"],
                "status": row["status"],
                "source": row["source"],
                "job_id": row["job_id"],
                "hypothesis": row["hypothesis"],
                "before_snapshot": _json_loads(row["before_snapshot"]) or {},
                "after_snapshot": _json_loads(row["after_snapshot"]),
                "metrics_before": _json_loads(row["metrics_before"]) or {},
                "metrics_after": _json_loads(row["metrics_after"]),
                "estimated_impact": _json_loads(row["estimated_impact"]) or {},
                "observed_impact": _json_loads(row["observed_impact"]),
                "notes": row["notes"],
            }
        )

    return {
        "total": int((total_row or {}).get("total", 0)),
        "limit": limit,
        "offset": offset,
        "events": events,
    }


def summarize_geo_events(shop: str, *, db_path: Path | None = None) -> dict[str, Any]:
    """Return compact status and impact summary for one shop."""
    data = list_geo_events(shop, limit=500, db_path=db_path)
    events = data["events"]
    by_status: dict[str, int] = {}
    estimated_revenue = 0.0
    observed_revenue = 0.0
    for event in events:
        status = event["status"]
        by_status[status] = by_status.get(status, 0) + 1
        estimated_revenue += float(event["estimated_impact"].get("revenue_estimate", 0) or 0)
        if event["observed_impact"]:
            observed_revenue += float(event["observed_impact"].get("revenue", 0) or 0)

    return {
        "total_events": len(events),
        "by_status": by_status,
        "estimated_revenue": round(estimated_revenue, 2),
        "observed_revenue": round(observed_revenue, 2),
        "measurement_note": "Observed impact is recorded only after measurement windows such as J+7/J+30/J+60.",
    }
