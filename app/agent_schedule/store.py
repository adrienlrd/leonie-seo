"""Persistence helpers for the daily GEO agent schedule.

One row per shop in ``agent_schedule_settings``. Mirrors the idioms used by
``app/learning/store.py`` (get_conn, ISO-UTC timestamps, ``db_path`` override).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.db_adapter import DB_PATH, get_conn

_VALID_MODES = ("semi_auto", "auto_apply")


@dataclass(frozen=True)
class AgentScheduleSettings:
    """Daily agent automation configuration for one shop."""

    shop: str
    enabled: bool = False
    mode: str = "semi_auto"
    frequency: str = "daily"
    local_time: str = "08:00"
    timezone: str = "Europe/Paris"
    next_run_at: str | None = None
    last_run_at: str | None = None
    last_run_id: int | None = None
    test_run_at: str | None = None
    last_reanalysis_at: str | None = None
    updated_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "shop": self.shop,
            "enabled": self.enabled,
            "mode": self.mode,
            "frequency": self.frequency,
            "local_time": self.local_time,
            "timezone": self.timezone,
            "next_run_at": self.next_run_at,
            "last_run_at": self.last_run_at,
            "last_run_id": self.last_run_id,
            "test_run_at": self.test_run_at,
            "last_reanalysis_at": self.last_reanalysis_at,
            "updated_at": self.updated_at,
        }


def _bool(value: Any) -> bool:
    return (
        bool(int(value)) if isinstance(value, int | str) and str(value).isdigit() else bool(value)
    )


def _from_row(shop: str, row: dict[str, Any]) -> AgentScheduleSettings:
    return AgentScheduleSettings(
        shop=shop,
        enabled=_bool(row.get("enabled")),
        mode=str(row.get("mode") or "semi_auto"),
        frequency=str(row.get("frequency") or "daily"),
        local_time=str(row.get("local_time") or "08:00"),
        timezone=str(row.get("timezone") or "Europe/Paris"),
        next_run_at=row.get("next_run_at"),
        last_run_at=row.get("last_run_at"),
        last_run_id=(int(row["last_run_id"]) if row.get("last_run_id") is not None else None),
        test_run_at=row.get("test_run_at"),
        last_reanalysis_at=row.get("last_reanalysis_at"),
        updated_at=row.get("updated_at"),
    )


def get_schedule(shop: str, *, db_path: Path | None = None) -> AgentScheduleSettings:
    """Return the schedule for a shop, or a disabled default when absent."""
    path = db_path if db_path is not None else DB_PATH
    with get_conn(path) as conn:
        row = conn.execute(
            "SELECT * FROM agent_schedule_settings WHERE shop = ?",
            (shop,),
        ).fetchone()
    if row is None:
        return AgentScheduleSettings(shop=shop)
    return _from_row(shop, row)


def upsert_schedule(
    shop: str,
    patch: dict[str, Any],
    *,
    db_path: Path | None = None,
) -> AgentScheduleSettings:
    """Update the schedule for a shop, preserving unset fields."""
    current = get_schedule(shop, db_path=db_path)
    mode = str(patch.get("mode", current.mode))
    if mode not in _VALID_MODES:
        mode = current.mode
    settings = AgentScheduleSettings(
        shop=shop,
        enabled=bool(patch.get("enabled", current.enabled)),
        mode=mode,
        frequency=str(patch.get("frequency", current.frequency) or "daily"),
        local_time=str(patch.get("local_time", current.local_time) or "08:00"),
        timezone=str(patch.get("timezone", current.timezone) or "Europe/Paris"),
        next_run_at=patch.get("next_run_at", current.next_run_at),
        last_run_at=patch.get("last_run_at", current.last_run_at),
        last_run_id=patch.get("last_run_id", current.last_run_id),
        test_run_at=patch.get("test_run_at", current.test_run_at),
        last_reanalysis_at=patch.get("last_reanalysis_at", current.last_reanalysis_at),
    )
    now = datetime.now(UTC).isoformat()
    path = db_path if db_path is not None else DB_PATH
    values = (
        settings.enabled,
        settings.mode,
        settings.frequency,
        settings.local_time,
        settings.timezone,
        settings.next_run_at,
        settings.last_run_at,
        settings.last_run_id,
        settings.test_run_at,
        settings.last_reanalysis_at,
        now,
        shop,
    )
    with get_conn(path) as conn:
        exists = conn.execute(
            "SELECT shop FROM agent_schedule_settings WHERE shop = ?",
            (shop,),
        ).fetchone()
        if exists:
            conn.execute(
                """
                UPDATE agent_schedule_settings
                SET enabled = ?, mode = ?, frequency = ?, local_time = ?, timezone = ?,
                    next_run_at = ?, last_run_at = ?, last_run_id = ?, test_run_at = ?,
                    last_reanalysis_at = ?, updated_at = ?
                WHERE shop = ?
                """,
                values,
            )
        else:
            conn.execute(
                """
                INSERT INTO agent_schedule_settings (
                    enabled, mode, frequency, local_time, timezone, next_run_at,
                    last_run_at, last_run_id, test_run_at, last_reanalysis_at, updated_at, shop
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                values,
            )
    return AgentScheduleSettings(**{**settings.__dict__, "updated_at": now})


def list_schedules(*, db_path: Path | None = None) -> list[AgentScheduleSettings]:
    """Return every persisted schedule (enabled or with a pending test run)."""
    path = db_path if db_path is not None else DB_PATH
    with get_conn(path) as conn:
        rows = conn.execute(
            """
            SELECT * FROM agent_schedule_settings
            WHERE enabled = 1 OR enabled = TRUE OR test_run_at IS NOT NULL
            """,
        ).fetchall()
    return [_from_row(str(row["shop"]), row) for row in rows]


def mark_run(
    shop: str,
    *,
    run_id: int | None,
    ran_at: str,
    next_run_at: str | None,
    clear_test: bool,
    db_path: Path | None = None,
) -> None:
    """Record a completed run: stamp last_run_*, advance next_run_at, clear test."""
    now = datetime.now(UTC).isoformat()
    path = db_path if db_path is not None else DB_PATH
    with get_conn(path) as conn:
        if clear_test:
            conn.execute(
                """
                UPDATE agent_schedule_settings
                SET last_run_at = ?, last_run_id = ?, next_run_at = ?,
                    test_run_at = NULL, updated_at = ?
                WHERE shop = ?
                """,
                (ran_at, run_id, next_run_at, now, shop),
            )
        else:
            conn.execute(
                """
                UPDATE agent_schedule_settings
                SET last_run_at = ?, last_run_id = ?, next_run_at = ?, updated_at = ?
                WHERE shop = ?
                """,
                (ran_at, run_id, next_run_at, now, shop),
            )
