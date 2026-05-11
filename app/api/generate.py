"""Generate meta tags via LLM — enqueue batch jobs, diff review, approve/reject."""

from __future__ import annotations

import uuid
from dataclasses import asdict
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.api.deps import ShopContext, get_shop_context
from app.jobs.store import enqueue
from app.llm.meta_store import batch_update_status, list_suggestions
from app.llm.review import diff_suggestions

router = APIRouter(tags=["generate"])


# ── Request / response models ─────────────────────────────────────────────────


class GenerateMetaRequest(BaseModel):
    products: list[dict]
    max_workers: int = 10


class GenerateMetaResponse(BaseModel):
    job_id: str
    queued: int
    message: str


class ReviewRequest(BaseModel):
    approve: list[int] = []
    reject: list[int] = []


class ReviewResponse(BaseModel):
    approved: int
    rejected: int


class AutoApproveResponse(BaseModel):
    approved: int
    skipped: int
    message: str


# ── Endpoints ─────────────────────────────────────────────────────────────────


@router.post("/api/shops/{shop}/generate/meta", response_model=GenerateMetaResponse)
async def enqueue_meta_generation(
    shop: str,
    body: GenerateMetaRequest,
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
) -> GenerateMetaResponse:
    """Enqueue an LLM batch job to generate meta tags for the provided products.

    Args:
        shop: Shopify shop domain (path param).
        body: List of Shopify product dicts + optional max_workers override.
        ctx: Resolved shop authentication context.

    Returns:
        job_id to poll via GET /api/jobs/{job_id}, and the number of products queued.
    """
    if not body.products:
        raise HTTPException(status_code=422, detail="products list must not be empty")

    job_id = str(uuid.uuid4())
    enqueue(
        "meta_generation",
        payload={
            "products": body.products,
            "max_workers": body.max_workers,
            "job_id": job_id,
        },
        job_id=job_id,
        shop=shop,
    )

    return GenerateMetaResponse(
        job_id=job_id,
        queued=len(body.products),
        message=f"{len(body.products)} products queued for meta generation",
    )


@router.get("/api/shops/{shop}/generate/meta/results")
async def get_meta_results(
    shop: str,
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
    status: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> list[dict]:
    """Return stored meta suggestions for a shop.

    Args:
        shop: Shopify shop domain.
        status: Optional filter — pending | approved | rejected | error.
        limit: Maximum rows (1–500, default 100).
    """
    return list_suggestions(shop, status=status, limit=limit)


@router.get("/api/shops/{shop}/generate/meta/diff")
async def get_meta_diff(
    shop: str,
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> list[dict]:
    """Return pending suggestions with diff vs current product data and length validation.

    Each item includes:
    - generated_title / generated_description
    - baseline_title (current Shopify product title)
    - title_length_ok / desc_length_ok (50-60 / 140-160 chars)
    - passes_quality_check (both lengths ok + non-empty title)

    Args:
        shop: Shopify shop domain.
        limit: Maximum rows (1–500, default 100).
    """
    pending = list_suggestions(shop, status="pending", limit=limit)
    diffs = diff_suggestions(pending)
    return [asdict(d) for d in diffs]


@router.post("/api/shops/{shop}/generate/meta/review", response_model=ReviewResponse)
async def review_meta_batch(
    shop: str,
    body: ReviewRequest,
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
) -> ReviewResponse:
    """Approve and/or reject suggestions by ID in a single request.

    Args:
        shop: Shopify shop domain.
        body: Lists of suggestion IDs to approve and to reject (may overlap — approve wins).

    Returns:
        Counts of approved and rejected rows.
    """
    if not body.approve and not body.reject:
        raise HTTPException(status_code=422, detail="approve or reject list must not both be empty")

    approved = batch_update_status(body.approve, "approved") if body.approve else 0
    rejected = batch_update_status(body.reject, "rejected") if body.reject else 0

    return ReviewResponse(approved=approved, rejected=rejected)


@router.post("/api/shops/{shop}/generate/meta/auto-approve", response_model=AutoApproveResponse)
async def auto_approve_meta(
    shop: str,
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
    limit: Annotated[int, Query(ge=1, le=500)] = 500,
) -> AutoApproveResponse:
    """Approve all pending suggestions that pass the quality gate (length constraints).

    Only approves suggestions where:
    - generated_title is 50–60 characters
    - generated_description is 140–160 characters

    Suggestions that fail the gate remain pending for manual review.

    Args:
        shop: Shopify shop domain.
        limit: Maximum pending rows to consider (default 500).
    """
    pending = list_suggestions(shop, status="pending", limit=limit)
    diffs = diff_suggestions(pending)

    passing_ids = [d.suggestion_id for d in diffs if d.passes_quality_check]
    approved = batch_update_status(passing_ids, "approved") if passing_ids else 0
    skipped = len(diffs) - len(passing_ids)

    return AutoApproveResponse(
        approved=approved,
        skipped=skipped,
        message=(
            f"{approved} approved automatically, "
            f"{skipped} kept pending (failed length check)"
        ),
    )
