"""Validation timeline for GEO optimization impact windows."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

MILESTONES = [
    {"key": "j0", "days": 0, "label": "J+0", "purpose": "Optimization applied; baseline starts."},
    {"key": "j14", "days": 14, "label": "J+14", "purpose": "Intermediate learning signal."},
    {"key": "j28", "days": 28, "label": "J+28", "purpose": "Primary validation window."},
    {"key": "j60", "days": 60, "label": "J+60", "purpose": "Long-term historical signal."},
]

MEASURABLE_STATUSES = {"applied", "measured", "rolled_back"}


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _applied_at(event: dict[str, Any]) -> datetime | None:
    history = event.get("status_history") or []
    for entry in history:
        if entry.get("status") in MEASURABLE_STATUSES:
            parsed = _parse_datetime(str(entry.get("changed_at") or ""))
            if parsed is not None:
                return parsed
    if event.get("status") in MEASURABLE_STATUSES:
        return _parse_datetime(str(event.get("created_at") or ""))
    return None


def _has_measurement(event: dict[str, Any], milestone_key: str) -> bool:
    measurement_status = str(event.get("measurement_status") or "").lower()
    if milestone_key in measurement_status:
        return True
    if event.get("metrics_after") or event.get("observed_impact"):
        return True
    return False


def _baseline_impressions(event: dict[str, Any]) -> int:
    metrics = event.get("metrics_before") or {}
    gsc = metrics.get("gsc") or {}
    try:
        return int(gsc.get("impressions") or 0)
    except (TypeError, ValueError):
        return 0


def _window_status(
    *,
    event: dict[str, Any],
    milestone_key: str,
    due_at: datetime,
    now: datetime,
    min_impressions: int,
) -> str:
    if milestone_key == "j0":
        return "ready"
    if now < due_at:
        return "pending"
    if _has_measurement(event, milestone_key):
        return "ready"
    if now < due_at + timedelta(days=3):
        return "measuring"
    if _baseline_impressions(event) < min_impressions:
        return "inconclusive"
    return "ready"


def _window_message(status: str, milestone_key: str) -> str:
    if status == "pending":
        return "Wait for enough time to pass before reading this window."
    if status == "measuring":
        return "The window has opened; collect data before drawing conclusions."
    if status == "inconclusive":
        return "Not enough baseline volume for a confident read."
    if milestone_key == "j14":
        return "Use as an intermediate signal; confidence is capped."
    if milestone_key == "j28":
        return "This is the primary validation window for learning."
    if milestone_key == "j60":
        return "This window is retained as a long-term historical read."
    return "Baseline started."


def build_validation_timeline(
    *,
    events: list[dict[str, Any]],
    now: datetime | None = None,
    event_id: int | None = None,
    min_impressions: int = 50,
) -> dict[str, Any]:
    """Build J+14/J+28/J+60 validation windows for optimization events."""
    current = (now or datetime.now(UTC)).astimezone(UTC)
    measurable_events = [
        event
        for event in events
        if event.get("status") in MEASURABLE_STATUSES
        and (event_id is None or int(event.get("id", 0)) == event_id)
    ]

    timelines = []
    status_counts = {"pending": 0, "measuring": 0, "ready": 0, "inconclusive": 0}
    next_due_at: datetime | None = None
    for event in measurable_events:
        applied = _applied_at(event)
        if applied is None:
            continue

        windows = []
        for milestone in MILESTONES:
            due_at = applied + timedelta(days=int(milestone["days"]))
            status = _window_status(
                event=event,
                milestone_key=str(milestone["key"]),
                due_at=due_at,
                now=current,
                min_impressions=min_impressions,
            )
            status_counts[status] += 1
            if status in {"pending", "measuring"} and (next_due_at is None or due_at < next_due_at):
                next_due_at = due_at
            windows.append(
                {
                    "key": milestone["key"],
                    "label": milestone["label"],
                    "days_after_apply": milestone["days"],
                    "due_at": due_at.isoformat(),
                    "status": status,
                    "purpose": milestone["purpose"],
                    "message": _window_message(status, str(milestone["key"])),
                }
            )

        timelines.append(
            {
                "event_id": event["id"],
                "snapshot_id": event.get("snapshot_id"),
                "resource_type": event["resource_type"],
                "resource_id": event["resource_id"],
                "resource_title": event["resource_title"],
                "action_type": event["action_type"],
                "status": event["status"],
                "measurement_status": event.get("measurement_status"),
                "applied_at": applied.isoformat(),
                "baseline": {
                    "score_before": event.get("score_before"),
                    "impressions": _baseline_impressions(event),
                },
                "windows": windows,
            }
        )

    return {
        "summary": {
            "events_considered": len(measurable_events),
            "timelines_built": len(timelines),
            "status_counts": status_counts,
            "next_due_at": next_due_at.isoformat() if next_due_at else None,
            "time_note": "SEO/GEO validation uses J+14 as an intermediate signal and J+28 as the primary learning window.",
            "min_impressions": min_impressions,
        },
        "timelines": timelines,
    }
