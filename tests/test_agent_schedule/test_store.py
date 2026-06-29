"""Tests for the agent schedule store, incl. the Postgres-safe list query."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from app.agent_schedule.store import list_schedules, upsert_schedule
from app.db import init_db


def _db(tmp_path: Path) -> Path:
    db = tmp_path / "history.db"
    init_db(db)
    return db


def test_list_schedules_returns_enabled_and_test_run_entries(tmp_path: Path) -> None:
    db = _db(tmp_path)
    upsert_schedule("enabled.myshopify.com", {"enabled": True}, db_path=db)
    upsert_schedule(
        "test.myshopify.com",
        {"enabled": False, "test_run_at": datetime.now(UTC).isoformat()},
        db_path=db,
    )
    upsert_schedule("disabled.myshopify.com", {"enabled": False}, db_path=db)

    shops = {s.shop for s in list_schedules(db_path=db)}

    # `WHERE enabled OR test_run_at IS NOT NULL` must work on both SQLite and
    # Postgres (no `enabled = 1` integer comparison against a boolean column).
    assert shops == {"enabled.myshopify.com", "test.myshopify.com"}
