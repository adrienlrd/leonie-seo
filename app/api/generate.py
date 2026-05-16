"""Generate meta tags via LLM — enqueue batch jobs, diff review, approve/reject."""

from __future__ import annotations

import uuid
from dataclasses import asdict
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.api.deps import ShopContext, get_shop_context
from app.api.snapshot_store import load_snapshot_from_file_or_db
from app.jobs.store import enqueue
from app.llm.meta_store import batch_update_status, list_suggestions
from app.llm.review import diff_suggestions
from app.safety import require_shopify_write_allowed

router = APIRouter(tags=["generate"])


# ── Request / response models ─────────────────────────────────────────────────


class GenerateMetaRequest(BaseModel):
    products: list[dict]
    max_workers: int = 10


class GenerateFromSnapshotRequest(BaseModel):
    limit: int = 25
    max_workers: int = 5


class GenerateMetaResponse(BaseModel):
    job_id: str
    queued: int
    message: str


class BulkApplyRequest(BaseModel):
    dry_run: bool = True
    max_per_run: int = 50
    delay: float = 0.5
    confirm_live_write: bool = False


class BlogBriefRequest(BaseModel):
    gaps: list[dict]
    max_workers: int = 3


class CollectionBriefRequest(BaseModel):
    clusters: list[dict]
    max_workers: int = 3


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


@router.post("/api/shops/{shop}/generate/meta/from-snapshot", response_model=GenerateMetaResponse)
async def enqueue_meta_generation_from_snapshot(
    shop: str,
    body: GenerateFromSnapshotRequest,
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
) -> GenerateMetaResponse:
    """Enqueue meta generation from the latest read-only Shopify crawl snapshot."""
    snapshot = load_snapshot_from_file_or_db(ctx.shop, ctx.snapshot_path)
    products = (snapshot or {}).get("products", [])
    if not products:
        raise HTTPException(
            status_code=404, detail="No product snapshot found. Run an audit first."
        )

    limit = max(1, min(body.limit, 100))
    max_workers = max(1, min(body.max_workers, 10))
    selected_products = products[:limit]
    job_id = str(uuid.uuid4())
    enqueue(
        "meta_generation",
        payload={
            "products": selected_products,
            "max_workers": max_workers,
            "job_id": job_id,
        },
        job_id=job_id,
        shop=ctx.shop,
    )
    return GenerateMetaResponse(
        job_id=job_id,
        queued=len(selected_products),
        message=f"{len(selected_products)} products queued for meta generation",
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
            f"{approved} approved automatically, {skipped} kept pending (failed length check)"
        ),
    )


@router.post("/api/shops/{shop}/generate/meta/apply", response_model=GenerateMetaResponse)
async def enqueue_bulk_apply(
    shop: str,
    body: BulkApplyRequest,
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
) -> GenerateMetaResponse:
    """Enqueue a job to apply all approved meta suggestions to Shopify.

    By default runs in dry-run mode — pass dry_run=false to write to Shopify.
    Progress is tracked via the job queue: poll GET /api/jobs/{job_id} for status.

    Args:
        shop: Shopify shop domain.
        body: dry_run (default True), max_per_run (default 50), delay between mutations.
    """
    require_shopify_write_allowed(
        action="bulk_apply",
        dry_run=body.dry_run,
        confirmed=body.confirm_live_write,
    )
    job_id = str(uuid.uuid4())
    enqueue(
        "bulk_apply",
        payload={
            "dry_run": body.dry_run,
            "max_per_run": body.max_per_run,
            "delay": body.delay,
            "confirm_live_write": body.confirm_live_write,
        },
        job_id=job_id,
        shop=shop,
    )
    mode = "dry-run" if body.dry_run else "LIVE"
    return GenerateMetaResponse(
        job_id=job_id,
        queued=body.max_per_run,
        message=f"Bulk apply queued ({mode}, up to {body.max_per_run} suggestions)",
    )


@router.post("/api/shops/{shop}/generate/blog-briefs")
async def generate_blog_briefs_endpoint(
    shop: str,
    body: BlogBriefRequest,
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
) -> list[dict]:
    """Generate SEO blog article briefs for a list of keyword gaps.

    Each brief includes a proposed H1, H2/H3 structure, LSI keywords,
    differentiator angle, E-E-A-T guidance, and internal CTA link.

    Args:
        shop: Shopify shop domain.
        body: gaps — list of keyword gap dicts (from GET /niche/gaps).
              max_workers — LLM concurrency (default 3).
    """
    if not body.gaps:
        raise HTTPException(status_code=422, detail="gaps list must not be empty")

    import asyncio

    from app.llm import get_router
    from app.llm.briefs import generate_blog_briefs

    router_llm = get_router(shop=shop)
    results = await asyncio.to_thread(
        generate_blog_briefs,
        body.gaps,
        router_llm,
        max_workers=body.max_workers,
    )
    return [asdict(r) for r in results]


@router.post("/api/shops/{shop}/generate/collection-briefs")
async def generate_collection_briefs_endpoint(
    shop: str,
    body: CollectionBriefRequest,
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
) -> list[dict]:
    """Generate SEO collection page briefs for a list of product clusters.

    Each brief includes H1, meta title, meta description, intro text,
    LSI keywords, internal link suggestions, and a differentiator angle.

    Args:
        shop: Shopify shop domain.
        body: clusters — list of product cluster dicts (from GET /niche/clusters).
              max_workers — LLM concurrency (default 3).
    """
    if not body.clusters:
        raise HTTPException(status_code=422, detail="clusters list must not be empty")

    import asyncio

    from app.llm import get_router
    from app.llm.briefs import generate_collection_briefs

    router_llm = get_router(shop=shop)
    results = await asyncio.to_thread(
        generate_collection_briefs,
        body.clusters,
        router_llm,
        max_workers=body.max_workers,
    )
    return [asdict(r) for r in results]
