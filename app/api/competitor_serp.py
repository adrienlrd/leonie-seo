"""FastAPI router — dedicated competitor SERP crawl page."""

from __future__ import annotations

import json
import logging
import uuid
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import BackgroundTasks, Depends, HTTPException
from fastapi.routing import APIRouter

from app.api.deps import ShopContext, get_shop_context
from app.market_analysis.competitor_serp_engine import (
    build_config_for_serp_job,
    run_competitor_serp_crawl,
)
from app.paths import data_dir

logger = logging.getLogger(__name__)

router = APIRouter()

_jobs: dict[str, dict[str, Any]] = {}
_DATA_DIR = data_dir()


# ── Persistence ───────────────────────────────────────────────────────────────


def _save_result(shop: str, data: dict[str, Any]) -> None:
    try:
        shop_dir = _DATA_DIR / shop
        shop_dir.mkdir(parents=True, exist_ok=True)
        (shop_dir / "competitor_serp_latest.json").write_text(
            json.dumps(data, ensure_ascii=False), encoding="utf-8"
        )
    except OSError as exc:
        logger.error("Failed to save competitor SERP result for %s: %s", shop, exc)


def _load_result(shop: str) -> dict[str, Any] | None:
    path = _DATA_DIR / shop / "competitor_serp_latest.json"
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


# ── Background task ───────────────────────────────────────────────────────────


def _run_crawl_background(job_id: str, shop: str) -> None:
    try:
        _jobs[job_id]["status"] = "running"
        config = build_config_for_serp_job()
        result = run_competitor_serp_crawl(shop, config)
        _save_result(shop, result)
        _jobs[job_id].update({
            "status": "completed",
            "completed_at": datetime.now(UTC).isoformat(),
            "total_urls_crawled": result.get("total_urls_crawled", 0),
            "keywords_used": result.get("keywords_used", 0),
            "competitor_count": len(result.get("competitors", [])),
        })
    except Exception as exc:  # noqa: BLE001
        logger.exception("Competitor SERP crawl failed for %s", shop)
        _jobs[job_id].update({
            "status": "failed",
            "error": str(exc),
        })


# ── Endpoints ─────────────────────────────────────────────────────────────────


@router.post("/shops/{shop}/competitor-serp/jobs")
async def start_competitor_serp_job(
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
    background_tasks: BackgroundTasks,
) -> dict[str, Any]:
    """Start an async competitor SERP crawl job."""
    job_id = str(uuid.uuid4())
    _jobs[job_id] = {
        "job_id": job_id,
        "shop": ctx.shop,
        "status": "pending",
        "created_at": datetime.now(UTC).isoformat(),
        "completed_at": None,
        "total_urls_crawled": None,
        "keywords_used": None,
        "competitor_count": None,
        "error": None,
    }
    background_tasks.add_task(_run_crawl_background, job_id, ctx.shop)
    return {"job_id": job_id, "status": "pending"}


@router.get("/shops/{shop}/competitor-serp/jobs/{job_id}")
async def get_competitor_serp_job(
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
    job_id: str,
) -> dict[str, Any]:
    """Poll a competitor SERP crawl job."""
    job = _jobs.get(job_id)
    if not job or job.get("shop") != ctx.shop:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.get("/shops/{shop}/competitor-serp/latest")
async def get_competitor_serp_latest(
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
) -> dict[str, Any]:
    """Return the latest competitor SERP crawl result."""
    data = _load_result(ctx.shop)
    if data is None:
        raise HTTPException(status_code=404, detail="No competitor SERP analysis found")
    return data
