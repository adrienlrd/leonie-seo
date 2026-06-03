"""GEO readiness endpoints."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field

from app.api.deps import ShopContext, get_shop_context
from app.api.snapshot_store import load_snapshot_from_file_or_db
from app.db_adapter import DB_PATH
from app.ga4.client import GA4Error
from app.geo.answers import build_catalog_answer_blocks
from app.geo.collections import build_collection_suggestions, parse_gsc_query_page_csv
from app.geo.competitors import build_competitor_monitor
from app.geo.confidence import compute_catalog_confidence
from app.geo.continuous_agent import run_continuous_improvement_agent
from app.geo.continuous_improvement import list_continuous_improvement
from app.geo.control_groups import build_control_groups
from app.geo.crawlability import build_ai_crawlability_advisor
from app.geo.event_tracking import (
    create_event_from_optimization_snapshot,
    mark_optimization_event_status,
)
from app.geo.facts import analyze_catalog_facts
from app.geo.faq_generator import generate_catalog_content
from app.geo.impact_report import build_catalog_report, render_markdown
from app.geo.ledger import create_geo_event, list_geo_events, summarize_geo_events
from app.geo.next_best_actions import build_next_best_actions
from app.geo.optimization_snapshots import (
    build_optimization_snapshot,
    create_optimization_snapshot,
    list_optimization_snapshots,
)
from app.geo.prioritization import prioritize_catalog
from app.geo.progress_curve import build_progress_curve
from app.geo.retention_milestones import build_retention_milestones
from app.geo.risk_guard import assess_catalog_risk
from app.geo.validation_timeline import build_validation_timeline
from app.geo.weekly import build_weekly_actions
from app.impact.report import _find_gsc_file, _parse_gsc_csv
from app.snapshot.scope import normalize_product_scope

router = APIRouter(prefix="/api", tags=["geo"])


def _find_gsc_query_page_file(shop: str) -> Path | None:
    project_root = Path(__file__).parents[2]
    path = project_root / "data" / "raw" / shop / "gsc_query_page.csv"
    return path if path.exists() else None


def _validated_scope(scope: str) -> str:
    try:
        return normalize_product_scope(scope)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


class GeoLedgerEventRequest(BaseModel):
    event_type: str = Field(default="planned_optimization")
    resource_type: str = Field(default="product")
    resource_id: str
    resource_title: str = ""
    action_type: str
    status: str = Field(default="planned")
    source: str = Field(default="geo")
    job_id: str | None = None
    snapshot_id: int | None = None
    hypothesis: str | None = None
    score_before: int | None = None
    score_after: int | None = None
    measurement_status: str = Field(default="not_started")
    before_snapshot: dict = Field(default_factory=dict)
    after_snapshot: dict | None = None
    metrics_before: dict = Field(default_factory=dict)
    metrics_after: dict | None = None
    estimated_impact: dict = Field(default_factory=dict)
    observed_impact: dict | None = None
    notes: str | None = None


class GeoEventFromSnapshotRequest(BaseModel):
    snapshot_id: int
    status: str = Field(default="planned")
    job_id: str | None = None
    estimated_impact: dict = Field(default_factory=dict)
    notes: str | None = None


class GeoEventStatusRequest(BaseModel):
    status: str
    score_after: int | None = None
    measurement_status: str | None = None
    after_snapshot: dict | None = None
    metrics_after: dict | None = None
    observed_impact: dict | None = None
    notes: str | None = None


class GeoOptimizationSnapshotRequest(BaseModel):
    resource_type: str = Field(pattern="^(product|collection)$")
    resource_id: str
    action_type: str
    source: str = Field(default="geo")
    hypothesis: str | None = None
    notes: str | None = None


class ContinuousImprovementAgentRequest(BaseModel):
    auto_apply: bool = False
    confirm_live_write: bool = False
    plan: str = Field(default="free", pattern="^(free|pro|agency)$")
    max_actions: int = Field(default=5, ge=1, le=20)


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
    scope: str = Query(default="active", pattern="^(active|draft|unlisted|archived|all)$"),
    top: int = 50,
) -> RedirectResponse:
    """Permanently redirected to /api/shops/{shop}/audit/readiness."""
    return RedirectResponse(
        url=f"/api/shops/{shop}/audit/readiness?scope={scope}&top={top}",
        status_code=301,
    )


@router.get("/shops/{shop}/geo/priorities")
async def get_geo_priorities(
    shop: str,
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
    top: int = 20,
    conversion_rate: float = Query(default=0.02, gt=0, le=1),
    average_order_value: float = Query(default=50.0, gt=0),
    position_improvement: float = Query(default=2.0, ge=0.5, le=10.0),
    scope: str = Query(default="active", pattern="^(active|draft|unlisted|archived|all)$"),
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
        scope=_validated_scope(scope),
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
    scope: str = Query(default="active", pattern="^(active|draft|unlisted|archived|all)$"),
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
        scope=_validated_scope(scope),
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


@router.get("/shops/{shop}/geo/continuous-improvement")
async def get_geo_continuous_improvement(
    shop: str,
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
    limit: int = Query(default=100, ge=1, le=300),
) -> dict:
    """Return continuous improvement tags, agent changes and metrics."""
    data = list_continuous_improvement(ctx.shop, limit=limit, db_path=DB_PATH)
    return {
        "shop": ctx.shop,
        "available": True,
        **data,
    }


@router.post("/shops/{shop}/geo/continuous-improvement/run")
async def run_geo_continuous_improvement_agent(
    shop: str,
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
    body: ContinuousImprovementAgentRequest,
) -> dict:
    """Run the continuous improvement agent in proposal or safe auto-apply mode."""
    try:
        result = await asyncio.to_thread(
            run_continuous_improvement_agent,
            ctx.shop,
            access_token=ctx.access_token,
            plan=body.plan,
            auto_apply=body.auto_apply,
            confirm_live_write=body.confirm_live_write,
            max_actions=body.max_actions,
            db_path=DB_PATH,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {
        "shop": ctx.shop,
        "available": True,
        **result,
    }


@router.get("/shops/{shop}/geo/optimization-snapshots")
async def get_geo_optimization_snapshots(
    shop: str,
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> dict:
    """Return stored before-optimization snapshots for a shop."""
    data = list_optimization_snapshots(ctx.shop, limit=limit, offset=offset, db_path=DB_PATH)
    return {
        "shop": ctx.shop,
        "available": True,
        **data,
    }


async def _load_ga4_daily(shop: str, days: int) -> tuple[dict, bool]:
    """Best-effort fetch of daily organic GA4 metrics; degrade to empty when unavailable."""
    try:
        from app.api.ga4 import _build_ga4_client
        from app.ga4.queries import get_organic_daily

        client = _build_ga4_client(shop)
    except (HTTPException, GA4Error):
        return {}, False
    try:
        rows = await asyncio.to_thread(get_organic_daily, client, days=days)
    except GA4Error:
        return {}, False
    return rows, True


@router.get("/shops/{shop}/geo/progress-curve")
async def get_geo_progress_curve(
    shop: str,
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
    days: int = Query(default=90, ge=7, le=180),
) -> dict:
    """Aggregate snapshots, events, GSC and GA4 daily rows into dashboard time-series."""
    snapshots = list_optimization_snapshots(ctx.shop, limit=500, db_path=DB_PATH)["snapshots"]
    events = list_geo_events(ctx.shop, limit=500, db_path=DB_PATH)["events"]
    gsc_file = _find_gsc_file(ctx.shop)
    ga4_daily, ga4_connected = await _load_ga4_daily(ctx.shop, days=days)

    return build_progress_curve(
        shop=ctx.shop,
        snapshots=snapshots,
        events=events,
        ga4_daily=ga4_daily,
        gsc_available=gsc_file is not None,
        ga4_connected=ga4_connected,
        window_days=days,
    )


@router.get("/shops/{shop}/geo/confidence-scores")
async def get_geo_confidence_scores(
    shop: str,
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
    limit: int = Query(default=500, ge=1, le=500),
) -> dict:
    """Return 0-100 impact confidence scores for all GEO optimization events."""
    events = list_geo_events(ctx.shop, limit=limit, db_path=DB_PATH)["events"]
    result = compute_catalog_confidence(events)
    return {
        "shop": ctx.shop,
        "generated_at": datetime.now(UTC).isoformat(),
        **result,
    }


@router.get("/shops/{shop}/geo/impact-report")
async def get_geo_impact_report(
    shop: str,
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
    limit: int = Query(default=500, ge=1, le=500),
) -> dict:
    """Return a before/after impact report with verdict and Markdown export."""
    events = list_geo_events(ctx.shop, limit=limit, db_path=DB_PATH)["events"]
    confidence_data = compute_catalog_confidence(events)
    catalog = build_catalog_report(events, confidence_data["scores"])

    return {
        "shop": ctx.shop,
        "generated_at": datetime.now(UTC).isoformat(),
        "reports": catalog["reports"],
        "markdown": render_markdown(catalog["reports"]),
        "summary": catalog["summary"],
    }


@router.get("/shops/{shop}/geo/retention-milestones")
async def get_geo_retention_milestones(
    shop: str,
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
    limit: int = Query(default=500, ge=1, le=500),
) -> dict:
    """Return J+7/J+30/J+60/J+90 retention milestones for applied GEO events."""
    events = list_geo_events(ctx.shop, limit=limit, db_path=DB_PATH)["events"]
    result = build_retention_milestones(events)
    return {
        "shop": ctx.shop,
        "generated_at": datetime.now(UTC).isoformat(),
        **result,
    }


@router.get("/shops/{shop}/geo/next-best-actions")
async def get_geo_next_best_actions(
    shop: str,
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
    limit: int = Query(default=500, ge=1, le=500),
    scope: str = Query(default="active", pattern="^(active|draft|unlisted|archived|all)$"),
) -> dict:
    """Return prioritised next-best-action recommendations from validated impact reports."""
    events = list_geo_events(ctx.shop, limit=limit, db_path=DB_PATH)["events"]
    confidence_data = compute_catalog_confidence(events)
    catalog = build_catalog_report(events, confidence_data["scores"])
    snapshot = load_snapshot_from_file_or_db(ctx.shop, ctx.snapshot_path)
    result = build_next_best_actions(
        catalog["reports"], snapshot=snapshot, scope=_validated_scope(scope)
    )
    return {
        "shop": ctx.shop,
        "generated_at": datetime.now(UTC).isoformat(),
        **result,
    }


@router.get("/shops/{shop}/geo/faq-content")
async def get_geo_faq_content(
    shop: str,
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
    top: int = Query(default=20, ge=1, le=50),
    scope: str = Query(default="active", pattern="^(active|draft|unlisted|archived|all)$"),
) -> dict:
    """Generate GEO FAQ, buying guides and JSON-LD from confirmed product facts and GSC queries."""
    snapshot = load_snapshot_from_file_or_db(ctx.shop, ctx.snapshot_path)
    if snapshot is None:
        raise HTTPException(
            status_code=404,
            detail="Snapshot introuvable. Lancez un audit SEO d'abord.",
        )

    products = snapshot.get("products") or []
    collections = snapshot.get("collections") or []

    gsc_file = _find_gsc_file(ctx.shop)
    gsc_rows = _parse_gsc_csv(gsc_file.read_text()) if gsc_file else {}
    gsc_queries = list(gsc_rows.keys())

    result = generate_catalog_content(
        products,
        gsc_queries=gsc_queries,
        collections=collections,
        top=top,
        scope=_validated_scope(scope),
    )
    return {
        "shop": ctx.shop,
        "generated_at": datetime.now(UTC).isoformat(),
        **result,
    }


@router.get("/shops/{shop}/geo/control-groups")
async def get_geo_control_groups(
    shop: str,
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
    event_id: int | None = None,
    top_events: int = Query(default=10, ge=1, le=50),
    controls_per_event: int = Query(default=3, ge=1, le=10),
) -> dict:
    """Return comparable unmodified control pages for GEO optimization events."""
    snapshot = load_snapshot_from_file_or_db(ctx.shop, ctx.snapshot_path)
    if snapshot is None:
        raise HTTPException(
            status_code=404,
            detail="Snapshot introuvable. Lancez un audit SEO d'abord.",
        )

    gsc_file = _find_gsc_file(ctx.shop)
    gsc_rows = _parse_gsc_csv(gsc_file.read_text()) if gsc_file else {}
    events = list_geo_events(ctx.shop, limit=200, db_path=DB_PATH)["events"]
    analysis = build_control_groups(
        snapshot=snapshot,
        events=events,
        gsc_rows=gsc_rows,
        event_id=event_id,
        top_events=top_events,
        controls_per_event=controls_per_event,
    )
    return {
        "shop": ctx.shop,
        "available": True,
        **analysis,
    }


@router.get("/shops/{shop}/geo/validation-timeline")
async def get_geo_validation_timeline(
    shop: str,
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
    event_id: int | None = None,
    min_impressions: int = Query(default=50, ge=0, le=10000),
) -> dict:
    """Return J+7/J+30/J+60/J+90 validation windows for GEO events."""
    events = list_geo_events(ctx.shop, limit=200, db_path=DB_PATH)["events"]
    analysis = build_validation_timeline(
        events=events,
        event_id=event_id,
        min_impressions=min_impressions,
    )
    return {
        "shop": ctx.shop,
        "available": True,
        **analysis,
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


@router.get("/shops/{shop}/geo/crawlability")
async def get_geo_crawlability(
    shop: str,
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
    top_products: int = Query(default=30, ge=1, le=100),
    top_collections: int = Query(default=20, ge=1, le=100),
) -> dict:
    """Return llms.txt preview and AI crawlability recommendations."""
    snapshot = load_snapshot_from_file_or_db(ctx.shop, ctx.snapshot_path)
    if snapshot is None:
        raise HTTPException(
            status_code=404,
            detail="Snapshot introuvable. Lancez un audit SEO d'abord.",
        )

    analysis = build_ai_crawlability_advisor(
        ctx.shop,
        snapshot,
        top_products=top_products,
        top_collections=top_collections,
    )
    return {
        "shop": ctx.shop,
        "available": True,
        **analysis,
    }


@router.get("/shops/{shop}/geo/competitors")
async def get_geo_competitors(
    shop: str,
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
    competitors: str = Query(default="", description="Comma-separated competitor domains"),
    top: int = Query(default=10, ge=1, le=50),
) -> dict:
    """Return a light AI-answer competitor monitor for conversational queries."""
    snapshot = load_snapshot_from_file_or_db(ctx.shop, ctx.snapshot_path)
    if snapshot is None:
        raise HTTPException(
            status_code=404,
            detail="Snapshot introuvable. Lancez un audit SEO d'abord.",
        )

    query_page_file = _find_gsc_query_page_file(ctx.shop)
    query_rows = parse_gsc_query_page_csv(query_page_file.read_text()) if query_page_file else []
    analysis = build_competitor_monitor(
        snapshot.get("products", []),
        query_rows,
        competitors=competitors,
        top=top,
    )
    return {
        "shop": ctx.shop,
        "available": True,
        "gsc_query_page_connected": bool(query_rows),
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
        snapshot_id=body.snapshot_id,
        hypothesis=body.hypothesis,
        score_before=body.score_before,
        score_after=body.score_after,
        measurement_status=body.measurement_status,
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


@router.post("/shops/{shop}/geo/ledger/events/from-snapshot")
async def create_geo_ledger_event_from_snapshot(
    shop: str,
    body: GeoEventFromSnapshotRequest,
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
) -> dict:
    """Create a traceable GEO event from a stored optimization snapshot."""
    try:
        event_id = create_event_from_optimization_snapshot(
            shop=ctx.shop,
            snapshot_id=body.snapshot_id,
            status=body.status,
            job_id=body.job_id,
            estimated_impact=body.estimated_impact,
            notes=body.notes,
            db_path=DB_PATH,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {
        "shop": ctx.shop,
        "event_id": event_id,
        "snapshot_id": body.snapshot_id,
        "created": True,
    }


@router.patch("/shops/{shop}/geo/ledger/events/{event_id}/status")
async def update_geo_ledger_event_status(
    shop: str,
    event_id: int,
    body: GeoEventStatusRequest,
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
) -> dict:
    """Update a GEO event status and append an audit history entry."""
    updated = mark_optimization_event_status(
        shop=ctx.shop,
        event_id=event_id,
        status=body.status,
        score_after=body.score_after,
        measurement_status=body.measurement_status,
        after_snapshot=body.after_snapshot,
        metrics_after=body.metrics_after,
        observed_impact=body.observed_impact,
        notes=body.notes,
        db_path=DB_PATH,
    )
    if not updated:
        raise HTTPException(status_code=404, detail=f"GEO event {event_id} not found")
    return {
        "shop": ctx.shop,
        "event_id": event_id,
        "updated": True,
    }


@router.post("/shops/{shop}/geo/optimization-snapshots")
async def create_geo_optimization_snapshot(
    shop: str,
    body: GeoOptimizationSnapshotRequest,
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
) -> dict:
    """Create a before-optimization snapshot for later impact validation."""
    snapshot = load_snapshot_from_file_or_db(ctx.shop, ctx.snapshot_path)
    if snapshot is None:
        raise HTTPException(
            status_code=404,
            detail="Snapshot introuvable. Lancez un audit SEO d'abord.",
        )

    gsc_file = _find_gsc_file(ctx.shop)
    gsc_rows = _parse_gsc_csv(gsc_file.read_text()) if gsc_file else {}
    try:
        built = build_optimization_snapshot(
            shop=ctx.shop,
            snapshot=snapshot,
            resource_type=body.resource_type,
            resource_id=body.resource_id,
            action_type=body.action_type,
            gsc_rows=gsc_rows,
            source=body.source,
            hypothesis=body.hypothesis,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    snapshot_id = create_optimization_snapshot(
        shop=ctx.shop,
        snapshot_data=built,
        notes=body.notes,
        db_path=DB_PATH,
    )
    return {
        "shop": ctx.shop,
        "created": True,
        "snapshot_id": snapshot_id,
        "snapshot": built,
    }
