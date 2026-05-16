"""PageSpeed Insights API endpoints for embedded Shopify workflows."""

from __future__ import annotations

import os
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.api.deps import ShopContext, get_shop_context
from app.jobs.store import enqueue
from app.pagespeed.client import latest_pagespeed_status, priority_urls_for_shop
from app.shop_config_store import delete_shop_config, get_shop_config, set_shop_config

router = APIRouter(tags=["pagespeed"])

_CONFIG_KEY = "pagespeed_api_key"


def _effective_api_key(shop: str) -> str | None:
    """Return the API key for a shop: DB value takes priority over env var."""
    return get_shop_config(shop, _CONFIG_KEY) or os.getenv("PAGESPEED_API_KEY") or None


class PageSpeedImportRequest(BaseModel):
    urls: list[str] | None = None
    max_urls: int = Field(default=5, ge=1, le=20)
    site_url: str | None = None


class PageSpeedConfigRequest(BaseModel):
    api_key: str = Field(min_length=1)


@router.get("/api/shops/{shop}/pagespeed/status")
async def pagespeed_status(ctx: Annotated[ShopContext, Depends(get_shop_context)]) -> dict:
    """Return PageSpeed freshness, scores and alerts for a shop."""
    key_in_db = get_shop_config(ctx.shop, _CONFIG_KEY)
    key_in_env = os.getenv("PAGESPEED_API_KEY")
    key_source = "db" if key_in_db else ("env" if key_in_env else None)
    status = latest_pagespeed_status(ctx.shop)
    return {
        "shop": ctx.shop,
        "configured": key_source is not None,
        "key_source": key_source,
        "targets": priority_urls_for_shop(ctx.shop, max_urls=5),
        **status,
    }


@router.post("/api/shops/{shop}/pagespeed/configure")
async def pagespeed_configure(
    body: PageSpeedConfigRequest,
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
) -> dict:
    """Store a PageSpeed API key for this shop (overrides env var)."""
    set_shop_config(ctx.shop, _CONFIG_KEY, body.api_key)
    return {"configured": True, "key_source": "db"}


@router.delete("/api/shops/{shop}/pagespeed/configure")
async def pagespeed_configure_delete(
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
) -> dict:
    """Remove the DB-stored PageSpeed API key (falls back to env var if set)."""
    delete_shop_config(ctx.shop, _CONFIG_KEY)
    return {"configured": bool(os.getenv("PAGESPEED_API_KEY")), "key_source": "env" if os.getenv("PAGESPEED_API_KEY") else None}


@router.post("/api/shops/{shop}/pagespeed/import", status_code=202)
async def pagespeed_import(
    body: PageSpeedImportRequest,
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
) -> dict:
    """Enqueue a PageSpeed import job for priority shop URLs.

    Works without an API key (lower quota). Pass a key via /configure for higher limits.
    """
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
