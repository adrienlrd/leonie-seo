"""Technical crawl import API endpoints for embedded Shopify workflows."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, File, UploadFile

from app.api.deps import ShopContext, get_shop_context
from app.crawl.client import analyze_crawl_csv, latest_crawl_status, store_crawl_report

router = APIRouter(tags=["crawl"])


@router.get("/api/shops/{shop}/crawl/status")
async def crawl_status(ctx: Annotated[ShopContext, Depends(get_shop_context)]) -> dict:
    """Return the latest crawl report status for a shop."""
    return {"shop": ctx.shop, **latest_crawl_status(ctx.shop)}


@router.post("/api/shops/{shop}/crawl/upload", status_code=202)
async def crawl_upload(
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
    overview: UploadFile = File(..., description="Screaming Frog 'Internal' overview CSV"),
    redirects: UploadFile | None = File(default=None, description="Screaming Frog 'Response Codes' CSV"),
) -> dict:
    """Parse an uploaded Screaming Frog CSV and return a crawl issue report."""
    overview_bytes = await overview.read()
    redirects_bytes = await redirects.read() if redirects else None

    report = analyze_crawl_csv(overview_bytes, redirects_bytes=redirects_bytes)
    latest_path, timestamped_path = store_crawl_report(ctx.shop, report)

    return {
        "shop": ctx.shop,
        "url_count": report["url_count"],
        "issue_count": report["issue_count"],
        "by_severity": report["by_severity"],
        "latest_path": str(latest_path),
        "timestamped_path": str(timestamped_path),
        "issues": report["issues"][:50],
    }
