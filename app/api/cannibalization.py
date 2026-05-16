"""Keyword cannibalization detection endpoint for embedded Shopify workflows."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.deps import ShopContext, get_shop_context
from scripts.audit.detect_cannibalization import (
    _recommendation,
    detect_cannibal_pairs,
    load_gsc_query_page,
)

router = APIRouter(tags=["cannibalization"])

_DATA_DIR = Path(__file__).parents[2] / "data" / "raw"


@router.get("/api/shops/{shop}/audit/cannibalization")
async def get_cannibalization(
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
    min_impressions: int = 10,
    top: int = 50,
) -> dict:
    """Return keyword cannibalization pairs sorted by severity descending.

    Requires gsc_query_page.csv — produced by the GSC import job.
    Returns available=false when no GSC query data exists yet.
    """
    gsc_path = _DATA_DIR / ctx.shop / "gsc_query_page.csv"
    df = load_gsc_query_page(str(gsc_path))

    if df.empty:
        return {
            "shop": ctx.shop,
            "available": False,
            "total": 0,
            "summary": {"high": 0, "medium": 0, "low": 0},
            "rows": [],
            "message": "Importez vos données Google Search Console pour détecter la cannibalisation.",
        }

    pairs = detect_cannibal_pairs(df, min_impressions=min_impressions)

    summary = {
        "high": sum(1 for r in pairs if r["severity"] >= 0.6),
        "medium": sum(1 for r in pairs if 0.3 <= r["severity"] < 0.6),
        "low": sum(1 for r in pairs if r["severity"] < 0.3),
    }

    rows = [
        {**pair, "recommendation": _recommendation(pair)}
        for pair in pairs[:top]
    ]

    return {
        "shop": ctx.shop,
        "available": True,
        "total": len(pairs),
        "summary": summary,
        "rows": rows,
    }
