"""Tests for the 14/28-day automatic re-analysis cycle (Task 7)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException

from app.agent_schedule import reanalysis, scheduler
from app.agent_schedule.reanalysis import is_reanalysis_due, run_scheduled_reanalysis
from app.agent_schedule.scheduler import run_due_agent_schedules
from app.agent_schedule.store import get_schedule, upsert_schedule
from app.db import init_db
from app.learning.store import update_settings

SHOP = "store.myshopify.com"


def _db(tmp_path: Path) -> Path:
    db = tmp_path / "history.db"
    init_db(db)
    return db


# ── is_reanalysis_due ────────────────────────────────────────────────────────


def test_is_reanalysis_due_when_never_run() -> None:
    assert is_reanalysis_due(None, 28, now=datetime.now(UTC)) is True


def test_is_reanalysis_due_false_within_14_day_window() -> None:
    now = datetime.now(UTC)
    last = (now - timedelta(days=10)).isoformat()
    assert is_reanalysis_due(last, 14, now=now) is False


def test_is_reanalysis_due_true_after_14_day_window() -> None:
    now = datetime.now(UTC)
    last = (now - timedelta(days=15)).isoformat()
    assert is_reanalysis_due(last, 14, now=now) is True


def test_is_reanalysis_due_true_after_1_day_window() -> None:
    now = datetime.now(UTC)
    last = (now - timedelta(days=1, minutes=1)).isoformat()
    assert is_reanalysis_due(last, 1, now=now) is True


def test_is_reanalysis_due_false_within_1_day_window() -> None:
    now = datetime.now(UTC)
    last = (now - timedelta(hours=2)).isoformat()
    assert is_reanalysis_due(last, 1, now=now) is False


def test_is_reanalysis_due_false_within_28_day_window() -> None:
    now = datetime.now(UTC)
    last = (now - timedelta(days=20)).isoformat()
    assert is_reanalysis_due(last, 28, now=now) is False


def test_is_reanalysis_due_true_after_28_day_window() -> None:
    now = datetime.now(UTC)
    last = (now - timedelta(days=29)).isoformat()
    assert is_reanalysis_due(last, 28, now=now) is True


# ── run_scheduled_reanalysis ─────────────────────────────────────────────────


def test_run_scheduled_reanalysis_runs_pipeline_in_order(tmp_path: Path) -> None:
    db = _db(tmp_path)
    calls: list[str] = []

    with (
        patch.object(
            reanalysis,
            "check_budget",
            return_value={"over_budget": False, "budget_usd": 20.0, "spent_usd": 0.0},
        ),
        patch.object(
            reanalysis,
            "_enqueue_refresh_jobs",
            side_effect=lambda *a, **k: calls.append("enqueue_refresh_jobs"),
        ),
        patch.object(
            reanalysis,
            "run_market_reanalysis",
            side_effect=lambda *a, **k: (calls.append("run_market_reanalysis") or {
                "analyzed_at": "2026-06-10T00:00:00+00:00",
                "analyzed_product_count": 1,
            }),
        ),
        patch.object(reanalysis, "get_plan_for_shop", return_value="pro"),
    ):
        outcome = run_scheduled_reanalysis(SHOP, access_token="shpat_test", db_path=db)

    assert outcome["status"] == "completed"
    assert calls == ["enqueue_refresh_jobs", "run_market_reanalysis"]


def test_run_scheduled_reanalysis_skips_heavy_pipeline_when_over_budget(tmp_path: Path) -> None:
    db = _db(tmp_path)

    with (
        patch.object(
            reanalysis,
            "check_budget",
            return_value={"over_budget": True, "budget_usd": 2.0, "spent_usd": 5.0},
        ),
        patch.object(reanalysis, "get_plan_for_shop", return_value="free"),
        patch.object(reanalysis, "_enqueue_refresh_jobs") as enqueue_jobs,
        patch.object(reanalysis, "run_market_reanalysis") as run_reanalysis,
    ):
        outcome = run_scheduled_reanalysis(SHOP, access_token="shpat_test", db_path=db)

    assert outcome["status"] == "skipped"
    assert outcome["reason"] == "budget_exceeded"
    enqueue_jobs.assert_not_called()
    run_reanalysis.assert_not_called()


def test_run_scheduled_reanalysis_skips_when_no_snapshot_on_disk(tmp_path: Path) -> None:
    db = _db(tmp_path)

    with (
        patch.object(
            reanalysis,
            "check_budget",
            return_value={"over_budget": False, "budget_usd": 20.0, "spent_usd": 0.0},
        ),
        patch.object(reanalysis, "get_plan_for_shop", return_value="pro"),
        patch.object(reanalysis, "_enqueue_refresh_jobs"),
        patch.object(
            reanalysis,
            "run_market_reanalysis",
            side_effect=HTTPException(status_code=404, detail="No crawl data found"),
        ),
    ):
        outcome = run_scheduled_reanalysis(SHOP, access_token="shpat_test", db_path=db)

    assert outcome["status"] == "skipped"
    assert outcome["reason"] == "no_snapshot"


# ── run_due_agent_schedules wiring ───────────────────────────────────────────


def test_run_due_triggers_reanalysis_when_due_and_updates_last_reanalysis_at(
    tmp_path: Path,
) -> None:
    db = _db(tmp_path)
    past = (datetime.now(UTC) - timedelta(minutes=1)).isoformat()
    upsert_schedule(SHOP, {"enabled": True, "next_run_at": past}, db_path=db)

    with (
        patch.object(scheduler, "load_latest_result", return_value={"products": []}),
        patch.object(
            scheduler, "run_learning_cycle", return_value={"run_id": 1, "status": "completed"}
        ),
        patch.object(scheduler, "get_token", return_value={"access_token": "shpat_test"}),
        patch.object(
            scheduler,
            "run_scheduled_reanalysis",
            return_value={"status": "completed", "analyzed_at": "2026-06-10T00:00:00+00:00"},
        ) as run_reanalysis,
    ):
        result = run_due_agent_schedules(db_path=db)

    run_reanalysis.assert_called_once()
    assert result["ran"][0]["reanalysis"]["status"] == "completed"
    schedule = get_schedule(SHOP, db_path=db)
    assert schedule.last_reanalysis_at is not None


def test_run_due_does_not_trigger_reanalysis_when_not_due(tmp_path: Path) -> None:
    db = _db(tmp_path)
    past = (datetime.now(UTC) - timedelta(minutes=1)).isoformat()
    recent_reanalysis = (datetime.now(UTC) - timedelta(days=1)).isoformat()
    upsert_schedule(
        SHOP,
        {"enabled": True, "next_run_at": past, "last_reanalysis_at": recent_reanalysis},
        db_path=db,
    )
    update_settings(SHOP, {"reanalysis_frequency_days": 28}, db_path=db)

    with (
        patch.object(scheduler, "load_latest_result", return_value={"products": []}),
        patch.object(
            scheduler, "run_learning_cycle", return_value={"run_id": 2, "status": "completed"}
        ),
        patch.object(scheduler, "run_scheduled_reanalysis") as run_reanalysis,
    ):
        result = run_due_agent_schedules(db_path=db)

    run_reanalysis.assert_not_called()
    assert result["ran"][0]["reanalysis"] is None
    schedule = get_schedule(SHOP, db_path=db)
    assert schedule.last_reanalysis_at == recent_reanalysis


def test_test_run_forces_reanalysis_even_when_not_due(tmp_path: Path) -> None:
    db = _db(tmp_path)
    past_test = (datetime.now(UTC) - timedelta(minutes=1)).isoformat()
    recent_reanalysis = (datetime.now(UTC) - timedelta(hours=1)).isoformat()
    upsert_schedule(
        SHOP,
        {"test_run_at": past_test, "last_reanalysis_at": recent_reanalysis},
        db_path=db,
    )
    update_settings(SHOP, {"reanalysis_frequency_days": 28}, db_path=db)

    with (
        patch.object(scheduler, "load_latest_result", return_value={"products": []}),
        patch.object(
            scheduler, "run_learning_cycle", return_value={"run_id": 9, "status": "completed"}
        ),
        patch.object(scheduler, "get_token", return_value={"access_token": "shpat_test"}),
        patch.object(
            scheduler,
            "run_scheduled_reanalysis",
            return_value={"status": "completed", "analyzed_at": "2026-06-10T00:00:00+00:00"},
        ) as run_reanalysis,
    ):
        result = run_due_agent_schedules(db_path=db)

    # Forced by the one-shot test even though the 28-day window has not elapsed.
    run_reanalysis.assert_called_once()
    assert result["ran"][0]["kind"] == "test"
    assert result["ran"][0]["reanalysis"]["status"] == "completed"


def test_run_due_skips_reanalysis_without_access_token_but_runs_learning_cycle(
    tmp_path: Path,
) -> None:
    db = _db(tmp_path)
    past = (datetime.now(UTC) - timedelta(minutes=1)).isoformat()
    upsert_schedule(SHOP, {"enabled": True, "next_run_at": past}, db_path=db)

    with (
        patch.object(scheduler, "load_latest_result", return_value={"products": []}),
        patch.object(
            scheduler, "run_learning_cycle", return_value={"run_id": 3, "status": "completed"}
        ) as run_cycle,
        patch.object(scheduler, "get_token", return_value=None),
    ):
        result = run_due_agent_schedules(db_path=db)

    run_cycle.assert_called_once()
    assert result["ran"][0]["reanalysis"] == {"status": "skipped", "reason": "no_access_token"}
    schedule = get_schedule(SHOP, db_path=db)
    assert schedule.last_reanalysis_at is None


def test_run_due_runs_learning_cycle_even_when_reanalysis_budget_exceeded(
    tmp_path: Path,
) -> None:
    db = _db(tmp_path)
    past = (datetime.now(UTC) - timedelta(minutes=1)).isoformat()
    upsert_schedule(SHOP, {"enabled": True, "next_run_at": past}, db_path=db)

    with (
        patch.object(scheduler, "load_latest_result", return_value={"products": []}),
        patch.object(
            scheduler, "run_learning_cycle", return_value={"run_id": 4, "status": "completed"}
        ) as run_cycle,
        patch.object(scheduler, "get_token", return_value={"access_token": "shpat_test"}),
        patch.object(
            scheduler,
            "run_scheduled_reanalysis",
            return_value={"status": "skipped", "reason": "budget_exceeded"},
        ),
    ):
        result = run_due_agent_schedules(db_path=db)

    run_cycle.assert_called_once()
    assert result["ran"][0]["reanalysis"]["reason"] == "budget_exceeded"
    schedule = get_schedule(SHOP, db_path=db)
    # Budget skip must not advance the cadence — retried on the next due tick.
    assert schedule.last_reanalysis_at is None
