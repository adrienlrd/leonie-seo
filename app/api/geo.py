"""GEO readiness endpoints."""

from __future__ import annotations

import asyncio
import logging
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
from app.gsc.token_store import get_google_token
from app.impact.report import _find_gsc_file, _parse_gsc_csv
from app.managed_products import filter_snapshot_products
from app.snapshot.scope import normalize_product_scope

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["geo"])


def _run_measurement_loop_safe(shop: str) -> None:
    """Run the measurement loop, swallowing any error."""
    try:
        from app.geo.measurement_loop import run_measurement_loop  # noqa: PLC0415

        run_measurement_loop(shop)
    except Exception:
        logger.warning("measurement loop failed for %s", shop, exc_info=True)


def _find_gsc_query_page_file(shop: str) -> Path | None:
    project_root = Path(__file__).parents[2]
    path = project_root / "data" / "raw" / shop / "gsc_query_page.csv"
    return path if path.exists() else None


def _validated_scope(scope: str) -> str:
    try:
        return normalize_product_scope(scope)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


# Blocking I/O helpers — snapshot files are 10-100MB and the GSC CSVs are large
# enough that reading + parsing them on the event loop can stall /health checks.
# Always call these via ``await asyncio.to_thread(...)`` from async routes.
def _load_snapshot_blocking(shop: str, snapshot_path: Path) -> dict | None:
    return filter_snapshot_products(shop, load_snapshot_from_file_or_db(shop, snapshot_path))


def _read_gsc_rows_blocking(gsc_file: Path | None) -> dict:
    return _parse_gsc_csv(gsc_file.read_text()) if gsc_file else {}


def _read_gsc_query_page_rows_blocking(query_page_file: Path | None) -> list:
    return parse_gsc_query_page_csv(query_page_file.read_text()) if query_page_file else []


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
    snapshot = await asyncio.to_thread(_load_snapshot_blocking, ctx.shop, ctx.snapshot_path)
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
    snapshot = await asyncio.to_thread(_load_snapshot_blocking, ctx.shop, ctx.snapshot_path)
    if snapshot is None:
        raise HTTPException(
            status_code=404,
            detail="Snapshot introuvable. Lancez un audit SEO d'abord.",
        )

    gsc_file = _find_gsc_file(ctx.shop)
    gsc_rows = await asyncio.to_thread(_read_gsc_rows_blocking, gsc_file)
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
    snapshot = await asyncio.to_thread(_load_snapshot_blocking, ctx.shop, ctx.snapshot_path)
    if snapshot is None:
        raise HTTPException(
            status_code=404,
            detail="Snapshot introuvable. Lancez un audit SEO d'abord.",
        )

    gsc_file = _find_gsc_file(ctx.shop)
    gsc_rows = await asyncio.to_thread(_read_gsc_rows_blocking, gsc_file)
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
    from app.learning.scheduler import diagnose_cycle_outcome

    diagnostics = diagnose_cycle_outcome(
        learning_enabled=True, continuous_result=result, cycle_errors=[]
    )
    return {
        "shop": ctx.shop,
        "available": True,
        "diagnostics": diagnostics,
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


@router.get("/shops/{shop}/geo/analysis-overview")
async def get_geo_analysis_overview(
    shop: str,
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
) -> dict:
    """Per-product analysis overview: applied changes, before/after, 28-day traffic."""
    await asyncio.to_thread(_run_measurement_loop_safe, ctx.shop)

    from app.geo.analysis_overview import build_analysis_overview  # noqa: PLC0415

    result = await asyncio.to_thread(build_analysis_overview, ctx.shop, db_path=DB_PATH)
    return {
        "shop": ctx.shop,
        "generated_at": datetime.now(UTC).isoformat(),
        **result,
    }


@router.get("/shops/{shop}/geo/clicks-since-validation")
async def get_clicks_since_validation_endpoint(
    shop: str,
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
) -> dict:
    """Google + AI clicks per validated resource since its last validation.

    Lightweight (decoupled from the heavy analysis-overview) so the Analyse page
    can poll it to keep the counters live. Results are cached server-side.
    """
    from app.geo.clicks_since_validation import compute_clicks_since_validation  # noqa: PLC0415

    return await asyncio.to_thread(compute_clicks_since_validation, ctx.shop, db_path=DB_PATH)


@router.get("/shops/{shop}/geo/theme-extension-status")
async def get_theme_extension_status_endpoint(
    shop: str,
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
) -> dict:
    """Whether the GEO by Organically theme app embed is enabled on the published theme."""
    from app.apply.theme_extension_status import get_theme_extension_status  # noqa: PLC0415

    status = await asyncio.to_thread(get_theme_extension_status, ctx.shop, ctx.access_token)
    return {"shop": ctx.shop, **status}


@router.get("/shops/{shop}/geo/realtime-signals")
async def get_realtime_signals_endpoint(
    shop: str,
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
) -> dict:
    """Last persisted real-time market signal snapshot (Grande boutique plan only).

    Read-only — never triggers a new grounded call. Returns `signals: null` for
    every other plan or before the first agency-plan analysis has run.
    """
    from app.billing.subscription_store import get_plan_for_shop  # noqa: PLC0415
    from app.niche.signals.realtime_trends import load_realtime_signals  # noqa: PLC0415

    if get_plan_for_shop(ctx.shop) != "agency":
        return {"shop": ctx.shop, "signals": None}
    signals = await asyncio.to_thread(load_realtime_signals, ctx.shop)
    return {"shop": ctx.shop, "signals": signals}


@router.get("/shops/{shop}/geo/progress-curve")
async def get_geo_progress_curve(
    shop: str,
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
    days: int = Query(default=90, ge=7, le=180),
) -> dict:
    """Aggregate snapshots, events, GSC and GA4 daily rows into dashboard time-series."""
    await asyncio.to_thread(_run_measurement_loop_safe, ctx.shop)
    snapshots = list_optimization_snapshots(ctx.shop, limit=500, db_path=DB_PATH)["snapshots"]
    events = list_geo_events(ctx.shop, limit=500, db_path=DB_PATH)["events"]
    gsc_file = _find_gsc_file(ctx.shop)
    ga4_daily, ga4_connected = await _load_ga4_daily(ctx.shop, days=days)
    google_authorized = get_google_token(ctx.shop) is not None

    return build_progress_curve(
        shop=ctx.shop,
        snapshots=snapshots,
        events=events,
        ga4_daily=ga4_daily,
        gsc_available=gsc_file is not None,
        ga4_connected=ga4_connected,
        google_authorized=google_authorized,
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
    await asyncio.to_thread(_run_measurement_loop_safe, ctx.shop)
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
    """Return J+14/J+28/J+60 retention milestones for applied GEO events."""
    await asyncio.to_thread(_run_measurement_loop_safe, ctx.shop)
    events = list_geo_events(ctx.shop, limit=limit, db_path=DB_PATH)["events"]
    result = build_retention_milestones(events)
    return {
        "shop": ctx.shop,
        "generated_at": datetime.now(UTC).isoformat(),
        **result,
    }


def _load_next_best_actions(
    shop: str,
    snapshot_path: Path,
    reports: list[dict],
    scope: str,
) -> dict:
    """Blocking: snapshot read/parse can be a 10-100MB file, must not run on the event loop."""
    snapshot = filter_snapshot_products(shop, load_snapshot_from_file_or_db(shop, snapshot_path))
    return build_next_best_actions(reports, snapshot=snapshot, scope=scope, shop=shop)


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
    result = await asyncio.to_thread(
        _load_next_best_actions, ctx.shop, ctx.snapshot_path, catalog["reports"], _validated_scope(scope)
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
    snapshot = await asyncio.to_thread(_load_snapshot_blocking, ctx.shop, ctx.snapshot_path)
    if snapshot is None:
        raise HTTPException(
            status_code=404,
            detail="Snapshot introuvable. Lancez un audit SEO d'abord.",
        )

    products = snapshot.get("products") or []
    collections = snapshot.get("collections") or []

    gsc_file = _find_gsc_file(ctx.shop)
    gsc_rows = await asyncio.to_thread(_read_gsc_rows_blocking, gsc_file)
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


def _load_control_groups(
    shop: str,
    snapshot_path: Path,
    events: list[dict],
    event_id: int | None,
    top_events: int,
    controls_per_event: int,
) -> dict | None:
    """Blocking: snapshot read/parse can be a 10-100MB file, must not run on the event loop."""
    snapshot = filter_snapshot_products(shop, load_snapshot_from_file_or_db(shop, snapshot_path))
    if snapshot is None:
        return None
    gsc_file = _find_gsc_file(shop)
    gsc_rows = _parse_gsc_csv(gsc_file.read_text()) if gsc_file else {}
    return build_control_groups(
        snapshot=snapshot,
        events=events,
        gsc_rows=gsc_rows,
        event_id=event_id,
        top_events=top_events,
        controls_per_event=controls_per_event,
    )


@router.get("/shops/{shop}/geo/control-groups")
async def get_geo_control_groups(
    shop: str,
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
    event_id: int | None = None,
    top_events: int = Query(default=10, ge=1, le=50),
    controls_per_event: int = Query(default=3, ge=1, le=10),
) -> dict:
    """Return comparable unmodified control pages for GEO optimization events."""
    events = list_geo_events(ctx.shop, limit=200, db_path=DB_PATH)["events"]
    analysis = await asyncio.to_thread(
        _load_control_groups,
        ctx.shop,
        ctx.snapshot_path,
        events,
        event_id,
        top_events,
        controls_per_event,
    )
    if analysis is None:
        raise HTTPException(
            status_code=404,
            detail="Snapshot introuvable. Lancez un audit SEO d'abord.",
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
    """Return J+14/J+28/J+60 validation windows for GEO events."""
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
    snapshot = await asyncio.to_thread(_load_snapshot_blocking, ctx.shop, ctx.snapshot_path)
    if snapshot is None:
        raise HTTPException(
            status_code=404,
            detail="Snapshot introuvable. Lancez un audit SEO d'abord.",
        )

    gsc_file = _find_gsc_file(ctx.shop)
    gsc_rows = await asyncio.to_thread(_read_gsc_rows_blocking, gsc_file)
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
    snapshot = await asyncio.to_thread(_load_snapshot_blocking, ctx.shop, ctx.snapshot_path)
    if snapshot is None:
        raise HTTPException(
            status_code=404,
            detail="Snapshot introuvable. Lancez un audit SEO d'abord.",
        )

    query_page_file = _find_gsc_query_page_file(ctx.shop)
    query_rows = await asyncio.to_thread(_read_gsc_query_page_rows_blocking, query_page_file)
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
    snapshot = await asyncio.to_thread(_load_snapshot_blocking, ctx.shop, ctx.snapshot_path)
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
    snapshot = await asyncio.to_thread(_load_snapshot_blocking, ctx.shop, ctx.snapshot_path)
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
    snapshot = await asyncio.to_thread(_load_snapshot_blocking, ctx.shop, ctx.snapshot_path)
    if snapshot is None:
        raise HTTPException(
            status_code=404,
            detail="Snapshot introuvable. Lancez un audit SEO d'abord.",
        )

    query_page_file = _find_gsc_query_page_file(ctx.shop)
    query_rows = await asyncio.to_thread(_read_gsc_query_page_rows_blocking, query_page_file)
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
    snapshot = await asyncio.to_thread(_load_snapshot_blocking, ctx.shop, ctx.snapshot_path)
    if snapshot is None:
        raise HTTPException(
            status_code=404,
            detail="Snapshot introuvable. Lancez un audit SEO d'abord.",
        )

    gsc_file = _find_gsc_file(ctx.shop)
    gsc_rows = await asyncio.to_thread(_read_gsc_rows_blocking, gsc_file)
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
