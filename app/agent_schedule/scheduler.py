"""Daily GEO agent scheduler.

Orchestration only: decides *when* ``run_learning_cycle`` runs per shop. The
actual agent and its LLM calls live in the learning cycle, which already honours
``merchant_learning_settings`` (mode + enabled). This module never duplicates the
agent.

Budget safety (explicit merchant requirement): the periodic tick that calls
``run_due_agent_schedules`` only does a cheap DB scan; an actual learning cycle
(LLM cost) fires at most once per day per shop, and a cooldown
(``AGENT_SCHEDULE_MIN_INTERVAL_HOURS``, default 20h) blocks any runaway loop even
if ``next_run_at`` is misconfigured or the internal endpoint is hammered.
"""

from __future__ import annotations

import logging
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.agent_schedule.store import (
    AgentScheduleSettings,
    get_schedule,
    list_schedules,
    mark_run,
    upsert_schedule,
)
from app.learning.scheduler import run_learning_cycle
from app.learning.store import get_settings, list_runs, update_settings
from app.market_analysis.jobs import load_latest_result

logger = logging.getLogger(__name__)

_DEFAULT_TIMEZONE = "Europe/Paris"
_DEFAULT_MIN_INTERVAL_HOURS = 20.0

# Shops with an in-flight cycle. Prevents two overlapping ticks/cron calls from
# running the same shop (and double-spending the LLM budget) at the same time.
_RUNNING: set[str] = set()


def _min_interval_hours() -> float:
    raw = os.getenv("AGENT_SCHEDULE_MIN_INTERVAL_HOURS")
    if not raw:
        return _DEFAULT_MIN_INTERVAL_HOURS
    try:
        value = float(raw)
    except ValueError:
        return _DEFAULT_MIN_INTERVAL_HOURS
    return value if value >= 0 else _DEFAULT_MIN_INTERVAL_HOURS


def _zone(timezone: str) -> ZoneInfo:
    try:
        return ZoneInfo(timezone or _DEFAULT_TIMEZONE)
    except (ZoneInfoNotFoundError, ValueError):
        return ZoneInfo(_DEFAULT_TIMEZONE)


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed


def _parse_local_time(local_time: str) -> tuple[int, int]:
    try:
        hh, mm = local_time.split(":", 1)
        hour = max(0, min(23, int(hh)))
        minute = max(0, min(59, int(mm)))
        return hour, minute
    except (ValueError, AttributeError):
        return 8, 0


def compute_next_run_at(
    local_time: str,
    timezone: str,
    *,
    now: datetime | None = None,
) -> str:
    """Return the next daily run instant (ISO UTC) for the given local time.

    Today if the local time is still ahead, tomorrow otherwise.
    """
    tz = _zone(timezone)
    current = now or datetime.now(UTC)
    local_now = current.astimezone(tz)
    hour, minute = _parse_local_time(local_time)
    candidate = local_now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if candidate <= local_now:
        candidate += timedelta(days=1)
    return candidate.astimezone(UTC).isoformat()


def _due(value: str | None, now: datetime) -> bool:
    parsed = _parse_iso(value)
    return parsed is not None and parsed <= now


def run_due_agent_schedules(
    *,
    now: datetime | None = None,
    db_path: Path | None = None,
) -> dict[str, Any]:
    """Run the learning cycle for every shop that is due.

    Cheap to call frequently: it only triggers ``run_learning_cycle`` (LLM cost)
    when a shop is genuinely due, and never twice within the cooldown window.
    """
    current = now or datetime.now(UTC)
    min_interval = timedelta(hours=_min_interval_hours())
    ran: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    checked = 0

    for schedule in list_schedules(db_path=db_path):
        shop = schedule.shop
        is_test_due = _due(schedule.test_run_at, current)
        is_daily_due = schedule.enabled and _due(schedule.next_run_at, current)
        if not (is_test_due or is_daily_due):
            continue
        checked += 1

        # Cooldown protects the API budget on the recurring path. An explicit
        # one-shot test bypasses it (it cannot loop: test_run_at is consumed).
        if is_daily_due and not is_test_due:
            last = _parse_iso(schedule.last_run_at)
            if last is not None and (current - last) < min_interval:
                skipped.append({"shop": shop, "reason": "cooldown"})
                continue

        if load_latest_result(shop) is None:
            skipped.append({"shop": shop, "reason": "no_market_analysis"})
            continue

        if shop in _RUNNING:
            skipped.append({"shop": shop, "reason": "already_running"})
            continue

        _RUNNING.add(shop)
        try:
            result = run_learning_cycle(shop, db_path=db_path)
            run_id = result.get("run_id")
            ran_at = datetime.now(UTC).isoformat()
            next_run_at = (
                compute_next_run_at(schedule.local_time, schedule.timezone, now=current)
                if schedule.enabled
                else schedule.next_run_at
            )
            mark_run(
                shop,
                run_id=run_id,
                ran_at=ran_at,
                next_run_at=next_run_at,
                clear_test=is_test_due,
                db_path=db_path,
            )
            ran.append(
                {
                    "shop": shop,
                    "run_id": run_id,
                    "kind": "test" if is_test_due else "daily",
                    "status": result.get("status"),
                }
            )
        except Exception as exc:  # noqa: BLE001 — report per-shop, never abort the sweep
            errors.append({"shop": shop, "error": str(exc)})
        finally:
            _RUNNING.discard(shop)

    return {"checked": checked, "ran": ran, "skipped": skipped, "errors": errors}


def enable_daily(
    shop: str,
    *,
    mode: str,
    local_time: str,
    timezone: str,
    db_path: Path | None = None,
) -> AgentScheduleSettings:
    """Activate the daily agent and sync the learning mode (source of truth)."""
    next_run_at = compute_next_run_at(local_time, timezone)
    settings = upsert_schedule(
        shop,
        {
            "enabled": True,
            "mode": mode,
            "frequency": "daily",
            "local_time": local_time,
            "timezone": timezone,
            "next_run_at": next_run_at,
        },
        db_path=db_path,
    )
    # Keep merchant_learning_settings consistent so the cycle uses the same mode.
    update_settings(shop, {"enabled": True, "mode": mode}, db_path=db_path)
    return settings


def disable(shop: str, *, db_path: Path | None = None) -> AgentScheduleSettings:
    """Disable the daily agent. Manual learning runs remain available."""
    return upsert_schedule(shop, {"enabled": False, "next_run_at": None}, db_path=db_path)


def schedule_test_in_5_min(
    shop: str,
    *,
    now: datetime | None = None,
    db_path: Path | None = None,
) -> AgentScheduleSettings:
    """Queue a single test run ~5 minutes out. Does NOT enable the daily agent."""
    current = now or datetime.now(UTC)
    test_run_at = (current + timedelta(minutes=5)).isoformat()
    return upsert_schedule(shop, {"test_run_at": test_run_at}, db_path=db_path)


def schedule_status(shop: str, *, db_path: Path | None = None) -> dict[str, Any]:
    """Return the schedule plus a summary of recent learning runs for the UI."""
    schedule = get_schedule(shop, db_path=db_path)
    learning = get_settings(shop, db_path=db_path)
    runs = list_runs(shop, limit=5, db_path=db_path)
    return {
        "shop": shop,
        "enabled": schedule.enabled,
        "mode": schedule.mode,
        "next_run_at": schedule.next_run_at,
        "last_run_at": schedule.last_run_at,
        "last_run_id": schedule.last_run_id,
        "test_run_at": schedule.test_run_at,
        "schedule": schedule.to_dict(),
        "learning_enabled": learning.enabled,
        "recent_runs": runs,
    }
