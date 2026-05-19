"""Tests for the GEO retention milestones tracker (task 123)."""

from __future__ import annotations

from datetime import UTC, datetime

from app.geo.retention_milestones import build_retention_milestones

_NOW = datetime(2026, 5, 19, 12, 0, 0, tzinfo=UTC)


def _event(applied_at: str, status: str = "applied") -> dict:
    return {
        "id": 1,
        "status": status,
        "created_at": applied_at,
        "status_history": [{"status": "applied", "changed_at": applied_at}],
        "metrics_before": {"gsc": {"impressions": 300}},
    }


def test_no_events_returns_has_active_events_false() -> None:
    result = build_retention_milestones([], now=_NOW)

    assert result["has_active_events"] is False
    assert result["milestones"] == []
    assert result["next_milestone"] is None
    assert len(result["retention_message_fr"]) > 0


def test_four_milestones_returned_when_events_present() -> None:
    events = [_event("2026-04-19T10:00:00+00:00")]  # 30 days ago
    result = build_retention_milestones(events, now=_NOW)

    assert result["has_active_events"] is True
    assert len(result["milestones"]) == 4
    labels = [m["label"] for m in result["milestones"]]
    assert labels == ["J+7", "J+30", "J+60", "J+90"]


def test_j7_and_j30_completed_after_30_days() -> None:
    events = [_event("2026-04-19T10:00:00+00:00")]  # 30 days ago
    result = build_retention_milestones(events, now=_NOW)

    by_label = {m["label"]: m for m in result["milestones"]}
    assert by_label["J+7"]["status"] == "completed"
    assert by_label["J+30"]["status"] == "completed"
    assert by_label["J+60"]["status"] in ("upcoming", "active")
    assert by_label["J+90"]["status"] == "upcoming"


def test_next_milestone_is_j60_when_30_days_elapsed() -> None:
    events = [_event("2026-04-19T10:00:00+00:00")]
    result = build_retention_milestones(events, now=_NOW)

    assert result["next_milestone"] is not None
    assert result["next_milestone"]["label"] == "J+60"
    assert result["next_milestone"]["days_remaining"] >= 0


def test_all_milestones_upcoming_when_event_applied_today() -> None:
    events = [_event("2026-05-19T08:00:00+00:00")]
    result = build_retention_milestones(events, now=_NOW)

    statuses = [m["status"] for m in result["milestones"]]
    assert all(s in ("upcoming", "active") for s in statuses)
    assert result["next_milestone"]["label"] == "J+7"


def test_events_reached_count_per_milestone() -> None:
    events = [
        _event("2026-04-19T10:00:00+00:00"),  # 30 days → J+7 ✓, J+30 ✓
        _event("2026-05-12T10:00:00+00:00"),  # 7 days → J+7 ✓, J+30 ✗
    ]
    result = build_retention_milestones(events, now=_NOW)

    by_label = {m["label"]: m for m in result["milestones"]}
    assert by_label["J+7"]["events_reached"] == 2
    assert by_label["J+30"]["events_reached"] == 1
    assert by_label["J+30"]["total_events"] == 2


def test_elapsed_days_and_active_event_count() -> None:
    events = [_event("2026-04-19T10:00:00+00:00")]
    result = build_retention_milestones(events, now=_NOW)

    assert result["active_event_count"] == 1
    assert result["elapsed_days"] == 30
