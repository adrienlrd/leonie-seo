"""GEO readiness endpoints."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.api.deps import ShopContext, get_shop_context
from app.api.snapshot_store import load_snapshot_from_file_or_db
from app.db_adapter import DB_PATH
from app.geo.answers import build_catalog_answer_blocks
from app.geo.collections import build_collection_suggestions, parse_gsc_query_page_csv
from app.geo.facts import analyze_catalog_facts
from app.geo.ledger import create_geo_event, list_geo_events, summarize_geo_events
from app.geo.prioritization import prioritize_catalog
from app.geo.readiness import score_catalog_readiness
from app.geo.risk_guard import assess_catalog_risk
from app.geo.weekly import build_weekly_actions
from app.impact.report import _find_gsc_file, _parse_gsc_csv

router = APIRouter(prefix="/api", tags=["geo"])


def _find_gsc_query_page_file(shop: str) -> Path | None:
    project_root = Path(__file__).parents[2]
    path = project_root / "data" / "raw" / shop / "gsc_query_page.csv"
    return path if path.exists() else None


class GeoLedgerEventRequest(BaseModel):
    event_type: str = Field(default="planned_optimization")
    resource_type: str = Field(default="product")
    resource_id: str
    resource_title: str = ""
    action_type: str
    status: str = Field(default="planned")
    source: str = Field(default="geo")
    job_id: str | None = None
    hypothesis: str | None = None
    before_snapshot: dict = Field(default_factory=dict)
    after_snapshot: dict | None = None
    metrics_before: dict = Field(default_factory=dict)
    metrics_after: dict | None = None
    estimated_impact: dict = Field(default_factory=dict)
    observed_impact: dict | None = None
    notes: str | None = None


@router.get("/shops/{shop}/geo/facts")
async def get_geo_facts(
    shop: str,
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
    top: int = 50,
) -> dict:
    """Return confirmed product facts and merchant verification gaps for GEO."""
    snapshot = load_snapshot_from_file_or_db(ctx.shop, ctx.snapshot_path)
    if snapshot is None:
        raise HTTPException(
            status_code=404,
            detail="Snapshot introuvable. Lancez un audit SEO d'abord.",
        )

    analysis = analyze_catalog_facts(snapshot.get("products", []), top=top)
    return {
        "shop": ctx.shop,
        "available": True,
        **analysis,
    }


@router.get("/shops/{shop}/geo/readiness")
async def get_geo_readiness(
    shop: str,
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
    top: int = 50,
) -> dict:
    """Return AI Search readiness scores for products in the latest snapshot."""
    snapshot = load_snapshot_from_file_or_db(ctx.shop, ctx.snapshot_path)
    if snapshot is None:
        raise HTTPException(
            status_code=404,
            detail="Snapshot introuvable. Lancez un audit SEO d'abord.",
        )

    analysis = score_catalog_readiness(snapshot.get("products", []), top=top)
    return {
        "shop": ctx.shop,
        "available": True,
        **analysis,
    }


@router.get("/shops/{shop}/geo/priorities")
async def get_geo_priorities(
    shop: str,
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
    top: int = 20,
    conversion_rate: float = Query(default=0.02, gt=0, le=1),
    average_order_value: float = Query(default=50.0, gt=0),
    position_improvement: float = Query(default=2.0, ge=0.5, le=10.0),
) -> dict:
    """Return revenue-aware GEO action priorities for products."""
    snapshot = load_snapshot_from_file_or_db(ctx.shop, ctx.snapshot_path)
    if snapshot is None:
        raise HTTPException(
            status_code=404,
            detail="Snapshot introuvable. Lancez un audit SEO d'abord.",
        )

    gsc_file = _find_gsc_file(ctx.shop)
    gsc_rows = _parse_gsc_csv(gsc_file.read_text()) if gsc_file else {}
    shop_domain = snapshot.get("shop", {}).get("domain", ctx.shop)
    analysis = prioritize_catalog(
        snapshot.get("products", []),
        shop_domain,
        gsc_rows,
        top=top,
        conversion_rate=conversion_rate,
        average_order_value=average_order_value,
        position_improvement=position_improvement,
    )
    return {
        "shop": ctx.shop,
        "available": True,
        "assumptions": {
            "conversion_rate": conversion_rate,
            "average_order_value": average_order_value,
            "position_improvement": position_improvement,
        },
        **analysis,
    }


@router.get("/shops/{shop}/geo/weekly-actions")
async def get_geo_weekly_actions(
    shop: str,
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
    limit: int = Query(default=3, ge=1, le=5),
    conversion_rate: float = Query(default=0.02, gt=0, le=1),
    average_order_value: float = Query(default=50.0, gt=0),
    position_improvement: float = Query(default=2.0, ge=0.5, le=10.0),
) -> dict:
    """Return a short weekly GEO action list for merchants."""
    snapshot = load_snapshot_from_file_or_db(ctx.shop, ctx.snapshot_path)
    if snapshot is None:
        raise HTTPException(
            status_code=404,
            detail="Snapshot introuvable. Lancez un audit SEO d'abord.",
        )

    gsc_file = _find_gsc_file(ctx.shop)
    gsc_rows = _parse_gsc_csv(gsc_file.read_text()) if gsc_file else {}
    shop_domain = snapshot.get("shop", {}).get("domain", ctx.shop)
    analysis = build_weekly_actions(
        snapshot.get("products", []),
        shop_domain,
        gsc_rows,
        limit=limit,
        conversion_rate=conversion_rate,
        average_order_value=average_order_value,
        position_improvement=position_improvement,
    )
    return {
        "shop": ctx.shop,
        "available": True,
        "assumptions": {
            "conversion_rate": conversion_rate,
            "average_order_value": average_order_value,
            "position_improvement": position_improvement,
        },
        **analysis,
    }


@router.get("/shops/{shop}/geo/ledger")
async def get_geo_ledger(
    shop: str,
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    status: str | None = None,
) -> dict:
    """Return GEO impact ledger events for a shop."""
    data = list_geo_events(ctx.shop, limit=limit, offset=offset, status=status, db_path=DB_PATH)
    return {
        "shop": ctx.shop,
        "available": True,
        "summary": summarize_geo_events(ctx.shop, db_path=DB_PATH),
        **data,
    }


@router.get("/shops/{shop}/geo/risk-guard")
async def get_geo_risk_guard(
    shop: str,
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
    top: int = 50,
    conversion_rate: float = Query(default=0.02, gt=0, le=1),
    average_order_value: float = Query(default=50.0, gt=0),
) -> dict:
    """Return GEO risk guard decisions for product pages."""
    snapshot = load_snapshot_from_file_or_db(ctx.shop, ctx.snapshot_path)
    if snapshot is None:
        raise HTTPException(
            status_code=404,
            detail="Snapshot introuvable. Lancez un audit SEO d'abord.",
        )

    gsc_file = _find_gsc_file(ctx.shop)
    gsc_rows = _parse_gsc_csv(gsc_file.read_text()) if gsc_file else {}
    shop_domain = snapshot.get("shop", {}).get("domain", ctx.shop)
    analysis = assess_catalog_risk(
        snapshot.get("products", []),
        shop_domain,
        gsc_rows,
        top=top,
        conversion_rate=conversion_rate,
        average_order_value=average_order_value,
    )
    return {
        "shop": ctx.shop,
        "available": True,
        "gsc_connected": bool(gsc_rows),
        **analysis,
    }


@router.get("/shops/{shop}/geo/collections")
async def get_geo_collections(
    shop: str,
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
    top: int = Query(default=10, ge=1, le=50),
    min_products: int = Query(default=2, ge=1, le=20),
) -> dict:
    """Return dry-run Shopify collection suggestions for conversational intents."""
    snapshot = load_snapshot_from_file_or_db(ctx.shop, ctx.snapshot_path)
    if snapshot is None:
        raise HTTPException(
            status_code=404,
            detail="Snapshot introuvable. Lancez un audit SEO d'abord.",
        )

    query_page_file = _find_gsc_query_page_file(ctx.shop)
    query_rows = parse_gsc_query_page_csv(query_page_file.read_text()) if query_page_file else []
    analysis = build_collection_suggestions(
        snapshot.get("products", []),
        snapshot.get("collections", []),
        query_rows,
        top=top,
        min_products=min_products,
    )
    return {
        "shop": ctx.shop,
        "available": True,
        "gsc_query_page_connected": bool(query_rows),
        **analysis,
    }


@router.get("/shops/{shop}/geo/answer-blocks")
async def get_geo_answer_blocks(
    shop: str,
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
    top: int = Query(default=30, ge=1, le=100),
    max_blocks: int = Query(default=6, ge=1, le=10),
) -> dict:
    """Return fact-grounded FAQ and answer block previews for products."""
    snapshot = load_snapshot_from_file_or_db(ctx.shop, ctx.snapshot_path)
    if snapshot is None:
        raise HTTPException(
            status_code=404,
            detail="Snapshot introuvable. Lancez un audit SEO d'abord.",
        )

    analysis = build_catalog_answer_blocks(
        snapshot.get("products", []),
        top=top,
        max_blocks=max_blocks,
    )
    return {
        "shop": ctx.shop,
        "available": True,
        **analysis,
    }


@router.post("/shops/{shop}/geo/ledger/events")
async def create_geo_ledger_event(
    shop: str,
    body: GeoLedgerEventRequest,
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
) -> dict:
    """Create a GEO impact ledger event.

    This is read-only with respect to Shopify: it records a planned, previewed,
    applied or measured GEO event but does not mutate merchant data.
    """
    event_id = create_geo_event(
        shop=ctx.shop,
        event_type=body.event_type,
        resource_type=body.resource_type,
        resource_id=body.resource_id,
        resource_title=body.resource_title,
        action_type=body.action_type,
        status=body.status,
        source=body.source,
        job_id=body.job_id,
        hypothesis=body.hypothesis,
        before_snapshot=body.before_snapshot,
        after_snapshot=body.after_snapshot,
        metrics_before=body.metrics_before,
        metrics_after=body.metrics_after,
        estimated_impact=body.estimated_impact,
        observed_impact=body.observed_impact,
        notes=body.notes,
        db_path=DB_PATH,
    )
    return {
        "shop": ctx.shop,
        "event_id": event_id,
        "created": True,
    }
