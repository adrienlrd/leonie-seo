"""Tests for the daily GEO agent scheduler."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo

from app.agent_schedule import scheduler
from app.agent_schedule.scheduler import (
    compute_next_run_at,
    disable,
    enable_daily,
    run_due_agent_schedules,
    schedule_test_in_5_min,
)
from app.agent_schedule.store import get_schedule, upsert_schedule
from app.db import init_db
from app.learning.store import get_settings

SHOP = "store.myshopify.com"


def _db(tmp_path: Path) -> Path:
    db = tmp_path / "history.db"
    init_db(db)
    return db


# ── enable / disable ─────────────────────────────────────────────────────────


def test_enable_daily_enables_and_computes_next_run(tmp_path: Path) -> None:
    db = _db(tmp_path)

    settings = enable_daily(
        SHOP, mode="semi_auto", local_time="08:00", timezone="Europe/Paris", db_path=db
    )

    assert settings.enabled is True
    assert settings.mode == "semi_auto"
    assert settings.next_run_at is not None
    # Learning settings are kept in sync (single source of truth for mode).
    learning = get_settings(SHOP, db_path=db)
    assert learning.enabled is True
    assert learning.mode.value == "semi_auto"


def test_disable_turns_off_and_clears_next_run(tmp_path: Path) -> None:
    db = _db(tmp_path)
    enable_daily(SHOP, mode="semi_auto", local_time="08:00", timezone="Europe/Paris", db_path=db)

    settings = disable(SHOP, db_path=db)

    assert settings.enabled is False
    assert settings.next_run_at is None


# ── next run computation ─────────────────────────────────────────────────────


def test_compute_next_run_at_today_when_time_ahead() -> None:
    tz = "Europe/Paris"
    now = datetime(2026, 6, 5, 6, 0, tzinfo=ZoneInfo(tz)).astimezone(UTC)

    next_run = compute_next_run_at("08:00", tz, now=now)

    parsed = datetime.fromisoformat(next_run)
    local = parsed.astimezone(ZoneInfo(tz))
    assert (local.year, local.month, local.day) == (2026, 6, 5)
    assert (local.hour, local.minute) == (8, 0)


def test_compute_next_run_at_tomorrow_when_time_passed() -> None:
    tz = "Europe/Paris"
    now = datetime(2026, 6, 5, 9, 0, tzinfo=ZoneInfo(tz)).astimezone(UTC)

    next_run = compute_next_run_at("08:00", tz, now=now)

    local = datetime.fromisoformat(next_run).astimezone(ZoneInfo(tz))
    assert (local.year, local.month, local.day) == (2026, 6, 6)
    assert (local.hour, local.minute) == (8, 0)


# ── test-in-5-min ────────────────────────────────────────────────────────────


def test_schedule_test_in_5_min_sets_test_run_at_without_enabling(tmp_path: Path) -> None:
    db = _db(tmp_path)
    now = datetime.now(UTC)

    settings = schedule_test_in_5_min(SHOP, now=now, db_path=db)

    assert settings.enabled is False
    assert settings.test_run_at is not None
    delta = datetime.fromisoformat(settings.test_run_at) - now
    assert timedelta(minutes=4) <= delta <= timedelta(minutes=6)


# ── run_due_agent_schedules ──────────────────────────────────────────────────


def test_run_due_executes_daily_run_once_and_advances_next_run(tmp_path: Path) -> None:
    db = _db(tmp_path)
    past = (datetime.now(UTC) - timedelta(minutes=1)).isoformat()
    upsert_schedule(
        SHOP,
        {"enabled": True, "mode": "semi_auto", "next_run_at": past},
        db_path=db,
    )

    with (
        patch.object(scheduler, "load_latest_result", return_value={"products": []}),
        patch.object(
            scheduler, "run_learning_cycle", return_value={"run_id": 7, "status": "completed"}
        ) as run_cycle,
    ):
        result = run_due_agent_schedules(db_path=db)

    assert run_cycle.call_count == 1
    assert len(result["ran"]) == 1
    assert result["ran"][0]["kind"] == "daily"
    schedule = get_schedule(SHOP, db_path=db)
    assert schedule.last_run_id == 7
    # next_run_at advanced into the future (tomorrow).
    assert datetime.fromisoformat(schedule.next_run_at) > datetime.now(UTC)


def test_run_due_skips_when_disabled(tmp_path: Path) -> None:
    db = _db(tmp_path)
    past = (datetime.now(UTC) - timedelta(minutes=1)).isoformat()
    upsert_schedule(SHOP, {"enabled": False, "next_run_at": past}, db_path=db)

    with (
        patch.object(scheduler, "load_latest_result", return_value={"products": []}),
        patch.object(scheduler, "run_learning_cycle") as run_cycle,
    ):
        result = run_due_agent_schedules(db_path=db)

    run_cycle.assert_not_called()
    assert result["ran"] == []


def test_run_due_skips_when_no_market_analysis(tmp_path: Path) -> None:
    db = _db(tmp_path)
    past = (datetime.now(UTC) - timedelta(minutes=1)).isoformat()
    upsert_schedule(SHOP, {"enabled": True, "next_run_at": past}, db_path=db)

    with (
        patch.object(scheduler, "load_latest_result", return_value=None),
        patch.object(scheduler, "run_learning_cycle") as run_cycle,
    ):
        result = run_due_agent_schedules(db_path=db)

    run_cycle.assert_not_called()
    assert result["skipped"][0]["reason"] == "no_market_analysis"


def test_run_due_cooldown_blocks_second_run(tmp_path: Path) -> None:
    db = _db(tmp_path)
    past = (datetime.now(UTC) - timedelta(minutes=1)).isoformat()
    recent = (datetime.now(UTC) - timedelta(minutes=5)).isoformat()
    # next_run is still in the past (misconfigured) but a run just happened.
    upsert_schedule(
        SHOP,
        {"enabled": True, "next_run_at": past, "last_run_at": recent},
        db_path=db,
    )

    with (
        patch.object(scheduler, "load_latest_result", return_value={"products": []}),
        patch.object(scheduler, "run_learning_cycle") as run_cycle,
    ):
        result = run_due_agent_schedules(db_path=db)

    run_cycle.assert_not_called()
    assert result["skipped"][0]["reason"] == "cooldown"


def test_run_due_executes_test_once_then_clears(tmp_path: Path) -> None:
    db = _db(tmp_path)
    schedule_test_in_5_min(
        SHOP, now=datetime.now(UTC) - timedelta(minutes=6), db_path=db
    )

    with (
        patch.object(scheduler, "load_latest_result", return_value={"products": []}),
        patch.object(
            scheduler, "run_learning_cycle", return_value={"run_id": 3, "status": "completed"}
        ) as run_cycle,
    ):
        first = run_due_agent_schedules(db_path=db)
        second = run_due_agent_schedules(db_path=db)

    assert run_cycle.call_count == 1
    assert first["ran"][0]["kind"] == "test"
    assert second["ran"] == []
    schedule = get_schedule(SHOP, db_path=db)
    assert schedule.test_run_at is None
    # A disabled test run must not enable the daily agent.
    assert schedule.enabled is False
