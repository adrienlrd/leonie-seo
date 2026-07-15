"""Heavy 14/28-day re-analysis pipeline for the agent scheduler (Task 7).

Orchestration only. The actual catalog crawl, market analysis, and learning
cycle live in their own modules; this module wires them together and decides
*whether* the heavy pipeline should run for a shop on a given tick.

Triggered from `app.agent_schedule.scheduler.run_due_agent_schedules`, at most
once per `reanalysis_frequency_days` window per shop (tracked via
`agent_schedule_settings.last_reanalysis_at`), and only when the shop is not
over its monthly LLM budget.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from fastapi import HTTPException

from app.api.deps import _RAW_DIR, ShopContext
from app.api.market_analysis import (
    _APPLYABLE_FIELDS,
    _apply_retired_and_locked_keywords,
    _attach_business_profile_context_status,
    _auto_sync_schema_facts,
    _gather_analysis_inputs,
    auto_publish_checked_proposals,
)
from app.billing.quotas import product_cap
from app.billing.subscription_store import get_plan_for_shop
from app.blog.auto_draft import auto_create_orphan_drafts
from app.geo.continuous_improvement import enrich_market_analysis_result, get_shop_retired_tags
from app.jobs.store import enqueue_unique
from app.market_analysis.engine import _DEFAULT_BUDGET_USD, _PLAN_BUDGETS_USD, run_market_analysis
from app.market_analysis.jobs import load_latest_result, save_latest_result
from app.observability.metrics import check_budget

logger = logging.getLogger(__name__)

_API_VERSION = "2025-01"


def is_reanalysis_due(
    last_reanalysis_at: str | None,
    frequency_days: int,
    *,
    now: datetime,
) -> bool:
    """Return True if a shop is due for its periodic full re-analysis.

    Never run before counts as due (so every installed shop eventually gets a
    first scheduled re-analysis).
    """
    if not last_reanalysis_at:
        return True
    try:
        last = datetime.fromisoformat(last_reanalysis_at.replace("Z", "+00:00"))
    except ValueError:
        return True
    if last.tzinfo is None:
        last = last.replace(tzinfo=now.tzinfo)
    return (now - last) >= timedelta(days=frequency_days)


def _enqueue_refresh_jobs(shop: str, access_token: str) -> None:
    """Queue a catalog crawl and a GSC import to refresh data for the next cycle.

    Fire-and-forget: this re-analysis run uses whatever snapshot/GSC data is
    already on disk (refreshed inline by `ensure_fresh_gsc` inside
    `_gather_analysis_inputs`); these jobs keep the *next* cycle's data fresh.
    """
    enqueue_unique("seo_audit", {"access_token": access_token}, shop=shop, max_retries=2)
    enqueue_unique("gsc_import", {"days": 28}, shop=shop, max_retries=2)


def _carry_forward_auto_publish_selection(
    shop: str,
    completed_data: dict[str, Any],
    selection: dict[str, list[str]] | None,
    *,
    db_path: Path | None = None,
) -> None:
    """Inject the merchant's per-product ``auto_publish_fields`` into fresh packs.

    A fresh re-analysis regenerates ``content_test_pack`` without the merchant's
    checkbox selection, so ``save_latest_result`` would drop it and auto-publish
    would fall back to *all* proposed fields. Priority: an explicit ``selection``
    (from the re-analysis popup) wins; otherwise the previously persisted
    selection is reused. An **empty list is preserved** (``[]`` = publish nothing
    for that product) — the whole point of respecting an "uncheck all".
    """
    source = selection
    if source is None:
        prior = load_latest_result(shop, db_path=db_path) or {}
        source = {}
        for product in prior.get("products") or []:
            if not isinstance(product, dict):
                continue
            pack = product.get("content_test_pack") or {}
            fields = pack.get("auto_publish_fields")
            if isinstance(fields, list):
                source[str(product.get("product_id") or "")] = fields

    for product in completed_data.get("products") or []:
        if not isinstance(product, dict):
            continue
        product_id = str(product.get("product_id") or "")
        if product_id not in source:
            continue
        pack = product.setdefault("content_test_pack", {})
        pack["auto_publish_fields"] = [f for f in source[product_id] if f in _APPLYABLE_FIELDS]


def run_market_reanalysis(
    shop: str,
    *,
    access_token: str,
    plan: str = "free",
    db_path: Path | None = None,
    selection: dict[str, list[str]] | None = None,
    progress_callback: Any | None = None,
    reflection_test: bool = True,
) -> dict[str, Any]:
    """Run a full market re-analysis for `shop` and persist the result.

    Uses the same rich inputs as the `/market-analysis/jobs` path (GA4, product
    identification labels, published articles merged for internal linking, retired
    tags and merchant-locked keywords) and the plan product cap, so a scheduled /
    encart re-analysis is identical in precision to the products-page analysis.
    Runs synchronously with no FastAPI request context (called from the scheduler);
    an optional ``progress_callback`` streams per-product progress to a job store.
    """
    ctx = ShopContext(
        shop=shop,
        access_token=access_token,
        graphql_endpoint=f"https://{shop}/admin/api/{_API_VERSION}/graphql.json",
        graphql_headers={
            "X-Shopify-Access-Token": access_token,
            "Content-Type": "application/json",
        },
        snapshot_path=_RAW_DIR / shop / "shopify_snapshot.json",
        plan=plan,
    )
    inputs = _gather_analysis_inputs(ctx)
    snapshot = inputs["snapshot"]
    business_profile = inputs["business_profile"]
    niche_hypothesis = inputs["niche_hypothesis"]
    shop_domain = inputs["shop_domain"]
    # Cap the catalog to the plan's product limit (parity with the /jobs path).
    products = inputs["products"][: product_cap(shop, db_path)]

    result = run_market_analysis(
        products,
        shop_domain,
        inputs["gsc_page_rows"],
        inputs["gsc_query_rows"],
        ga4_page_rows=inputs["ga4_page_rows"],
        niche_hypothesis=niche_hypothesis,
        crawl_findings=inputs["crawl_findings"] or None,
        max_products=0,
        product_labels=inputs["identifications"] or None,
        plan=plan,
        merchant_facts_by_product=inputs["merchant_facts"] or None,
        retired_questions_by_product=inputs["retired_questions"] or None,
        business_profile=business_profile,
        progress_callback=progress_callback,
        collections=snapshot.get("collections") or [],
        articles=inputs["merged_articles"],
        db_path=db_path,
        reflection_test=reflection_test,
        # Always a full-catalog run (never targeted), so fetch the real-time
        # signal once per job — internally still gated to the agency plan.
        fetch_realtime=True,
    )

    retired_lower = {lbl.lower().strip() for lbl in get_shop_retired_tags(shop_domain)}
    _apply_retired_and_locked_keywords(result, shop_domain, retired_lower)

    completed_data: dict[str, Any] = {
        "job_id": "scheduled-reanalysis",
        "shop": shop,
        "status": "completed",
        "analyzed_at": result["analyzed_at"],
        "active_product_count": result["active_product_count"],
        "analyzed_product_count": result["analyzed_product_count"],
        "total_opportunity_count": result["total_opportunity_count"],
        "sources_used": result["sources_used"],
        "provider_status": result.get("provider_status", {}),
        "competitor_signals": result.get("competitor_signals", []),
        "cannibalization_alerts": result.get("cannibalization_alerts", []),
        "orphan_products": result.get("orphan_products", []),
        "blog_gap_suggestions": result.get("blog_gap_suggestions", []),
        "business_profile_context": result.get("business_profile_context", {}),
        "products": result["products"],
        "progress": result["analyzed_product_count"],
        "total": result["analyzed_product_count"],
        "error": None,
    }
    completed_data = _attach_business_profile_context_status(completed_data, business_profile)
    completed_data = enrich_market_analysis_result(
        shop,
        completed_data,
        persist_tags=True,
        business_profile=business_profile,
        niche_hypothesis=niche_hypothesis,
        db_path=db_path,
    )
    _carry_forward_auto_publish_selection(shop, completed_data, selection, db_path=db_path)
    save_latest_result(shop, completed_data)
    _auto_sync_schema_facts(shop, completed_data["products"])
    auto_create_orphan_drafts(shop, completed_data)
    completed_data["auto_publish"] = auto_publish_checked_proposals(
        shop, completed_data, niche_hypothesis, db_path=db_path, access_token=access_token
    )
    return completed_data


def run_scheduled_reanalysis(
    shop: str,
    *,
    access_token: str,
    db_path: Path | None = None,
    selection: dict[str, list[str]] | None = None,
    progress_callback: Any | None = None,
) -> dict[str, Any]:
    """Run the heavy re-analysis pipeline for a due shop, respecting the LLM budget.

    Returns ``{"status": "completed", ...}`` on success or
    ``{"status": "skipped", "reason": "budget_exceeded", ...}`` when the shop is
    already over its monthly LLM budget — the caller still runs the lightweight
    learning cycle in that case.
    """
    plan = get_plan_for_shop(shop)
    budget_usd = _PLAN_BUDGETS_USD.get(plan, _DEFAULT_BUDGET_USD)
    budget_status = check_budget(shop, budget_usd, days=30, db_path=db_path)
    if budget_status["over_budget"]:
        logger.info("Skipping scheduled re-analysis for %s: over LLM budget", shop)
        return {"status": "skipped", "reason": "budget_exceeded", "budget": budget_status}

    _enqueue_refresh_jobs(shop, access_token)
    try:
        result = run_market_reanalysis(
            shop,
            access_token=access_token,
            plan=plan,
            db_path=db_path,
            selection=selection,
            progress_callback=progress_callback,
        )
    except HTTPException as exc:
        if exc.status_code == 404:
            logger.info("Skipping scheduled re-analysis for %s: no snapshot on disk", shop)
            return {"status": "skipped", "reason": "no_snapshot"}
        raise
    return {
        "status": "completed",
        "analyzed_at": result.get("analyzed_at"),
        "analyzed_product_count": result.get("analyzed_product_count"),
        "auto_publish": result.get("auto_publish"),
    }
