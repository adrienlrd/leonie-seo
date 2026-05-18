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


def _json_loads_list(value: str | None) -> list[dict[str, Any]]:
    if not value:
        return []
    try:
        loaded = json.loads(value)
    except json.JSONDecodeError:
        return []
    if not isinstance(loaded, list):
        return []
    return [item for item in loaded if isinstance(item, dict)]


def _status_history_entry(status: str, created_at: str, note: str | None = None) -> dict[str, Any]:
    entry: dict[str, Any] = {"status": status, "changed_at": created_at}
    if note:
        entry["note"] = note
    return entry


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
    snapshot_id: int | None = None,
    hypothesis: str | None = None,
    score_before: int | None = None,
    score_after: int | None = None,
    measurement_status: str = "not_started",
    status_history: list[dict[str, Any]] | None = None,
    after_snapshot: dict[str, Any] | None = None,
    metrics_after: dict[str, Any] | None = None,
    observed_impact: dict[str, Any] | None = None,
    notes: str | None = None,
    db_path: Path | None = None,
) -> int:
    """Create one GEO impact ledger event and return its ID."""
    path = db_path if db_path is not None else DB_PATH
    now = datetime.now(UTC).isoformat()
    history = status_history or [_status_history_entry(status, now)]
    with get_conn(path) as conn:
        conn.execute(
            """
            INSERT INTO geo_impact_events (
                shop, created_at, event_type, resource_type, resource_id, resource_title,
                action_type, status, source, job_id, snapshot_id, hypothesis,
                score_before, score_after, measurement_status, status_history,
                before_snapshot, after_snapshot, metrics_before, metrics_after, estimated_impact,
                observed_impact, notes
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                snapshot_id,
                hypothesis,
                score_before,
                score_after,
                measurement_status,
                json.dumps(history, ensure_ascii=False, sort_keys=True),
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
                "snapshot_id": row["snapshot_id"],
                "hypothesis": row["hypothesis"],
                "score_before": row["score_before"],
                "score_after": row["score_after"],
                "measurement_status": row["measurement_status"],
                "status_history": _json_loads_list(row["status_history"]),
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


def update_geo_event_status(
    *,
    shop: str,
    event_id: int,
    status: str,
    score_after: int | None = None,
    measurement_status: str | None = None,
    after_snapshot: dict[str, Any] | None = None,
    metrics_after: dict[str, Any] | None = None,
    observed_impact: dict[str, Any] | None = None,
    notes: str | None = None,
    db_path: Path | None = None,
) -> bool:
    """Update one GEO event status while appending a status history entry."""
    path = db_path if db_path is not None else DB_PATH
    changed_at = datetime.now(UTC).isoformat()
    with get_conn(path) as conn:
        row = conn.execute(
            "SELECT status_history, notes FROM geo_impact_events WHERE shop = ? AND id = ?",
            (shop, event_id),
        ).fetchone()
        if row is None:
            return False

        history_raw = row["status_history"]
        try:
            history_loaded = json.loads(history_raw) if history_raw else []
        except json.JSONDecodeError:
            history_loaded = []
        history = history_loaded if isinstance(history_loaded, list) else []
        history.append(_status_history_entry(status, changed_at, notes))

        conn.execute(
            """
            UPDATE geo_impact_events
            SET status = ?,
                score_after = COALESCE(?, score_after),
                measurement_status = COALESCE(?, measurement_status),
                after_snapshot = COALESCE(?, after_snapshot),
                metrics_after = COALESCE(?, metrics_after),
                observed_impact = COALESCE(?, observed_impact),
                notes = COALESCE(?, notes),
                status_history = ?
            WHERE shop = ? AND id = ?
            """,
            (
                status,
                score_after,
                measurement_status,
                _json_dumps(after_snapshot),
                _json_dumps(metrics_after),
                _json_dumps(observed_impact),
                notes,
                json.dumps(history, ensure_ascii=False, sort_keys=True),
                shop,
                event_id,
            ),
        )
    return True
