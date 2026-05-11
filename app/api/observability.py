"""Observability API — LLM usage metrics and budget status."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.deps import ShopContext, get_shop_context
from app.observability.metrics import check_budget, get_shop_metrics

router = APIRouter(tags=["observability"])


@router.get("/api/shops/{shop}/observability/metrics")
async def get_metrics(
    shop: str,
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
    days: Annotated[int, Query(ge=1, le=365)] = 30,
) -> dict:
    """Return aggregated LLM usage metrics for a shop.

    Includes total calls, token consumption, estimated cost in USD,
    average latency, and per-provider breakdown.

    Args:
        shop: Shopify shop domain.
        days: Lookback window in days (1–365, default 30).
    """
    return get_shop_metrics(shop, days=days)


@router.get("/api/shops/{shop}/observability/budget")
async def get_budget_status(
    shop: str,
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
    budget_usd: Annotated[float, Query(gt=0)] = 10.0,
    days: Annotated[int, Query(ge=1, le=365)] = 30,
) -> dict:
    """Return budget consumption status for a shop.

    Returns remaining budget, usage percentage, and an alert string
    when spend exceeds 80% or surpasses the budget ceiling.

    Args:
        shop: Shopify shop domain.
        budget_usd: Monthly budget ceiling in USD (default $10).
        days: Lookback window in days (default 30).
    """
    return check_budget(shop, budget_usd, days=days)
