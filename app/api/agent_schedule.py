"""Daily GEO agent schedule API endpoints.

Thin layer over ``app.agent_schedule.scheduler``. Mirrors the conventions of
``app/api/learning.py`` (shop context dependency, asyncio.to_thread for blocking
DB work, DB_PATH injection for tests).
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field

from app.agent_schedule.evaluation import evaluate_agent_effectiveness
from app.agent_schedule.export import build_export
from app.agent_schedule.reanalysis import run_scheduled_reanalysis
from app.agent_schedule.scheduler import (
    disable,
    enable_daily,
    run_due_agent_schedules,
    schedule_status,
    schedule_test_in_1h,
    schedule_test_in_5_min,
)
from app.agent_schedule.store import upsert_schedule
from app.api.deps import ShopContext, get_shop_context, require_internal_secret
from app.billing.quotas import QuotaExceeded, auto_analysis_allowed, check_quota, record_usage
from app.db_adapter import DB_PATH
from app.market_analysis.jobs import create_job, get_job, update_job

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["agent-schedule"])

_LOCAL_TIME_RE = r"^([01]\d|2[0-3]):[0-5]\d$"


def _require_auto_analysis(shop: str) -> None:
    """402 when the shop's plan does not include the automatic agent."""
    if not auto_analysis_allowed(shop):
        raise HTTPException(
            status_code=402,
            detail={"error": "quota_exceeded", "kind": "auto_analysis", "plan": "free", "upgrade": "pro"},
        )


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
        _require_auto_analysis(ctx.shop)
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
    _require_auto_analysis(ctx.shop)
    settings = schedule_test_in_5_min(ctx.shop, db_path=DB_PATH)
    return {"shop": ctx.shop, "schedule": settings.to_dict()}


@router.post("/shops/{shop}/agent-schedule/test-in-1h")
async def test_agent_in_1h(
    shop: str,
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
) -> dict[str, Any]:
    """Queue a single test run ~1 hour out, forcing a full re-analysis + auto-publish.

    Lets the merchant verify the whole automation loop without waiting for the
    recurring cadence. Does not enable the daily agent.
    """
    _require_auto_analysis(ctx.shop)
    settings = schedule_test_in_1h(ctx.shop, db_path=DB_PATH)
    return {"shop": ctx.shop, "schedule": settings.to_dict()}


def _run_reanalysis_job(
    job_id: str,
    shop: str,
    access_token: str,
    selection: dict[str, list[str]] | None = None,
) -> None:
    """Background worker: run the scheduled re-analysis and record the job outcome.

    A full catalog re-analysis takes minutes, so it must run as a background job
    (started via `run-and-publish`, polled via `run-and-publish/{job_id}`) to
    avoid the request timing out while the analysis is still running.

    ``selection`` (per-product ``{product_id: [fields]}``) comes from the
    re-analysis popup and decides what auto-publish writes; when absent the
    persisted per-product checkbox selection is honored instead.
    """
    try:
        outcome = run_scheduled_reanalysis(
            shop, access_token=access_token, db_path=DB_PATH, selection=selection
        )
        # Record the completion so the dashboard history + calendar reflect it
        # (mirrors the scheduled path in scheduler._maybe_run_reanalysis).
        if outcome.get("status") == "completed":
            upsert_schedule(
                shop, {"last_reanalysis_at": datetime.now(UTC).isoformat()}, db_path=DB_PATH
            )
        update_job(
            job_id,
            status="completed",
            analyzed_at=outcome.get("analyzed_at"),
            analyzed_product_count=outcome.get("analyzed_product_count") or 0,
            reanalysis_status=outcome.get("status"),
            reanalysis_reason=outcome.get("reason"),
            auto_publish=outcome.get("auto_publish"),
        )
    except Exception as exc:  # noqa: BLE001 — surface the failure to the poller
        logger.exception("Scheduled re-analysis job %s failed for %s", job_id, shop)
        update_job(job_id, status="error", error=str(exc))


class RunAndPublishRequest(BaseModel):
    selection: dict[str, list[str]] | None = None


@router.post("/shops/{shop}/agent-schedule/run-and-publish")
async def run_and_publish_now(
    shop: str,
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
    background_tasks: BackgroundTasks,
    body: RunAndPublishRequest | None = None,
) -> dict[str, Any]:
    """Start a fresh full re-analysis + auto-publish as a background job.

    Reuses the scheduled re-analysis pipeline (fresh analysis → persist →
    auto-publish), respecting the LLM budget. Returns a ``job_id`` to poll via
    ``GET run-and-publish/{job_id}``; the analysis keeps running server-side even
    if the merchant navigates away.

    An optional ``selection`` (per-product ``{product_id: [fields]}``, from the
    re-analysis popup) decides exactly what auto-publish writes.
    """
    if not ctx.access_token:
        raise HTTPException(status_code=401, detail="Missing Shopify access token")
    _require_auto_analysis(ctx.shop)
    try:
        check_quota(ctx.shop, "analysis")
    except QuotaExceeded as exc:
        raise HTTPException(status_code=402, detail=exc.payload()) from exc
    record_usage(ctx.shop, "analysis")
    selection = body.selection if body is not None else None
    job_id = create_job(ctx.shop)
    update_job(job_id, status="running")
    background_tasks.add_task(_run_reanalysis_job, job_id, ctx.shop, ctx.access_token, selection)
    return {"shop": ctx.shop, "job_id": job_id}


@router.get("/shops/{shop}/agent-schedule/run-and-publish/{job_id}")
async def get_run_and_publish_job(
    shop: str,
    job_id: str,
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
) -> dict[str, Any]:
    """Return the status of a re-analysis job started via ``run-and-publish``."""
    job = get_job(job_id)
    if job is None or job.get("shop") != ctx.shop:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


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
