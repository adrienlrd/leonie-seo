"""GA4 organic funnel API — sessions, conversions, revenue per URL."""

from __future__ import annotations

import os
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import ShopContext, get_shop_context
from app.ga4.client import GA4Client, GA4Error
from app.ga4.funnel import build_funnel, summarize_funnel
from app.ga4.queries import get_organic_by_page
from app.impact.report import _find_gsc_file, _parse_gsc_csv

router = APIRouter(prefix="/api", tags=["ga4"])


def _build_ga4_client() -> GA4Client:
    property_id = os.getenv("GA4_PROPERTY_ID")
    if not property_id:
        raise HTTPException(
            status_code=503,
            detail="GA4_PROPERTY_ID environment variable not configured.",
        )
    return GA4Client(property_id)


@router.get("/shops/{shop}/ga4/funnel")
async def get_organic_funnel(
    shop: str,
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
    days: Annotated[int, Query(ge=1, le=365)] = 30,
) -> dict:
    """Return the organic search funnel for a shop: impressions → clicks → sessions → conversions → revenue.

    Joins GSC data (from cached snapshot) with GA4 organic data (live API call).

    Args:
        shop: Shopify shop domain.
        days: Lookback window in days (1–365, default 30).
    """
    # Load GSC data from snapshot CSV
    gsc_file = _find_gsc_file(shop)
    if gsc_file is None:
        raise HTTPException(
            status_code=404,
            detail="No GSC data found. Run 'leonie-seo audit gsc' first.",
        )
    gsc_rows = _parse_gsc_csv(gsc_file.read_text())

    # Fetch GA4 organic sessions
    client = _build_ga4_client()
    try:
        ga4_rows = get_organic_by_page(client, days=days)
    except GA4Error as exc:
        raise HTTPException(status_code=502, detail=f"GA4 API error: {exc}") from exc

    funnel = build_funnel(gsc_rows, ga4_rows)
    summary = summarize_funnel(funnel)

    return {
        "shop": shop,
        "days": days,
        "summary": summary,
        "by_url": funnel,
    }


@router.get("/shops/{shop}/ga4/status")
async def get_ga4_status(
    shop: str,
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
) -> dict:
    """Check GA4 integration status (env vars configured, credentials reachable).

    Args:
        shop: Shopify shop domain.
    """
    property_id = os.getenv("GA4_PROPERTY_ID")
    creds_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    return {
        "ga4_property_id_set": bool(property_id),
        "credentials_file_set": bool(creds_path),
        "ready": bool(property_id and creds_path),
    }
