"""Impact API — estimated ROI per modified URL."""

from __future__ import annotations

import json
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import ShopContext, get_shop_context
from app.impact.report import build_impact_report

router = APIRouter(prefix="/api", tags=["impact"])


def _load_snapshot(ctx: ShopContext) -> dict:
    path = ctx.snapshot_path
    if not path.exists():
        raise HTTPException(
            status_code=404,
            detail="No crawl data found. Run 'leonie-seo audit crawl' first.",
        )
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError) as exc:
        raise HTTPException(status_code=500, detail=f"Snapshot unreadable: {exc}") from exc


@router.get("/shops/{shop}/impact")
async def get_impact(
    shop: str,
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
    days: Annotated[int, Query(ge=1, le=365)] = 30,
    conversion_rate: Annotated[float, Query(gt=0, le=1)] = 0.02,
    aov: Annotated[float, Query(gt=0)] = 50.0,
    position_improvement: Annotated[float, Query(ge=0.5, le=10.0)] = 2.0,
) -> dict:
    """Return estimated SEO ROI for all modified URLs in the last N days.

    Estimates are based on a standard organic CTR curve applied to GSC impressions.
    Position before is approximated as current_position + position_improvement.

    Args:
        shop: Shopify shop domain.
        days: Lookback window for applied changes (1–365, default 30).
        conversion_rate: Organic conversion rate fraction (default 0.02 = 2%).
        aov: Average order value in currency units (default 50.0).
        position_improvement: Assumed SERP positions gained from changes (default 2).
    """
    snapshot = _load_snapshot(ctx)
    return build_impact_report(
        shop,
        snapshot,
        days=days,
        position_improvement=position_improvement,
        conversion_rate=conversion_rate,
        aov=aov,
    )
