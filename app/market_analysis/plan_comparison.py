"""Pro vs Grande boutique comparison — internal diagnostic tool, read-only.

Runs the same rich analysis pipeline as `agent_schedule.reanalysis` twice, once
per plan, so a merchant/dev can see exactly what the "agency" plan's real-time
grounding adds over "pro" on the same catalog data. Deliberately calls
`run_market_analysis` directly (not the `run_market_reanalysis` wrapper): the
wrapper persists results, syncs schema facts, creates blog drafts and can
auto-publish to the live Shopify store — none of that belongs in a comparison
test. This module has zero write side effects, Shopify or DB.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.api.deps import _RAW_DIR, ShopContext
from app.api.market_analysis import _gather_analysis_inputs
from app.billing.quotas import get_quotas
from app.language import get_shop_language
from app.market_analysis.engine import run_market_analysis

_API_VERSION = "2025-01"


def _run_one(
    plan: str,
    *,
    inputs: dict[str, Any],
    shop: str,
    shop_domain: str,
    db_path: Path | None,
    fetch_realtime: bool,
    fetch_realtime_force: bool,
) -> dict[str, Any]:
    products = inputs["products"][: get_quotas(plan)["products"]]
    result = run_market_analysis(
        products,
        shop_domain,
        inputs["gsc_page_rows"],
        inputs["gsc_query_rows"],
        ga4_page_rows=inputs["ga4_page_rows"],
        niche_hypothesis=inputs["niche_hypothesis"],
        crawl_findings=inputs["crawl_findings"] or None,
        max_products=0,
        product_labels=inputs["identifications"] or None,
        plan=plan,
        merchant_facts_by_product=inputs["merchant_facts"] or None,
        retired_questions_by_product=inputs["retired_questions"] or None,
        business_profile=inputs["business_profile"],
        collections=inputs["snapshot"].get("collections") or [],
        articles=inputs["merged_articles"],
        db_path=db_path,
        reflection_test=True,
        fetch_realtime=fetch_realtime,
        fetch_realtime_force=fetch_realtime_force,
        language=get_shop_language(shop),
    )
    result["realtime_grounding_used"] = "realtime_grounding" in result.get("sources_used", [])
    return result


def _plan_diff(result: dict[str, Any]) -> dict[str, Any]:
    """Summarize whether/how grounding actually affected this plan's output —
    answers "did Gemini add value?" without diffing the full result by hand.
    """
    events_used = 0
    signals = result.get("realtime_signals")
    if signals:
        events_used = len(signals.get("events") or []) + len(signals.get("rising_queries") or [])
    realtime_status = result.get("realtime_status") or {}
    verification_status = result.get("market_verification_status") or {}
    return {
        "realtime_grounding_used": result.get("realtime_grounding_used", False),
        "realtime_status": realtime_status.get("status"),
        "realtime_products_attempted": realtime_status.get("products_attempted", 0),
        "realtime_products_ok": realtime_status.get("products_ok", 0),
        "market_verification_status": verification_status.get("status"),
        "market_verification_products_attempted": verification_status.get("products_attempted", 0),
        "market_verification_products_ok": verification_status.get("products_ok", 0),
        "keywords_with_market_verification": result.get("keywords_with_market_verification", 0),
        "events_used": events_used,
    }


def run_plan_comparison(
    shop: str,
    *,
    access_token: str,
    db_path: Path | None = None,
    on_phase: Any | None = None,
) -> dict[str, Any]:
    """Run the analysis once as "pro" and once as "agency" (grounding forced
    on), on the same source data, and return both raw results side by side.

    Never persists (`save_latest_result`), never syncs Shopify (schema facts,
    tags, drafts), never auto-publishes, and never changes the shop's real
    billing plan — purely for comparing the two plans' output.

    ``on_phase`` (optional), called with a single string "pro" or "agency"
    right before that run starts — coarse phase reporting only (each
    sub-analysis is a full multi-product run; per-product progress isn't
    threaded through to keep this diagnostic tool simple).
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
        plan="pro",
    )
    inputs = _gather_analysis_inputs(ctx)
    shop_domain = inputs["shop_domain"]

    if on_phase:
        on_phase("pro")
    pro_result = _run_one(
        "pro",
        inputs=inputs,
        shop=shop,
        shop_domain=shop_domain,
        db_path=db_path,
        fetch_realtime=False,
        fetch_realtime_force=False,
    )

    if on_phase:
        on_phase("agency")
    agency_result = _run_one(
        "agency",
        inputs=inputs,
        shop=shop,
        shop_domain=shop_domain,
        db_path=db_path,
        fetch_realtime=True,
        fetch_realtime_force=True,
    )

    return {
        "compared_at": datetime.now(UTC).isoformat(),
        "shop": shop,
        "pro": pro_result,
        "agency": agency_result,
        "diff_summary": {"pro": _plan_diff(pro_result), "agency": _plan_diff(agency_result)},
    }
