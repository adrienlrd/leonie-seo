"""Job queue API endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path
from pydantic import BaseModel

from app.api.deps import get_authenticated_shop
from app.jobs.handlers import registered_queues
from app.jobs.store import enqueue, get_job, list_jobs

router = APIRouter(prefix="/api", tags=["jobs"])


class EnqueueRequest(BaseModel):
    queue: str
    payload: dict = {}
    delay_seconds: int = 0
    max_retries: int = 3
    priority: int = 0


@router.post("/jobs", status_code=202)
async def create_job(
    body: EnqueueRequest,
    authenticated_shop: Annotated[str, Depends(get_authenticated_shop)],
) -> dict:
    """Enqueue a background job. Returns job ID immediately (non-blocking).

    The job is scoped to the authenticated shop — the caller cannot enqueue
    jobs for a different tenant. Requires either an internal secret call
    (X-Leonie-Shop + X-Internal-Secret) or a valid Shopify session token.
    """
    if body.queue not in registered_queues():
        raise HTTPException(status_code=400, detail=f"Unknown queue '{body.queue}'")
    job_id = enqueue(
        body.queue,
        body.payload,
        shop=authenticated_shop,
        delay_seconds=body.delay_seconds,
        max_retries=body.max_retries,
        priority=body.priority,
    )
    return {"job_id": job_id, "status": "pending"}


@router.get("/jobs/{job_id}")
async def get_job_status(
    job_id: Annotated[str, Path(description="Job UUID")],
    authenticated_shop: Annotated[str, Depends(get_authenticated_shop)],
) -> dict:
    """Return the current status and result of a job.

    Enforces shop ownership: a 404 is returned both when the job doesn't exist
    and when it belongs to a different tenant (avoid leaking existence).
    """
    job = get_job(job_id)
    if job is None or job.get("shop") != authenticated_shop:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.get("/shops/{shop}/jobs")
async def list_shop_jobs(
    shop: str,
    authenticated_shop: Annotated[str, Depends(get_authenticated_shop)],
    queue: str | None = None,
    status: str | None = None,
    limit: int = 50,
) -> dict:
    """List recent jobs for a tenant, optionally filtered by queue or status.

    Listing jobs only needs tenant ownership, not a Shopify Admin API token.
    Remix authenticates this route with X-Leonie-Shop + X-Internal-Secret.
    """
    if authenticated_shop != shop:
        raise HTTPException(status_code=403, detail="Authenticated shop does not match path")
    jobs = list_jobs(shop=authenticated_shop, queue=queue, status=status, limit=min(limit, 200))
    return {"shop": authenticated_shop, "jobs": jobs, "count": len(jobs)}
