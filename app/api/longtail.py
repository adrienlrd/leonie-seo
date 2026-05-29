"""Long-tail keyword coverage endpoint for embedded Shopify workflows."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import ShopContext, get_shop_context
from app.api.snapshot_store import load_snapshot_from_file_or_db
from app.paths import data_dir
from scripts.audit.analyze_longtail import build_gap_report, load_keywords

router = APIRouter(tags=["longtail"])

_DATA_DIR = data_dir()
_KEYWORDS_PATH = Path(__file__).parents[2] / "config" / "keywords.yaml"


_GSC_COLUMNS = ["url", "clicks", "impressions", "ctr", "position"]


def _load_gsc_df(shop: str) -> pd.DataFrame:
    path = _DATA_DIR / shop / "gsc_performance.csv"
    if path.exists():
        try:
            df = pd.read_csv(path)
            # Ensure required columns exist even if file is partial
            for col in _GSC_COLUMNS:
                if col not in df.columns:
                    df[col] = 0
            return df
        except Exception:
            pass
    return pd.DataFrame(columns=_GSC_COLUMNS)


@router.get("/api/shops/{shop}/audit/longtail")
async def get_longtail(
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
    top: int = 50,
) -> dict:
    """Return long-tail keyword coverage: ranking / on-site / gap classification.

    Requires keywords.yaml config and a Shopify snapshot.
    GSC data is optional — enriches position/impressions when available.
    """
    if not _KEYWORDS_PATH.exists():
        raise HTTPException(
            status_code=404,
            detail="keywords.yaml not found. Add config/keywords.yaml to enable long-tail analysis.",
        )

    snapshot = load_snapshot_from_file_or_db(ctx.shop, ctx.snapshot_path)
    if snapshot is None:
        raise HTTPException(
            status_code=404,
            detail="No Shopify snapshot found. Run an SEO audit first.",
        )

    keywords_by_cat = load_keywords(str(_KEYWORDS_PATH))
    products = snapshot.get("products", [])
    collections = snapshot.get("collections", [])
    gsc_df = _load_gsc_df(ctx.shop)

    report = build_gap_report(keywords_by_cat, gsc_df, products, collections)

    total = len(report)
    counts = {"ranking": 0, "on_site": 0, "gap": 0}
    for row in report:
        counts[row["status"]] = counts.get(row["status"], 0) + 1

    return {
        "shop": ctx.shop,
        "available": True,
        "total": total,
        "gsc_connected": not gsc_df.empty,
        "summary": counts,
        "rows": report[:top],
    }
