"""Market analysis API — SEO/GEO opportunity analysis per active product (read-only)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.audit import _load_crawl_findings, _load_snapshot, _snapshot_age_days
from app.api.deps import ShopContext, get_shop_context
from app.impact.report import _find_gsc_file, _parse_gsc_csv
from app.market_analysis.engine import run_market_analysis
from app.niche.understanding import get_validated_niche_hypothesis

router = APIRouter(prefix="/api", tags=["market_analysis"])

_DATA_DIR = Path(__file__).parents[2] / "data" / "raw"


def _load_gsc_query_rows(shop: str) -> list[dict[str, Any]]:
    shop_dir = _DATA_DIR / shop
    if not shop_dir.exists():
        return []
    candidates = sorted(shop_dir.glob("gsc_*.json"), reverse=True)
    for path in candidates:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            raw_rows = data if isinstance(data, list) else data.get("rows", [])
            normalised: list[dict[str, Any]] = []
            for row in raw_rows:
                if not isinstance(row, dict):
                    continue
                keys = row.get("keys")
                query = row.get("query") or (keys[0] if isinstance(keys, list) and keys else "")
                normalised.append({
                    "query": query,
                    "impressions": row.get("impressions", 0),
                    "clicks": row.get("clicks", 0),
                    "position": row.get("position", row.get("avg_position", 0)),
                })
            return normalised
        except (json.JSONDecodeError, OSError, KeyError, IndexError):
            continue
    return []


@router.post("/shops/{shop}/market-analysis/run")
async def run_market_analysis_endpoint(
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
    max_products: int = Query(default=10, ge=1, le=20),
) -> dict[str, Any]:
    """Analyse SEO/GEO des produits actifs — lecture seule, aucune écriture Shopify."""
    snapshot = _load_snapshot(ctx)
    products = snapshot.get("products", [])
    shop_info = snapshot.get("shop")
    shop_domain = shop_info.get("domain", ctx.shop) if isinstance(shop_info, dict) else ctx.shop

    niche_hypothesis = get_validated_niche_hypothesis(ctx.shop)
    crawl_findings = _load_crawl_findings(ctx.shop)

    gsc_page_rows: dict[str, dict[str, Any]] = {}
    gsc_path = _find_gsc_file(ctx.shop)
    if gsc_path:
        try:
            gsc_page_rows = _parse_gsc_csv(gsc_path.read_text(encoding="utf-8"))
        except OSError:
            pass

    gsc_query_rows = _load_gsc_query_rows(ctx.shop)

    try:
        result = run_market_analysis(
            products,
            shop_domain,
            gsc_page_rows,
            gsc_query_rows,
            niche_hypothesis=niche_hypothesis,
            crawl_findings=crawl_findings or None,
            max_products=max_products,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Erreur analyse marché : {exc}") from exc

    age = _snapshot_age_days(snapshot)
    return {**result, "snapshot_age_days": age}
