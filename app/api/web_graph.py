"""Web Graph API — CC-Index competitor coverage and brand signals."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import ShopContext, get_shop_context
from app.niche.brand_signals import compare_competitor_coverage, search_brand_in_urls
from app.niche.web_graph import CCIndexClient, WebGraphError

router = APIRouter(prefix="/api", tags=["web-graph"])


def _build_client() -> CCIndexClient:
    return CCIndexClient()


@router.get("/shops/{shop}/web-graph/competitors")
async def get_competitor_coverage(
    shop: str,
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
    domains: Annotated[
        str,
        Query(description="Comma-separated competitor domains, e.g. miacara.com,zara.com"),
    ],
) -> dict:
    """Return CC-Index crawled page count for a list of competitor domains.

    Page count is a rough proxy for content footprint and site authority.

    Args:
        shop: Shopify shop domain.
        domains: Comma-separated list of competitor hostnames.
    """
    competitor_list = [d.strip().lower() for d in domains.split(",") if d.strip()]
    if not competitor_list:
        raise HTTPException(status_code=422, detail="No valid domains provided.")

    client = _build_client()
    try:
        coverage = compare_competitor_coverage(client, competitor_list)
    except WebGraphError as exc:
        raise HTTPException(status_code=502, detail=f"CC-Index error: {exc}") from exc

    return {
        "shop": shop,
        "crawl": client._cached_crawl,
        "competitors": coverage,
    }


@router.get("/shops/{shop}/web-graph/url-patterns")
async def get_url_patterns(
    shop: str,
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
    domain: Annotated[str, Query(description="Domain to analyse, e.g. miacara.com")],
    limit: Annotated[int, Query(ge=10, le=1000)] = 200,
) -> dict:
    """Return URL path pattern distribution for a domain.

    Groups crawled URLs by first-level path prefix and returns counts.
    Useful for understanding a competitor's content structure.

    Args:
        shop: Shopify shop domain.
        domain: Hostname to analyse.
        limit: Max pages to sample (10–1000, default 200).
    """
    client = _build_client()
    try:
        patterns = client.get_url_patterns(domain.strip().lower(), limit=limit)
    except WebGraphError as exc:
        raise HTTPException(status_code=502, detail=f"CC-Index error: {exc}") from exc

    return {
        "shop": shop,
        "domain": domain,
        "crawl": client._cached_crawl,
        "url_patterns": patterns,
        "total_pages_sampled": sum(patterns.values()),
    }


@router.get("/shops/{shop}/web-graph/brand-signals")
async def get_brand_signals(
    shop: str,
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
    brand_slug: Annotated[
        str,
        Query(description="URL-safe brand identifier, e.g. leoniedelacroix"),
    ],
    limit: Annotated[int, Query(ge=10, le=500)] = 100,
) -> dict:
    """Find third-party pages mentioning a brand slug in their URL.

    Uses CC-Index wildcard search (*brand_slug*) to surface comparison
    articles, retailer pages, and press mentions without parsing HTML.

    Args:
        shop: Shopify shop domain.
        brand_slug: URL-safe brand identifier.
        limit: Max results (10–500, default 100).
    """
    client = _build_client()
    try:
        urls = search_brand_in_urls(client, brand_slug.strip().lower(), limit=limit)
    except WebGraphError as exc:
        raise HTTPException(status_code=502, detail=f"CC-Index error: {exc}") from exc

    return {
        "shop": shop,
        "brand_slug": brand_slug,
        "crawl": client._cached_crawl,
        "mention_count": len(urls),
        "urls": urls,
    }
