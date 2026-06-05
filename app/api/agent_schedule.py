"""Daily GEO agent schedule API endpoints.

Thin layer over ``app.agent_schedule.scheduler``. Mirrors the conventions of
``app/api/learning.py`` (shop context dependency, asyncio.to_thread for blocking
DB work, DB_PATH injection for tests).
"""

from __future__ import annotations

import asyncio
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.agent_schedule.evaluation import evaluate_agent_effectiveness
from app.agent_schedule.export import build_export
from app.agent_schedule.scheduler import (
    disable,
    enable_daily,
    run_due_agent_schedules,
    schedule_status,
    schedule_test_in_5_min,
)
from app.api.deps import ShopContext, get_shop_context, require_internal_secret
from app.db_adapter import DB_PATH

router = APIRouter(prefix="/api", tags=["agent-schedule"])

_LOCAL_TIME_RE = r"^([01]\d|2[0-3]):[0-5]\d$"


class AgentScheduleSettingsRequest(BaseModel):
    enabled: bool = True
    mode: Literal["semi_auto", "auto_apply"] = "semi_auto"
    frequency: Literal["daily"] = "daily"
    local_time: str = Field(default="08:00", pattern=_LOCAL_TIME_RE)
    timezone: str = Field(default="Europe/Paris", min_length=1, max_length=64)


@router.get("/shops/{shop}/agent-schedule/status")
async def get_agent_schedule_status(
    shop: str,
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
) -> dict[str, Any]:
    """Return the schedule, next/last run and a summary of recent runs."""
    return {"available": True, **schedule_status(ctx.shop, db_path=DB_PATH)}


@router.put("/shops/{shop}/agent-schedule/settings")
async def put_agent_schedule_settings(
    shop: str,
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
    body: AgentScheduleSettingsRequest,
) -> dict[str, Any]:
    """Enable or update the daily automation. Disabling is a no-op here.

    Use POST /disable to turn the agent off.
    """
    if not body.enabled:
        settings = disable(ctx.shop, db_path=DB_PATH)
    else:
        settings = enable_daily(
            ctx.shop,
            mode=body.mode,
            local_time=body.local_time,
            timezone=body.timezone,
            db_path=DB_PATH,
        )
    return {"shop": ctx.shop, "schedule": settings.to_dict()}


@router.post("/shops/{shop}/agent-schedule/disable")
async def disable_agent_schedule(
    shop: str,
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
) -> dict[str, Any]:
    """Disable the daily agent. Manual runs stay available."""
    settings = disable(ctx.shop, db_path=DB_PATH)
    return {"shop": ctx.shop, "schedule": settings.to_dict()}


@router.post("/shops/{shop}/agent-schedule/test-in-5-min")
async def test_agent_in_5_min(
    shop: str,
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
) -> dict[str, Any]:
    """Queue a single test run ~5 minutes out. Does not enable the daily agent."""
    settings = schedule_test_in_5_min(ctx.shop, db_path=DB_PATH)
    return {"shop": ctx.shop, "schedule": settings.to_dict()}


@router.get("/shops/{shop}/agent-schedule/effectiveness")
async def get_agent_effectiveness(
    shop: str,
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
) -> dict[str, Any]:
    """Return whether the agent improves SEO and GEO, with how-to-improve advice."""
    return await asyncio.to_thread(evaluate_agent_effectiveness, ctx.shop, db_path=DB_PATH)


@router.get("/shops/{shop}/agent-schedule/export")
async def export_agent_schedule(
    shop: str,
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
) -> dict[str, Any]:
    """Return a full JSON export of agent settings, runs, proposals and metrics."""
    return await asyncio.to_thread(build_export, ctx.shop, db_path=DB_PATH)


@router.post(
    "/internal/agent-schedule/run-due",
    dependencies=[Depends(require_internal_secret)],
)
async def run_due_internal() -> dict[str, Any]:
    """Run every shop whose daily schedule (or one-shot test) is due.

    Reusable cron entrypoint. A Render/Railway/Vercel Cron job may call this every
    5-10 minutes: it is cheap (a DB scan) and only triggers an actual learning
    cycle when a shop is genuinely due, never more than once per cooldown window.
    """
    return await asyncio.to_thread(run_due_agent_schedules, db_path=DB_PATH)
