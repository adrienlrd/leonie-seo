"""Niche Intelligence API — clusters, keyword gaps, full report."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.api.deps import ShopContext, get_shop_context
from app.api.snapshot_store import load_latest_snapshot_from_db
from app.llm.provider import LLMError
from app.niche.engine import run_niche_analysis
from app.niche.understanding import (
    NicheUnderstandingError,
    generate_niche_hypothesis,
    get_niche_hypothesis,
    get_niche_hypothesis_history,
    save_niche_hypothesis,
)

router = APIRouter(tags=["niche"])

_DATA_DIR = Path(__file__).parents[2] / "data" / "raw"


def _load_snapshot(shop: str) -> list[dict]:
    """Load the most recent Shopify product snapshot for a shop.

    Looks only in `data/raw/{shop}/snapshot_*.json` — never falls back to
    the legacy flat path, which would leak data across tenants in
    multi-tenant deployments. Returns an empty list if no snapshot exists.
    """
    shop_dir = _DATA_DIR / shop
    if not shop_dir.exists():
        snapshot = load_latest_snapshot_from_db(shop)
        return snapshot.get("products", []) if snapshot else []
    candidates = sorted(shop_dir.glob("snapshot_*.json"), reverse=True)
    for path in candidates:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            products = data if isinstance(data, list) else data.get("products", [])
            return products
        except (json.JSONDecodeError, OSError):
            continue
    snapshot = load_latest_snapshot_from_db(shop)
    return snapshot.get("products", []) if snapshot else []


def _load_gsc(shop: str) -> list[dict]:
    """Load the most recent GSC query export for a shop.

    Looks only in `data/raw/{shop}/gsc_*.json` — same multi-tenant safety
    rationale as `_load_snapshot`. Returns an empty list if no export exists.
    """
    shop_dir = _DATA_DIR / shop
    if not shop_dir.exists():
        return []
    candidates = sorted(shop_dir.glob("gsc_*.json"), reverse=True)
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
        except (json.JSONDecodeError, OSError, KeyError, IndexError):
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
            detail="No GSC data found. Connect Google Search Console in the app first.",
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


@router.get("/api/shops/{shop}/niche/intent-clusters")
async def get_intent_clusters(
    shop: str,
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
    min_impressions: int = 5,
) -> list[dict]:
    """Return GSC queries clustered by user intent and semantic similarity.

    Queries below min_impressions are excluded as noise.
    Results are sorted by total_impressions descending.

    Args:
        shop: Shopify shop domain.
        min_impressions: Minimum impressions threshold (default 5).
    """
    from app.niche.intent import cluster_gsc_queries

    gsc_queries = _load_gsc(shop)
    if not gsc_queries:
        raise HTTPException(
            status_code=404,
            detail="No GSC data found. Connect Google Search Console in the app first.",
        )

    clusters = cluster_gsc_queries(gsc_queries, min_impressions=min_impressions)
    return [asdict(c) for c in clusters]


class SignalRequest(BaseModel):
    seeds: list[str]
    sources: list[str] | None = None  # None = all sources
    geo: str = "FR"


class NicheUnderstandRequest(BaseModel):
    force_refresh: bool = False
    use_llm: bool = True


class NicheHypothesisPatch(BaseModel):
    hypothesis: dict
    status: str | None = None


@router.post("/api/shops/{shop}/niche/signals")
async def fetch_niche_signals(
    shop: str,
    body: SignalRequest,
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
) -> list[dict]:
    """Fetch keyword signals from Google Suggest, Trends and Reddit for seed keywords.

    Args:
        shop: Shopify shop domain.
        body: seeds — list of seed keywords (cluster names or GSC queries).
              sources — optional subset: ["google_suggest", "trends", "reddit"].
              geo — country code for regional results (default "FR").

    Returns:
        Deduplicated keyword signals sorted by relevance_score descending.
    """
    if not body.seeds:
        raise HTTPException(status_code=422, detail="seeds list must not be empty")

    from app.niche.signals.aggregator import fetch_all_signals

    signals = fetch_all_signals(
        body.seeds,
        sources=body.sources,
        geo=body.geo,
    )
    return [asdict(s) for s in signals]


@router.post("/api/shops/{shop}/niche/understand")
async def post_niche_understand(
    shop: str,
    body: NicheUnderstandRequest,
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
) -> dict:
    """Generate a merchant-reviewable niche hypothesis."""
    products = _load_snapshot(shop)
    gsc_queries = _load_gsc(shop)
    if not products and not gsc_queries:
        raise HTTPException(
            status_code=404,
            detail="No snapshot or GSC data found. Run the audit pipeline first.",
        )

    try:
        hypothesis = generate_niche_hypothesis(
            shop,
            products,
            gsc_queries,
            force_refresh=body.force_refresh,
            use_llm=body.use_llm,
        )
    except NicheUnderstandingError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except LLMError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return {
        "available": True,
        "shop": ctx.shop,
        "hypothesis": hypothesis,
        "history": get_niche_hypothesis_history(shop),
    }


@router.get("/api/shops/{shop}/niche/hypothesis")
async def get_niche_hypothesis_endpoint(
    shop: str,
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
) -> dict:
    """Return the stored merchant niche hypothesis."""
    hypothesis = get_niche_hypothesis(shop)
    return {
        "available": hypothesis is not None,
        "shop": ctx.shop,
        "hypothesis": hypothesis,
        "history": get_niche_hypothesis_history(shop),
    }


@router.patch("/api/shops/{shop}/niche/hypothesis")
async def patch_niche_hypothesis(
    shop: str,
    body: NicheHypothesisPatch,
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
) -> dict:
    """Persist merchant edits to the niche hypothesis."""
    hypothesis = dict(body.hypothesis)
    if body.status:
        hypothesis["status"] = body.status
    saved = save_niche_hypothesis(shop, hypothesis)
    return {
        "available": True,
        "shop": ctx.shop,
        "hypothesis": saved,
        "history": get_niche_hypothesis_history(shop),
    }
