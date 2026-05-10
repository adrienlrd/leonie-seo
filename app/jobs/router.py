"""Job queue API endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, HTTPException, Path
from pydantic import BaseModel

from app.jobs.handlers import registered_queues
from app.jobs.store import enqueue, get_job, list_jobs

router = APIRouter(prefix="/api", tags=["jobs"])


class EnqueueRequest(BaseModel):
    queue: str
    payload: dict = {}
    shop: str | None = None
    delay_seconds: int = 0
    max_retries: int = 3
    priority: int = 0


@router.post("/jobs", status_code=202)
async def create_job(body: EnqueueRequest) -> dict:
    """Enqueue a background job. Returns job ID immediately (non-blocking)."""
    if body.queue not in registered_queues():
        raise HTTPException(status_code=400, detail=f"Unknown queue '{body.queue}'")
    job_id = enqueue(
        body.queue,
        body.payload,
        shop=body.shop,
        delay_seconds=body.delay_seconds,
        max_retries=body.max_retries,
        priority=body.priority,
    )
    return {"job_id": job_id, "status": "pending"}


@router.get("/jobs/{job_id}")
async def get_job_status(
    job_id: Annotated[str, Path(description="Job UUID")],
) -> dict:
    """Return the current status and result of a job."""
    job = get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.get("/shops/{shop}/jobs")
async def list_shop_jobs(
    shop: Annotated[str, Path(description="Shop domain")],
    queue: str | None = None,
    status: str | None = None,
    limit: int = 50,
) -> dict:
    """List recent jobs for a tenant, optionally filtered by queue or status."""
    jobs = list_jobs(shop=shop, queue=queue, status=status, limit=min(limit, 200))
    return {"shop": shop, "jobs": jobs, "count": len(jobs)}
