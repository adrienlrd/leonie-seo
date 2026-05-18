"""Tests for GEO validation timeline windows."""

from __future__ import annotations

from datetime import UTC, datetime

from app.geo.validation_timeline import build_validation_timeline


def _event(created_at: str, impressions: int = 120) -> dict:
    return {
        "id": 1,
        "snapshot_id": 10,
        "created_at": created_at,
        "resource_type": "product",
        "resource_id": "p1",
        "resource_title": "Harnais",
        "action_type": "enrich_product_facts",
        "status": "applied",
        "measurement_status": "baseline_captured",
        "score_before": 62,
        "status_history": [{"status": "applied", "changed_at": created_at}],
        "metrics_before": {"gsc": {"impressions": impressions}},
        "metrics_after": None,
        "observed_impact": None,
    }


def test_build_validation_timeline_marks_future_windows_pending() -> None:
    result = build_validation_timeline(
        events=[_event("2026-05-01T00:00:00+00:00")],
        now=datetime(2026, 5, 5, tzinfo=UTC),
    )

    windows = result["timelines"][0]["windows"]
    assert windows[0]["status"] == "ready"
    assert windows[1]["status"] == "pending"
    assert result["summary"]["next_due_at"] == "2026-05-08T00:00:00+00:00"


def test_build_validation_timeline_marks_open_window_measuring() -> None:
    result = build_validation_timeline(
        events=[_event("2026-05-01T00:00:00+00:00")],
        now=datetime(2026, 5, 9, tzinfo=UTC),
    )

    assert result["timelines"][0]["windows"][1]["status"] == "measuring"


def test_build_validation_timeline_marks_low_volume_elapsed_window_inconclusive() -> None:
    result = build_validation_timeline(
        events=[_event("2026-05-01T00:00:00+00:00", impressions=10)],
        now=datetime(2026, 6, 15, tzinfo=UTC),
        min_impressions=50,
    )

    j30 = result["timelines"][0]["windows"][2]
    assert j30["status"] == "inconclusive"
    assert result["summary"]["status_counts"]["inconclusive"] >= 1


def test_build_validation_timeline_marks_measured_windows_ready() -> None:
    event = _event("2026-05-01T00:00:00+00:00")
    event["measurement_status"] = "j30_measured"

    result = build_validation_timeline(
        events=[event],
        now=datetime(2026, 6, 15, tzinfo=UTC),
    )

    assert result["timelines"][0]["windows"][2]["status"] == "ready"
