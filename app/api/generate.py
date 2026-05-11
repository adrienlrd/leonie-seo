"""Generate meta tags via LLM — enqueue batch jobs and retrieve results."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.api.deps import ShopContext, get_shop_context
from app.jobs.store import enqueue
from app.llm.meta_store import list_suggestions

router = APIRouter(tags=["generate"])


class GenerateMetaRequest(BaseModel):
    products: list[dict]
    max_workers: int = 10


class GenerateMetaResponse(BaseModel):
    job_id: str
    queued: int
    message: str


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

    # Pre-generate the job ID so it can be embedded in the payload for tracing.
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
