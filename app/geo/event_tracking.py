"""Optimization event tracking built from persisted GEO snapshots."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.db_adapter import DB_PATH
from app.geo.ledger import create_geo_event, update_geo_event_status
from app.geo.optimization_snapshots import get_optimization_snapshot


def _score_before(snapshot: dict[str, Any]) -> int:
    readiness = snapshot.get("readiness_score")
    if isinstance(readiness, int):
        return readiness
    scores = snapshot.get("snapshot", {}).get("scores", {})
    return int(scores.get("readiness_score", 0) or 0)


def create_event_from_optimization_snapshot(
    *,
    shop: str,
    snapshot_id: int,
    status: str = "planned",
    job_id: str | None = None,
    estimated_impact: dict[str, Any] | None = None,
    notes: str | None = None,
    db_path: Path | None = None,
) -> int:
    """Create a traceable impact event from a before-optimization snapshot."""
    path = db_path if db_path is not None else DB_PATH
    snapshot = get_optimization_snapshot(shop=shop, snapshot_id=snapshot_id, db_path=path)
    if snapshot is None:
        raise ValueError(f"Optimization snapshot {snapshot_id} not found")

    event_type = "applied_optimization" if status == "applied" else "planned_optimization"
    return create_geo_event(
        shop=shop,
        event_type=event_type,
        resource_type=snapshot["resource_type"],
        resource_id=snapshot["resource_id"],
        resource_title=snapshot["resource_title"],
        action_type=snapshot["action_type"],
        status=status,
        source=snapshot["source"],
        job_id=job_id,
        snapshot_id=snapshot_id,
        hypothesis=snapshot["hypothesis"],
        score_before=_score_before(snapshot),
        measurement_status="baseline_captured",
        before_snapshot=snapshot["snapshot"],
        metrics_before=snapshot["metrics"],
        estimated_impact=estimated_impact or {},
        notes=notes or snapshot.get("notes"),
        db_path=path,
    )


def mark_optimization_event_status(
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
    """Update the event status and keep the optimization history auditable."""
    path = db_path if db_path is not None else DB_PATH
    return update_geo_event_status(
        shop=shop,
        event_id=event_id,
        status=status,
        score_after=score_after,
        measurement_status=measurement_status,
        after_snapshot=after_snapshot,
        metrics_after=metrics_after,
        observed_impact=observed_impact,
        notes=notes,
        db_path=path,
    )
