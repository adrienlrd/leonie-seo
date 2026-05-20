"""Technical crawl import API endpoints for embedded Shopify workflows."""

from __future__ import annotations

from typing import Annotated
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile

from app.api.deps import ShopContext, get_shop_context
from app.api.snapshot_store import load_snapshot_from_file_or_db
from app.crawl.client import analyze_crawl_csv, latest_crawl_status, store_crawl_report
from app.crawl.findings import (
    findings_from_mini_results,
    findings_from_sitemap_diff,
    store_crawl_findings,
    summarize_findings,
)
from app.crawl.mini import crawl_urls
from app.crawl.robots import fetch_robots_txt
from app.crawl.sitemap import (
    default_sitemap_urls,
    diff_sitemap_snapshot,
    fetch_sitemap_urls,
    snapshot_public_urls,
)

router = APIRouter(tags=["crawl"])


def _snapshot_base_url(snapshot: dict, shop: str) -> str:
    shop_data = snapshot.get("shop") or {}
    primary = shop_data.get("primaryDomain") or {}
    candidate = primary.get("url") or shop_data.get("domain") or shop_data.get("myshopifyDomain") or shop
    value = str(candidate).strip().rstrip("/")
    if not value.startswith(("http://", "https://")):
        value = f"https://{value}"
    return value


def _same_host(url: str, base_url: str) -> bool:
    return urlparse(url).netloc == urlparse(base_url).netloc


def _prioritized_urls(snapshot: dict, base_url: str, sitemap_urls: list[str], max_urls: int) -> list[str]:
    snapshot_urls = sorted(snapshot_public_urls(snapshot, base_url))
    same_host_sitemap_urls = [url for url in sitemap_urls if _same_host(url, base_url)]
    return list(dict.fromkeys(snapshot_urls + same_host_sitemap_urls))[:max_urls]


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


@router.post("/api/shops/{shop}/crawl/l3", status_code=202)
async def crawl_l3(
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
    max_urls: int = Query(default=50, ge=1, le=1000),
    throttle_seconds: float = Query(default=1.0, ge=0, le=10),
) -> dict:
    """Run a capped native Crawl L3 audit without requiring Screaming Frog."""
    snapshot = load_snapshot_from_file_or_db(ctx.shop, ctx.snapshot_path)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="Snapshot introuvable. Lancez un audit SEO d'abord.")

    base_url = _snapshot_base_url(snapshot, ctx.shop)
    robots = fetch_robots_txt(base_url)
    sitemap_entries = fetch_sitemap_urls(default_sitemap_urls(base_url, robots.sitemaps))
    sitemap_diff = diff_sitemap_snapshot(sitemap_entries, snapshot, base_url)
    candidate_urls = _prioritized_urls(snapshot, base_url, [entry.loc for entry in sitemap_entries], max_urls)
    mini_results = crawl_urls(
        candidate_urls,
        robots=robots,
        max_urls=max_urls,
        throttle_seconds=throttle_seconds,
    )

    findings = findings_from_sitemap_diff(sitemap_diff) + findings_from_mini_results(mini_results)
    persisted_count = store_crawl_findings(ctx.shop, findings)
    summary = summarize_findings(findings)
    report = {
        "source": "crawl_l3",
        "base_url": base_url,
        "url_count": len(candidate_urls),
        "sitemap_url_count": len(sitemap_entries),
        "mini_crawl_url_count": len(mini_results),
        "persisted_findings": persisted_count,
        **summary,
        "issues": findings[:100],
    }
    latest_path, timestamped_path = store_crawl_report(ctx.shop, report)

    return {
        "shop": ctx.shop,
        "available": True,
        "latest_path": str(latest_path),
        "timestamped_path": str(timestamped_path),
        **report,
    }
