"""PageSpeed Insights API endpoints for embedded Shopify workflows."""

from __future__ import annotations

import os
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.deps import ShopContext, get_shop_context
from app.jobs.store import enqueue
from app.pagespeed.client import latest_pagespeed_status, priority_urls_for_shop

router = APIRouter(tags=["pagespeed"])


class PageSpeedImportRequest(BaseModel):
    urls: list[str] | None = None
    max_urls: int = Field(default=5, ge=1, le=20)
    site_url: str | None = None


@router.get("/api/shops/{shop}/pagespeed/status")
async def pagespeed_status(ctx: Annotated[ShopContext, Depends(get_shop_context)]) -> dict:
    """Return PageSpeed freshness, scores and alerts for a shop."""
    status = latest_pagespeed_status(ctx.shop)
    return {
        "shop": ctx.shop,
        "configured": bool(os.getenv("PAGESPEED_API_KEY")),
        "targets": priority_urls_for_shop(ctx.shop, max_urls=5),
        **status,
    }


@router.post("/api/shops/{shop}/pagespeed/import", status_code=202)
async def pagespeed_import(
    body: PageSpeedImportRequest,
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
) -> dict:
    """Enqueue a PageSpeed import job for priority shop URLs."""
    if not os.getenv("PAGESPEED_API_KEY"):
        raise HTTPException(status_code=409, detail="PAGESPEED_API_KEY is not configured")
    job_id = enqueue(
        "pagespeed_import",
        {
            "urls": body.urls,
            "max_urls": body.max_urls,
            "site_url": body.site_url,
        },
        shop=ctx.shop,
        max_retries=2,
    )
    return {"job_id": job_id, "status": "pending"}
