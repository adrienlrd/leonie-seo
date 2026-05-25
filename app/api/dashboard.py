"""Dashboard aggregator endpoint — single call for the 6-zone merchant dashboard."""

from __future__ import annotations

import os
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query

from app.api.audit import _load_crawl_findings, _load_snapshot, _snapshot_age_days
from app.api.deps import ShopContext, get_shop_context
from app.api.opportunities import _load_gsc_query_rows
from app.db_adapter import DB_PATH, get_conn
from app.geo.ledger import list_geo_events
from app.geo.validation_timeline import build_validation_timeline
from app.impact.report import _find_gsc_file, _parse_gsc_csv
from app.niche.understanding import get_validated_niche_hypothesis
from app.observability.metrics import check_budget, get_shop_metrics
from app.priorities.engine import build_priority_actions

router = APIRouter(prefix="/api", tags=["dashboard"])

_PLAN_BUDGET_USD: dict[str, float] = {
    "free": 0.0,
    "pro": 15.0,
    "agency": 50.0,
}

_READINESS_LEVEL: dict[str, str] = {
    "excellent": "excellent",
    "bon": "bon",
    "partiel": "partiel",
    "faible": "faible",
}


def _readiness_level_en(level_fr: str) -> str:
    return {
        "excellent": "excellent",
        "bon": "good",
        "partiel": "partial",
        "faible": "low",
    }.get(level_fr, level_fr)


def _build_zone1(shop: str, products: list[dict], niche_hypothesis: dict | None) -> dict:
    from app.geo.readiness import score_catalog_readiness  # noqa: PLC0415

    if not products:
        return {
            "global_score": None,
            "global_level": None,
            "products_in_scope": 0,
            "niche_summary": None,
            "niche_validated": False,
        }

    sub_scores: dict[str, int] = {}
    try:
        readiness = score_catalog_readiness(
            products,
            scope="active",
            niche_hypothesis=niche_hypothesis,
        )
        avg = readiness.get("global_score", 0)
        level = readiness.get("global_level", "faible")
        in_scope = readiness.get("total", len(products))

        # Aggregate per-dimension sub-scores across all scored products
        scored_products = readiness.get("products", [])
        if scored_products:
            def _avg_component(key: str) -> int:
                vals = [
                    p.get("components", {}).get(key, {}).get("score", 0)
                    for p in scored_products
                ]
                return round(sum(vals) / len(vals)) if vals else 0

            sub_scores = {
                "seo": _avg_component("seo"),
                "geo": round((_avg_component("schema") + _avg_component("answerability")) / 2),
                "content": _avg_component("facts"),
                "technical": round((_avg_component("commerce") + _avg_component("trust")) / 2),
            }
    except Exception:
        avg, level, in_scope = 0, "faible", len(products)

    niche_summary: str | None = None
    niche_validated = False
    niche_available = False
    if niche_hypothesis:
        summary = niche_hypothesis.get("shop_summary") or {}
        niche_summary = summary.get("what_you_sell")
        niche_validated = niche_hypothesis.get("status") == "validated_by_merchant"
        niche_available = True

    return {
        "global_score": avg,
        "global_level": level,
        "products_in_scope": in_scope,
        "niche_summary": niche_summary,
        "niche_validated": niche_validated,
        "niche_available": niche_available,
        "sub_scores": sub_scores,
    }


def _build_zone2(
    products: list[dict],
    shop_domain: str,
    shop: str,
    gsc_page_rows: dict,
    gsc_query_rows: list,
    niche_hypothesis: dict | None,
    crawl_findings: list | None,
    plan: str,
) -> dict:
    try:
        result = build_priority_actions(
            products,
            shop_domain,
            shop,
            gsc_page_rows,
            gsc_query_rows,
            niche_hypothesis=niche_hypothesis,
            crawl_findings=crawl_findings or None,
            scope="active",
            llm_router=None,
            plan=plan,
        )
        actions = result.get("actions", [])
        sparse_signal = result.get("sparse_signal", False)
        no_action_reason = result.get("no_action_reason")
    except Exception:
        actions, sparse_signal, no_action_reason = [], True, "data_unavailable"

    return {
        "actions": actions[:3],
        "sparse_signal": sparse_signal,
        "no_action_reason": no_action_reason,
    }


def _build_zone3(shop: str, events: list[dict]) -> dict:
    active_count = sum(1 for e in events if e.get("status") == "applied")

    next_milestone_at: str | None = None
    try:
        timeline = build_validation_timeline(events=events)
        next_due = timeline.get("next_due_at")
        if next_due:
            next_milestone_at = (
                next_due.isoformat() if hasattr(next_due, "isoformat") else str(next_due)
            )
    except Exception:
        pass

    sparkline: list[dict] = []
    gsc_path = _find_gsc_file(shop)
    if gsc_path:
        try:
            rows = _parse_gsc_csv(gsc_path.read_text(encoding="utf-8"))
            recent = sorted(rows.items())[-30:]
            sparkline = [
                {"date": k, "value": int(v.get("impressions", 0))}
                for k, v in recent
            ]
        except Exception:
            pass

    trend: str = "flat"
    if len(sparkline) >= 2:
        first_half = sum(p["value"] for p in sparkline[: len(sparkline) // 2])
        second_half = sum(p["value"] for p in sparkline[len(sparkline) // 2 :])
        if second_half > first_half * 1.05:
            trend = "up"
        elif second_half < first_half * 0.95:
            trend = "down"

    return {
        "active_optimizations_count": active_count,
        "next_milestone_at": next_milestone_at,
        "search_performance_sparkline": sparkline,
        "trend": trend,
    }


def _load_dashboard_events(shop: str) -> list[dict[str, Any]]:
    """Return ledger events for the dashboard without failing the whole page."""
    try:
        ledger = list_geo_events(shop, limit=200)
    except Exception:
        return []

    events = ledger.get("events") if isinstance(ledger, dict) else ledger
    if not isinstance(events, list):
        return []
    return [event for event in events if isinstance(event, dict)]


def _build_zone4(shop: str, niche_hypothesis: dict | None, plan: str) -> dict:
    completed: list[str] = ["shopify"]
    pending: list[dict] = []

    try:
        with get_conn(DB_PATH) as conn:
            gsc_row = conn.execute(
                "SELECT 1 FROM google_tokens WHERE shop = ? LIMIT 1", (shop,)
            ).fetchone()
        if gsc_row:
            completed.append("gsc")
        else:
            pending.append({"key": "gsc", "label": "Connecter Google Search Console"})
    except Exception:
        pending.append({"key": "gsc", "label": "Connecter Google Search Console"})

    try:
        with get_conn(DB_PATH) as conn:
            ga4_row = conn.execute(
                "SELECT value FROM shop_config WHERE shop = ? AND key = 'ga4_property_id' LIMIT 1",
                (shop,),
            ).fetchone()
        if ga4_row:
            completed.append("ga4")
        else:
            pending.append({"key": "ga4", "label": "Connecter Google Analytics 4 (recommandé)"})
    except Exception:
        pass

    if niche_hypothesis and niche_hypothesis.get("status") == "validated_by_merchant":
        completed.append("niche")
    else:
        pending.append({"key": "niche", "label": "Valider la niche détectée par l'IA"})

    if plan != "none" and plan in {"pro", "agency"}:
        completed.append("plan")
    elif plan == "free":
        pass
    else:
        pending.append({"key": "plan", "label": "Choisir un plan"})

    return {"completed_steps": completed, "pending_steps": pending}


def _build_zone5(shop: str) -> dict:
    alerts: list[dict] = []
    try:
        with get_conn(DB_PATH) as conn:
            rows = conn.execute(
                """SELECT type, severity, message, url
                   FROM merchant_alerts
                   WHERE shop = ? AND dismissed = 0
                   ORDER BY
                     CASE severity WHEN 'critical' THEN 0 WHEN 'error' THEN 1
                                   WHEN 'warning' THEN 2 ELSE 3 END,
                     created_at DESC
                   LIMIT 3""",
                (shop,),
            ).fetchall()
        alerts = [dict(r) for r in rows]
    except Exception:
        pass
    return {"alerts": alerts}


def _build_llm_budget(shop: str, plan: str) -> dict:
    budget_usd = _PLAN_BUDGET_USD.get(plan, 15.0)
    try:
        result = check_budget(shop, budget_usd)
        return {
            "used_usd": round(result["spent_usd"], 4),
            "limit_usd": budget_usd,
            "pct": round(result["usage_pct"], 1),
        }
    except Exception:
        metrics = {}
        try:
            metrics = get_shop_metrics(shop, days=30)
        except Exception:
            pass
        used = round(metrics.get("total_cost_usd", 0.0), 4)
        pct = round((used / budget_usd * 100) if budget_usd > 0 else 0.0, 1)
        return {"used_usd": used, "limit_usd": budget_usd, "pct": pct}


def _build_banners(shop: str, snapshot: dict) -> dict:
    pilot_safe = os.getenv("LEONIE_PILOT_SAFE_MODE", "").lower() in {"1", "true", "yes"}

    age = _snapshot_age_days(snapshot)
    # Trigger sync when snapshot is missing (age=None) OR older than 7 days
    stale_snapshot = age is None or age > 7

    bulk_in_progress = False
    bulk_current, bulk_total = 0, 0
    try:
        with get_conn(DB_PATH) as conn:
            row = conn.execute(
                """SELECT COUNT(*) AS cnt FROM jobs
                   WHERE shop = ? AND queue = 'bulk_apply' AND status = 'running'""",
                (shop,),
            ).fetchone()
        if row and row["cnt"] > 0:
            bulk_in_progress = True
    except Exception:
        pass

    return {
        "pilot_safe": pilot_safe,
        "stale_snapshot": stale_snapshot,
        "bulk_apply_in_progress": {
            "running": bulk_in_progress,
            "current": bulk_current,
            "total": bulk_total,
        },
    }


@router.get("/shops/{shop}/dashboard")
async def get_dashboard(
    shop: str,
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
    plan: str = Query(default="free", pattern="^(free|pro|agency)$"),
) -> dict[str, Any]:
    """Return the unified merchant dashboard payload aggregating all 6 zones.

    Single call designed to power the app._index.tsx view. Aggregates:
    - Header: LLM budget
    - Zone 1: AI Search Readiness score + niche
    - Zone 2: exactly 3 priority actions
    - Zone 3: active optimizations count + next milestone + sparkline
    - Zone 4: onboarding pending steps
    - Zone 5: top 3 alerts
    - Zone 6: AI visibility status (disabled V1)
    - Banners: pilot_safe, stale_snapshot, bulk_apply

    Args:
        plan: Merchant plan (free|pro|agency).
    """
    snapshot = _load_snapshot(ctx)
    products = snapshot.get("products", [])
    shop_info = snapshot.get("shop")
    shop_domain = (
        shop_info.get("domain", ctx.shop) if isinstance(shop_info, dict) else ctx.shop
    )

    niche_hypothesis = get_validated_niche_hypothesis(ctx.shop)
    crawl_findings = _load_crawl_findings(ctx.shop)

    gsc_page_rows: dict[str, Any] = {}
    gsc_path = _find_gsc_file(ctx.shop)
    if gsc_path:
        try:
            gsc_page_rows = _parse_gsc_csv(gsc_path.read_text(encoding="utf-8"))
        except OSError:
            pass

    gsc_query_rows = _load_gsc_query_rows(ctx.shop)

    events = _load_dashboard_events(ctx.shop)

    zone1 = _build_zone1(ctx.shop, products, niche_hypothesis)
    zone2 = _build_zone2(
        products,
        shop_domain,
        ctx.shop,
        gsc_page_rows,
        gsc_query_rows,
        niche_hypothesis,
        crawl_findings,
        plan,
    )
    zone3 = _build_zone3(ctx.shop, events)
    zone4 = _build_zone4(ctx.shop, niche_hypothesis, plan)
    zone5 = _build_zone5(ctx.shop)
    llm_budget = _build_llm_budget(ctx.shop, plan)
    banners = _build_banners(ctx.shop, snapshot)

    return {
        "shop": ctx.shop,
        "plan": plan,
        "health": "ok",
        "llm_budget": llm_budget,
        "zone1": zone1,
        "zone2": zone2,
        "zone3": zone3,
        "zone4": zone4,
        "zone5": zone5,
        "zone6": {"ai_visibility_enabled": False, "available_in": "v2"},
        "banners": banners,
        "generated_at": datetime.now(UTC).isoformat(),
    }
