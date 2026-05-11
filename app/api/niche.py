"""Niche Intelligence API — clusters, keyword gaps, full report."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import ShopContext, get_shop_context
from app.niche.engine import run_niche_analysis

router = APIRouter(tags=["niche"])

_DATA_DIR = Path(__file__).parents[2] / "data" / "raw"


def _load_snapshot(shop: str) -> list[dict]:
    """Load the most recent Shopify product snapshot for a shop.

    Returns an empty list if no snapshot is found (non-blocking).
    """
    candidates = sorted(_DATA_DIR.glob("snapshot_*.json"), reverse=True)
    for path in candidates:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            products = data if isinstance(data, list) else data.get("products", [])
            return products
        except (json.JSONDecodeError, OSError):
            continue
    return []


def _load_gsc(shop: str) -> list[dict]:
    """Load the most recent GSC query export for a shop.

    Returns an empty list if no export is found.
    """
    candidates = sorted(_DATA_DIR.glob("gsc_*.json"), reverse=True)
    for path in candidates:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            queries = data if isinstance(data, list) else data.get("rows", [])
            # Normalise field names (GSC exports may use camelCase or snake_case)
            normalised = []
            for row in queries:
                if isinstance(row, dict):
                    normalised.append(
                        {
                            "query": row.get(
                                "query",
                                row.get("keys", [""])[0]
                                if isinstance(row.get("keys"), list)
                                else "",
                            ),
                            "impressions": row.get("impressions", 0),
                            "clicks": row.get("clicks", 0),
                            "position": row.get("position", row.get("avg_position", 0)),
                        }
                    )
            return normalised
        except (json.JSONDecodeError, OSError, (KeyError, IndexError)):
            continue
    return []


@router.get("/api/shops/{shop}/niche/clusters")
async def get_niche_clusters(
    shop: str,
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
) -> list[dict]:
    """Return product clusters detected from the latest Shopify snapshot.

    Each cluster includes its name, products, and top TF-IDF keywords.

    Args:
        shop: Shopify shop domain.
    """
    from app.niche.clustering import cluster_products

    products = _load_snapshot(shop)
    if not products:
        raise HTTPException(
            status_code=404,
            detail="No product snapshot found. Run 'leonie-seo audit crawl' first.",
        )
    clusters = cluster_products(products)
    return [asdict(c) for c in clusters]


@router.get("/api/shops/{shop}/niche/gaps")
async def get_niche_gaps(
    shop: str,
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
) -> list[dict]:
    """Return keyword gaps from GSC data vs product cluster coverage.

    Each gap includes the query, impressions, GSC position, nearest cluster,
    SERP saturation level, and opportunity score (0-1).

    Args:
        shop: Shopify shop domain.
    """
    from app.niche.clustering import cluster_products
    from app.niche.gaps import analyze_keyword_gaps

    products = _load_snapshot(shop)
    gsc_queries = _load_gsc(shop)

    if not gsc_queries:
        raise HTTPException(
            status_code=404,
            detail="No GSC data found. Run 'leonie-seo audit gsc' first.",
        )

    clusters = cluster_products(products)
    gaps = analyze_keyword_gaps(gsc_queries, clusters)
    return [asdict(g) for g in gaps]


@router.get("/api/shops/{shop}/niche/report")
async def get_niche_report(
    shop: str,
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
) -> dict:
    """Return the full Niche Intelligence report (clusters + gaps).

    Args:
        shop: Shopify shop domain.
    """
    products = _load_snapshot(shop)
    gsc_queries = _load_gsc(shop)

    if not products and not gsc_queries:
        raise HTTPException(
            status_code=404,
            detail="No snapshot or GSC data found. Run the audit pipeline first.",
        )

    report = run_niche_analysis(products, gsc_queries, shop=shop)
    return asdict(report)
