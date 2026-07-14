"""Market analysis API — async job-based SEO/GEO analysis per active product."""

from __future__ import annotations

import asyncio
import json
import os
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel

from app.api.audit import _load_crawl_findings, _load_snapshot, _snapshot_age_days
from app.api.deps import ShopContext, get_shop_context
from app.apply.apply_faq import apply_schema_facts_to_shopify
from app.apply.shopify_writer import ShopifyWriter
from app.billing.quotas import (
    QuotaExceeded,
    check_product_analysis_quota,
    check_quota,
    product_cap,
    record_product_analysis,
    record_usage,
)
from app.blog.auto_draft import auto_create_orphan_drafts
from app.blog.store import list_drafts
from app.business_profile.context import (
    build_business_profile_context_meta,
    resolve_business_profile_context_status,
)
from app.business_profile.jobs import load_business_profile
from app.content_actions.audit import validate_proposal_text
from app.geo.auto_tracking import record_applied_change
from app.geo.continuous_improvement import (
    enrich_market_analysis_result,
    get_product_locked_tags,
    get_shop_retired_tags,
    merge_product_tags,
    reset_all_shop_tags,
    set_product_tag,
)
from app.gsc.client import ensure_fresh_gsc
from app.impact.report import _find_gsc_file, _parse_gsc_csv
from app.learning.models import PRIMARY_WINDOW_DAYS, LearningMode
from app.learning.store import get_settings, record_run
from app.market_analysis.competitors import (
    load_competitors,
    load_excluded_competitors,
    save_competitors,
    save_excluded_competitors,
)
from app.market_analysis.engine import run_market_analysis
from app.market_analysis.identifier import generate_product_labels
from app.market_analysis.jobs import (
    active_job,
    append_job_event,
    create_job,
    get_job,
    load_identification_job,
    load_identifications,
    load_latest_result,
    load_merchant_facts,
    load_question_metadata,
    load_retired_questions,
    patch_product_proposals,
    queue_position,
    remove_products_from_analysis,
    replace_product_analysis,
    restore_question,
    retire_question,
    save_identification_job,
    save_identifications,
    save_latest_result,
    save_merchant_facts,
    save_question_metadata,
    update_job,
)
from app.market_analysis.providers.dataforseo_provider import DataForSEOProvider
from app.market_analysis.providers.google_ads_provider import GoogleAdsKeywordProvider
from app.niche.understanding import get_validated_niche_hypothesis
from app.oauth.token_store import get_token
from app.paths import data_dir
from app.snapshot.scope import filter_products_by_scope

router = APIRouter(prefix="/api", tags=["market_analysis"])

# Serialize heavy market analyses so concurrent merchants don't saturate the
# single API instance's RAM. Default 1 (one at a time); raise via env once the
# instance has more headroom. _run_analysis_background runs in the BackgroundTasks
# threadpool, so this is a threading primitive (not asyncio).
_ANALYSIS_GATE = threading.Semaphore(int(os.getenv("MAX_CONCURRENT_ANALYSES", "1")))

_DATA_DIR = data_dir()
_MERCHANT_FACT_KEYS = frozenset(
    {
        "materials",
        "origins",
        "certifications",
        "warranty",
        "care",
        "dimensions",
        "compatibility",
        "size_recommendation",
        "targets",
        "properties",
        "delivery",
        "returns",
        "use_cases",
        "selection_criteria",
    }
)


def _stored_business_profile_context_hash(context: Any) -> str | None:
    if not isinstance(context, dict):
        return None
    value = context.get("hash")
    return value if isinstance(value, str) and value else None


def _attach_business_profile_context_status(
    result: dict[str, Any],
    current_profile: dict[str, Any] | None,
) -> dict[str, Any]:
    """Attach freshness metadata comparing stored analysis context to current profile."""
    current_context = build_business_profile_context_meta(current_profile)
    top_context = result.get("business_profile_context")
    top_hash = _stored_business_profile_context_hash(top_context)
    top_status = resolve_business_profile_context_status(top_hash, current_profile)

    enriched = dict(result)
    product_statuses: list[str] = []
    products: list[dict[str, Any]] = []
    raw_products = result.get("products", [])
    if not isinstance(raw_products, list):
        raw_products = []
    for product in raw_products:
        if not isinstance(product, dict):
            continue
        product_copy = dict(product)
        product_hash = product_copy.get("business_profile_context_hash")
        if not isinstance(product_hash, str) or not product_hash:
            product_hash = top_hash
        product_status = resolve_business_profile_context_status(product_hash, current_profile)
        product_copy["business_profile_context_status"] = product_status
        product_statuses.append(product_status)
        products.append(product_copy)

    overall_status = top_status
    if current_context.get("hash"):
        if top_status == "stale" or "stale" in product_statuses:
            overall_status = "stale"
        elif top_status == "unknown" or "unknown" in product_statuses:
            overall_status = "unknown"

    enriched["business_profile_context_status"] = overall_status
    enriched["current_business_profile_context"] = current_context
    enriched["products"] = products
    return enriched


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
                normalised.append(
                    {
                        "query": query,
                        "impressions": row.get("impressions", 0),
                        "clicks": row.get("clicks", 0),
                        "position": row.get("position", row.get("avg_position", 0)),
                    }
                )
            return normalised
        except (json.JSONDecodeError, OSError, KeyError, IndexError):
            continue
    return []


def _load_ga4_page_rows(shop: str) -> dict[str, dict[str, Any]]:
    """Load GA4 organic page metrics if GA4 is connected for this shop. Returns {} otherwise."""
    try:
        from app.api.ga4 import _build_ga4_client  # noqa: PLC0415
        from app.ga4.queries import get_organic_by_page  # noqa: PLC0415

        client = _build_ga4_client(shop)
        return get_organic_by_page(client, days=90)
    except Exception:
        return {}


def _run_identification_background(
    job_id: str,
    products: list[dict[str, Any]],
    shop_domain: str,
    niche_summary: str,
) -> None:
    """Background task: generate AI short labels for all active products."""
    try:
        update_job(job_id, status="running")
        labels = generate_product_labels(
            products,
            shop_domain,
            niche_summary,
            progress_callback=lambda done, total: append_job_event(
                job_id, "identification_chunk", {"done": done, "total": total}
            ),
        )
        product_titles = {str(p.get("id", "")): p.get("title", "") for p in products}
        completed_data: dict[str, Any] = {
            "job_id": job_id,
            "shop": shop_domain,
            "status": "completed",
            "labels": labels,
            "product_titles": product_titles,
            "product_count": len(labels),
            "error": None,
        }
        append_job_event(job_id, "identification_completed", {"count": len(labels)})
        update_job(job_id, **{k: v for k, v in completed_data.items() if k != "job_id"})
        save_identification_job(shop_domain, completed_data)
    except Exception as exc:
        update_job(job_id, status="failed", error=str(exc))


def _handle_from_url(url: str) -> str:
    """Extract a product/collection handle from a /products/handle or /collections/.../products/handle URL."""
    url = url.strip().rstrip("/")
    parts = url.split("/")
    if "products" in parts:
        idx = len(parts) - 1 - parts[::-1].index("products") + 1  # noqa: E501 — index after "products"
        if idx < len(parts):
            return parts[idx]
    if parts:
        return parts[-1]
    return ""


def _published_articles_as_snapshot(shop: str) -> list[dict[str, Any]]:
    """Convert the shop's published blog drafts to the snapshot article format.

    The returned dicts match the format expected by build_recommendations():
    { handle, title, keywords[], linked_product_handles[] }
    """
    import logging  # noqa: PLC0415

    logger = logging.getLogger(__name__)
    try:
        drafts = list_drafts(shop)
    except Exception as exc:
        logger.warning("_published_articles_as_snapshot: could not load drafts for %s: %s", shop, exc)
        return []
    articles = []
    for draft in drafts:
        if draft.get("status") != "published_to_shopify":
            continue
        handle = str(draft.get("shopify_article_handle") or "").strip()
        if not handle:
            continue
        linked_handles = [
            _handle_from_url(str(link.get("target_url") or ""))
            for link in (draft.get("internal_links") or [])
            if link.get("target_url")
        ]
        articles.append({
            "handle": handle,
            "title": str(draft.get("blog_title") or ""),
            "keywords": list(draft.get("tags") or []),
            "linked_product_handles": [h for h in linked_handles if h],
        })
    return articles


def _auto_sync_schema_facts(shop: str, products: list[dict[str, Any]]) -> None:
    """Push confirmed facts to the `leonie.schema_facts` metafield for each product.

    Fail-open: a sync error is logged but never blocks the analysis result.
    """
    import logging  # noqa: PLC0415

    logger = logging.getLogger(__name__)
    for product in products:
        pack = product.get("content_test_pack") or {}
        confirmed_facts = pack.get("confirmed_facts") or []
        if not confirmed_facts:
            continue
        pid = product.get("product_id", "")
        if not pid:
            continue
        try:
            apply_schema_facts_to_shopify(shop, pid, confirmed_facts)
        except Exception as exc:
            logger.warning("Auto schema-facts sync failed for %s/%s: %s", shop, pid, exc)


def _apply_retired_and_locked_keywords(
    result: dict[str, Any], shop_domain: str, retired_lower: set[str]
) -> None:
    """Drop retired keyword tags and re-inject merchant-locked keywords in place.

    Ensures deliberately committed keywords survive re-analysis even if the LLM
    didn't pick them, and that retired ones stay out. Shared by the /jobs path and
    the scheduled re-analysis so both produce identical keyword sets.
    """
    if retired_lower:
        for _p in result.get("products") or []:
            _p["seo_keywords"] = [
                kw for kw in (_p.get("seo_keywords") or [])
                if kw.get("query", "").lower().strip() not in retired_lower
            ]

    for _p in result.get("products") or []:
        pid = str(_p.get("product_id") or "")
        if not pid:
            continue
        persisted_tags = get_product_locked_tags(shop_domain, pid)
        existing_queries = {
            kw.get("query", "").lower().strip()
            for kw in (_p.get("seo_keywords") or [])
        }
        for _t in persisted_tags:
            if (
                _t.get("locked_by_merchant")
                and _t.get("status") != "negative"
                and _t.get("tag_type") == "keyword"
                and str(_t.get("label") or "").lower().strip() not in existing_queries
                and str(_t.get("label") or "").lower().strip() not in retired_lower
            ):
                _p.setdefault("seo_keywords", []).append({
                    "query": _t["label"],
                    "intent_type": "commercial",
                    "demand_score": 50,
                    "competition_score": 50,
                    "product_fit_score": 80,
                    "target_role": "secondary",
                    "data_source": "merchant",
                    "priority_score": 60,
                    "locked": True,
                })


def _run_analysis_background(
    job_id: str,
    products: list[dict[str, Any]],
    shop_domain: str,
    gsc_page_rows: dict[str, dict[str, Any]],
    gsc_query_rows: list[dict[str, Any]],
    ga4_page_rows: dict[str, dict[str, Any]],
    niche_hypothesis: dict[str, Any] | None,
    crawl_findings: list[dict[str, Any]] | None,
    identifications: dict[str, str] | None = None,
    persist: bool = True,
    plan: str | None = None,
    merchant_facts_by_product: dict[str, dict[str, str]] | None = None,
    retired_questions_by_product: dict[str, list[str]] | None = None,
    persist_product_results: bool = False,
    business_profile: dict[str, Any] | None = None,
    collections: list[dict[str, Any]] | None = None,
    articles: list[dict[str, Any]] | None = None,
    reflection_test: bool = True,
) -> None:
    """Background task: runs the full analysis and updates the job store incrementally."""
    started_at = datetime.now(UTC)
    last_step: dict[str, Any] = {"phase": None, "done": 0}

    def _on_progress(
        done: int, total: int, partial: list[dict[str, Any]], phase: str = "content"
    ) -> None:
        update_job(
            job_id,
            progress=done,
            total=total,
            status="running",
            phase=phase,
            products=list(partial),
            analyzed_product_count=done,
            total_opportunity_count=sum(
                len(r.get("seo_keywords", [])) + len(r.get("geo_questions", [])) for r in partial
            ),
        )
        # Narrate each finished product exactly once per pass (the activity feed
        # must only report work that actually happened).
        if phase != last_step["phase"]:
            last_step["phase"] = phase
            last_step["done"] = 0
        if done <= last_step["done"] or done > len(partial):
            return
        last_step["done"] = done
        finished = partial[done - 1]
        keywords = finished.get("seo_keywords") or []
        append_job_event(
            job_id,
            "product_targeted" if phase == "targeting" else "product_content_ready",
            {
                "title": str(finished.get("product_title") or ""),
                "keywords": len(keywords),
                "real_keywords": sum(
                    1
                    for kw in keywords
                    if isinstance(kw, dict)
                    and kw.get("data_source") not in (None, "llm_estimated", "llm_proposed", "market_seed")
                ),
                "geo_questions": len(finished.get("geo_questions") or []),
            },
        )

    # Mark the job queued, then block until a concurrency slot frees up so
    # simultaneous analyses run one after another instead of saturating the API.
    update_job(job_id, status="queued", queue_position=queue_position(job_id))
    _ANALYSIS_GATE.acquire()
    try:
        # Compute provider_status early (env-var check only, no I/O) so the
        # frontend sees the correct badges from the very first poll
        early_provider_status: dict[str, Any] = {
            "free": True,
            "dataforseo": DataForSEOProvider().available,
            "google_ads": GoogleAdsKeywordProvider().available,
        }
        active_count = len(filter_products_by_scope(products, "active"))
        update_job(
            job_id,
            status="running",
            total=active_count,
            progress=0,
            provider_status=early_provider_status,
        )
        append_job_event(
            job_id,
            "sources_connected",
            {
                "catalog": True,
                "gsc": bool(gsc_query_rows or gsc_page_rows),
                "ga4": bool(ga4_page_rows),
                "dataforseo": bool(early_provider_status["dataforseo"]),
                "competitor_crawl": bool(crawl_findings),
            },
        )

        retired_labels = get_shop_retired_tags(shop_domain)
        retired_lower = {lbl.lower().strip() for lbl in retired_labels}

        # Merge snapshot articles with the shop's published blog articles so the
        # internal-linking engine sees articles we've already published.
        merged_articles = list(articles or []) + _published_articles_as_snapshot(shop_domain)

        result = run_market_analysis(
            products,
            shop_domain,
            gsc_page_rows,
            gsc_query_rows,
            ga4_page_rows=ga4_page_rows,
            niche_hypothesis=niche_hypothesis,
            crawl_findings=crawl_findings or None,
            max_products=0,
            product_labels=identifications or None,
            plan=plan,
            merchant_facts_by_product=merchant_facts_by_product,
            retired_questions_by_product=retired_questions_by_product,
            business_profile=business_profile,
            progress_callback=_on_progress,
            collections=collections,
            articles=merged_articles,
            reflection_test=reflection_test,
        )

        _apply_retired_and_locked_keywords(result, shop_domain, retired_lower)
        completed_data: dict[str, Any] = {
            "job_id": job_id,
            "shop": shop_domain,
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
            "reflection_test": reflection_test,
            "products": result["products"],
            "progress": result["analyzed_product_count"],
            "total": result["analyzed_product_count"],
            "error": None,
        }
        completed_data = _attach_business_profile_context_status(completed_data, business_profile)
        if persist:
            completed_data = enrich_market_analysis_result(
                shop_domain,
                completed_data,
                persist_tags=True,
                business_profile=business_profile,
                niche_hypothesis=niche_hypothesis,
            )
            save_latest_result(shop_domain, completed_data)
            _auto_sync_schema_facts(shop_domain, completed_data["products"])
            auto_create_orphan_drafts(shop_domain, completed_data)
            auto_publish_checked_proposals(shop_domain, completed_data, niche_hypothesis)
        elif persist_product_results:
            for product_result in completed_data["products"]:
                replace_product_analysis(shop_domain, product_result, result["analyzed_at"])
            _auto_sync_schema_facts(shop_domain, completed_data["products"])
            completed_data = enrich_market_analysis_result(
                shop_domain,
                completed_data,
                persist_tags=True,
                business_profile=business_profile,
                niche_hypothesis=niche_hypothesis,
            )
            auto_publish_checked_proposals(shop_domain, completed_data, niche_hypothesis)
        else:
            completed_data = enrich_market_analysis_result(
                shop_domain,
                completed_data,
                business_profile=business_profile,
                niche_hypothesis=niche_hypothesis,
            )
        append_job_event(
            job_id,
            "analysis_completed",
            {
                "products": int(completed_data.get("analyzed_product_count") or 0),
                "keywords_evaluated": sum(
                    len(p.get("seo_keywords") or [])
                    for p in completed_data.get("products") or []
                    if isinstance(p, dict)
                ),
                "sources": len(completed_data.get("sources_used") or []),
                "duration_s": int((datetime.now(UTC) - started_at).total_seconds()),
            },
        )
        update_job(job_id, **{k: v for k, v in completed_data.items() if k != "job_id"})
    except Exception as exc:
        import logging  # noqa: PLC0415

        logging.getLogger(__name__).exception("Market analysis job %s failed", job_id)
        update_job(job_id, status="failed", error=str(exc))
    finally:
        _ANALYSIS_GATE.release()


@router.post("/shops/{shop}/market-analysis/identify")
async def start_identification_job(
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
    background_tasks: BackgroundTasks,
) -> dict[str, Any]:
    """Start an async job to generate AI short labels for all active products (step 1)."""
    snapshot = _load_snapshot(ctx)
    products = filter_products_by_scope(snapshot.get("products", []), "active")
    niche_hypothesis = get_validated_niche_hypothesis(ctx.shop)
    niche_summary = niche_hypothesis.get("primary_niche", "") if niche_hypothesis else ""
    shop_info = snapshot.get("shop")
    shop_domain = shop_info.get("domain", ctx.shop) if isinstance(shop_info, dict) else ctx.shop

    job_id = create_job(ctx.shop)
    background_tasks.add_task(
        _run_identification_background,
        job_id,
        products,
        shop_domain,
        niche_summary,
    )
    return {"job_id": job_id, "status": "pending", "product_count": len(products)}


@router.get("/shops/{shop}/market-analysis/identify/latest")
async def get_latest_identification(
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
) -> dict[str, Any]:
    """Return the last completed identification job for this shop."""
    result = load_identification_job(ctx.shop)
    if result is None:
        raise HTTPException(status_code=404, detail="Aucune identification précédente disponible")
    return result


@router.post("/shops/{shop}/market-analysis/identifications")
async def save_market_analysis_identifications(
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
    body: dict[str, Any],
) -> dict[str, Any]:
    """Persist merchant-validated product labels {product_id: label}."""
    identifications: dict[str, str] = {
        str(k): str(v) for k, v in body.get("identifications", {}).items()
    }
    save_identifications(ctx.shop, identifications)
    return {"saved": len(identifications)}


@router.post("/shops/{shop}/market-analysis/facts/{product_id:path}")
async def save_market_analysis_facts(
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
    product_id: str,
    body: dict[str, Any],
    background_tasks: BackgroundTasks,
) -> dict[str, Any]:
    """Save confirmed merchant answers and write them to Shopify as leonie.schema_facts.

    Writing to Shopify runs in background so the endpoint returns immediately.
    The metafield is read back by analyze_product_facts on the next analysis,
    so the raw GEO score reflects confirmed facts without waiting for a description publish.
    """
    raw_answers = body.get("answers")
    if not isinstance(raw_answers, dict):
        raise HTTPException(status_code=400, detail="answers must be an object")
    answers = {
        str(key): str(value).strip()[:500]
        for key, value in raw_answers.items()
        if key in _MERCHANT_FACT_KEYS and isinstance(value, str) and value.strip()
    }
    if not answers:
        raise HTTPException(status_code=400, detail="At least one supported answer is required")
    # Merge new answers with all previously saved facts for this product so the
    # Shopify metafield always contains the full accumulated set, not just the delta.
    saved = save_merchant_facts(ctx.shop, product_id, answers)
    confirmed_for_shopify = [
        {
            "key": k,
            "label": k.replace("_", " ").title(),
            "value": v,
            "confidence": "confirmed",
        }
        for k, v in saved.items()
        if v
    ]
    if confirmed_for_shopify:
        background_tasks.add_task(
            apply_schema_facts_to_shopify, ctx.shop, product_id, confirmed_for_shopify
        )
    return {"saved": len(answers), "facts": saved, "shopify_write": bool(confirmed_for_shopify)}


@router.post("/shops/{shop}/market-analysis/auto-publish")
async def trigger_auto_publish_now(
    shop: str,
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
) -> dict[str, Any]:
    """Publish the latest analysis's checked proposals now.

    Used when the merchant turns on automatic publishing: instead of waiting for
    the next analysis, immediately push the checked + safe fields of the latest
    result. Requires auto mode to be already set (the frontend sets it first).
    Subsequent analyses keep auto-publishing via the in-pipeline hook.
    """
    result = load_latest_result(ctx.shop)
    if result is None:
        return {"published": 0, "held": 0, "products": 0, "no_analysis": True}
    niche_hypothesis = get_validated_niche_hypothesis(ctx.shop)
    summary = await asyncio.to_thread(
        auto_publish_checked_proposals, ctx.shop, result, niche_hypothesis
    )
    return summary


@router.post("/shops/{shop}/market-analysis/jobs")
async def start_market_analysis_job(
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
    background_tasks: BackgroundTasks,
    product_ids: list[str] | None = Query(default=None),
    plan: str | None = Query(default=None),
    persist_product_result: bool = Query(default=False),
    reflection_test: bool = Query(default=True),
) -> dict[str, Any]:
    """Start an async market analysis job. Uses saved identifications if available."""
    # Targeted single/multi-product re-analysis is limited per product; a full
    # catalog analysis is limited by the overall "analysis" quota.
    targeted = list(product_ids) if product_ids else []
    try:
        if targeted:
            for pid in targeted:
                check_product_analysis_quota(ctx.shop, pid)
        else:
            check_quota(ctx.shop, "analysis")
    except QuotaExceeded as exc:
        raise HTTPException(status_code=402, detail=exc.payload()) from exc
    # Counted immediately so parallel requests cannot all pass the check above.
    if targeted:
        for pid in targeted:
            record_product_analysis(ctx.shop, pid)
    else:
        record_usage(ctx.shop, "analysis")
    snapshot = _load_snapshot(ctx)
    products = snapshot.get("products", [])
    persist = True
    if product_ids:
        pid_set = set(product_ids)
        products = [p for p in products if str(p.get("id", "")) in pid_set]
        persist = False
    products = products[: product_cap(ctx.shop)]
    shop_info = snapshot.get("shop")
    shop_domain = shop_info.get("domain", ctx.shop) if isinstance(shop_info, dict) else ctx.shop

    niche_hypothesis = get_validated_niche_hypothesis(ctx.shop)
    crawl_findings = _load_crawl_findings(ctx.shop)

    # Auto-refresh GSC if connected + data missing or stale, so the merchant never
    # needs to remember to re-import. Fail-open: if Google is down the analysis
    # still runs without the freshest GSC data.
    ensure_fresh_gsc(ctx.shop)

    gsc_page_rows: dict[str, dict[str, Any]] = {}
    gsc_path = _find_gsc_file(ctx.shop)
    if gsc_path:
        try:
            gsc_page_rows = _parse_gsc_csv(gsc_path.read_text(encoding="utf-8"))
        except OSError:
            pass

    gsc_query_rows = _load_gsc_query_rows(ctx.shop)
    ga4_page_rows = _load_ga4_page_rows(ctx.shop)
    identifications = load_identifications(ctx.shop)  # {} if none saved yet
    merchant_facts = load_merchant_facts(ctx.shop)
    retired_qs = load_retired_questions(ctx.shop)
    business_profile = load_business_profile(ctx.shop)

    job_id = create_job(ctx.shop)

    background_tasks.add_task(
        _run_analysis_background,
        job_id,
        products,
        shop_domain,
        gsc_page_rows,
        gsc_query_rows,
        ga4_page_rows,
        niche_hypothesis,
        crawl_findings,
        identifications or None,
        persist,
        plan,
        merchant_facts or None,
        retired_qs or None,
        persist_product_result,
        business_profile,
        snapshot.get("collections") or [],
        snapshot.get("articles") or [],
        reflection_test,
    )

    age = _snapshot_age_days(snapshot)
    return {
        "job_id": job_id,
        "status": "pending",
        "snapshot_age_days": age,
        "reflection_test": reflection_test,
    }


@router.get("/shops/{shop}/market-analysis/active-job")
async def get_active_market_analysis_job(
    shop: str,
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
) -> dict[str, Any] | None:
    """Return the shop's in-progress analysis job (queued/running) so the UI can resume it.

    Distinct path from /jobs/{job_id} to avoid the path-param catching "active-job".
    """
    return active_job(ctx.shop)


@router.get("/shops/{shop}/market-analysis/jobs/{job_id}")
async def get_market_analysis_job(
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
    job_id: str,
) -> dict[str, Any]:
    """Poll the status and partial results of a market analysis job."""
    job = get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job {job_id} introuvable")
    return job


@router.get("/shops/{shop}/market-analysis/latest")
async def get_latest_market_analysis(
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
) -> dict[str, Any]:
    """Return the last completed analysis for this shop (persisted across restarts)."""
    result = load_latest_result(ctx.shop)
    if result is None:
        raise HTTPException(status_code=404, detail="Aucune analyse précédente disponible")
    enriched = _attach_business_profile_context_status(result, load_business_profile(ctx.shop))
    enriched = enrich_market_analysis_result(ctx.shop, enriched)

    retired_by_product = load_retired_questions(ctx.shop)
    meta_by_product = load_question_metadata(ctx.shop)
    merchant_facts = load_merchant_facts(ctx.shop)
    products = enriched.get("products") or []
    for product in products:
        if not isinstance(product, dict):
            continue
        pid = str(product.get("product_id") or "")
        retired_keys_list = retired_by_product.get(pid, [])
        retired_keys_set = set(retired_keys_list)
        pack = product.get("content_test_pack")
        if not isinstance(pack, dict):
            continue

        # Persist question metadata so we can display them after retirement
        active_qs = pack.get("enrichment_questions") or []
        if active_qs:
            save_question_metadata(ctx.shop, pid, active_qs)
            meta_by_product = load_question_metadata(ctx.shop)

        meta = meta_by_product.get(pid) or {}
        active_keys = {q.get("key") for q in active_qs if isinstance(q, dict) and q.get("key")}
        product_facts = merchant_facts.get(pid) or {}

        # Keys answered by merchant: from confirmed_facts OR from the merchant_facts file
        confirmed_facts = pack.get("confirmed_facts") or []
        answered_keys = {
            f.get("key") for f in confirmed_facts
            if isinstance(f, dict) and f.get("source") == "merchant_confirmation" and f.get("key")
        }
        # Also pick up any key saved via /facts that hasn't been merged yet by a re-analysis
        answered_keys |= set(product_facts.keys())
        auto_completed_keys = answered_keys - active_keys - retired_keys_set

        completed_questions: list[dict[str, Any]] = []
        for k in retired_keys_list:
            q = meta.get(k)
            if q:
                completed_questions.append({
                    **q,
                    "is_retired": True,
                    "answer": product_facts.get(k, ""),
                })
        for k in sorted(auto_completed_keys):
            q = meta.get(k)
            if q:
                completed_questions.append({
                    **q,
                    "is_retired": False,
                    "answer": product_facts.get(k, ""),
                })

        pack["retired_question_keys"] = retired_keys_list
        pack["completed_questions"] = completed_questions
    return enriched


@router.get("/shops/{shop}/market-analysis/products/{product_id:path}/tags")
async def get_market_analysis_product_tags(
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
    product_id: str,
) -> dict[str, Any]:
    """Return current improvement tags for one product."""
    result = load_latest_result(ctx.shop)
    if result is None:
        raise HTTPException(status_code=404, detail="Aucune analyse précédente disponible")
    product = next(
        (p for p in result.get("products", []) if str(p.get("product_id", "")) == str(product_id)),
        None,
    )
    if not isinstance(product, dict):
        raise HTTPException(status_code=404, detail=f"Product {product_id} not found")
    return {
        "product_id": product_id,
        "tags": merge_product_tags(ctx.shop, product, persist=True),
    }


@router.post("/shops/{shop}/market-analysis/products/{product_id:path}/tags")
async def save_market_analysis_product_tag(
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
    product_id: str,
    body: dict[str, Any],
) -> dict[str, Any]:
    """Create or update a merchant-controlled product tag."""
    try:
        tag = set_product_tag(
            ctx.shop,
            product_id,
            label=str(body.get("label") or ""),
            tag_type=str(body.get("tag_type") or "merchant"),
            status=str(body.get("status") or "forced"),
            locked_by_merchant=bool(body.get("locked_by_merchant", True)),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"saved": True, "tag": tag}


@router.post("/shops/{shop}/market-analysis/products/{product_id:path}/tags/{tag_id}/retire")
async def retire_market_analysis_product_tag(
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
    product_id: str,
    tag_id: str,
) -> dict[str, Any]:
    """Mark a tag as retired (excluded from future analyses). Locked — survives re-analysis."""
    result = load_latest_result(ctx.shop)
    product = next(
        (p for p in (result.get("products") or []) if str(p.get("product_id", "")) == product_id),
        None,
    ) if result else None
    existing_label = None
    existing_tag_type = "merchant"
    if product:
        for t in merge_product_tags(ctx.shop, product):
            if t.get("tag_id") == tag_id:
                existing_label = t.get("label")
                existing_tag_type = str(t.get("tag_type") or "merchant")
                break
    if not existing_label:
        raise HTTPException(status_code=404, detail="Tag not found")
    tag = set_product_tag(
        ctx.shop,
        product_id,
        label=existing_label,
        tag_type=existing_tag_type,
        status="negative",
        locked_by_merchant=True,
    )
    return {"retired": True, "tag": tag}


@router.post("/shops/{shop}/market-analysis/products/{product_id:path}/tags/{tag_id}/restore")
async def restore_market_analysis_product_tag(
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
    product_id: str,
    tag_id: str,
) -> dict[str, Any]:
    """Restore a retired tag back to active (positive + locked)."""
    result = load_latest_result(ctx.shop)
    product = next(
        (p for p in (result.get("products") or []) if str(p.get("product_id", "")) == product_id),
        None,
    ) if result else None
    existing_label = None
    existing_tag_type = "merchant"
    if product:
        for t in merge_product_tags(ctx.shop, product):
            if t.get("tag_id") == tag_id:
                existing_label = t.get("label")
                existing_tag_type = str(t.get("tag_type") or "merchant")
                break
    if not existing_label:
        raise HTTPException(status_code=404, detail="Tag not found")
    tag = set_product_tag(
        ctx.shop,
        product_id,
        label=existing_label,
        tag_type=existing_tag_type,
        status="positive",
        locked_by_merchant=True,
    )
    return {"restored": True, "tag": tag}


@router.post("/shops/{shop}/market-analysis/products/{product_id:path}/questions/{key}/retire")
async def retire_enrichment_question(
    shop: str,
    product_id: str,
    key: str,
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
) -> dict[str, Any]:
    """Mark an enrichment question as not relevant for a product."""
    retire_question(ctx.shop, product_id, key)
    return {"retired": True, "key": key, "product_id": product_id}


@router.post("/shops/{shop}/market-analysis/products/{product_id:path}/questions/{key}/restore")
async def restore_enrichment_question(
    shop: str,
    product_id: str,
    key: str,
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
) -> dict[str, Any]:
    """Restore a previously retired enrichment question."""
    restore_question(ctx.shop, product_id, key)
    return {"restored": True, "key": key, "product_id": product_id}


@router.delete("/shops/{shop}/tags/reset")
async def reset_shop_tags(
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
) -> dict[str, Any]:
    """Delete all improvement tags for the shop. Only callable from Account settings."""
    deleted = reset_all_shop_tags(ctx.shop)
    return {"reset": deleted}


@router.delete("/shops/{shop}/reset-all")
async def reset_shop_all_data(
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
) -> dict[str, Any]:
    """Reset the shop to its first-open state: wipe all server-side data except
    the OAuth token and subscription. Only callable from the Danger Zone."""
    from app.oauth.gdpr import reset_shop_data

    result = reset_shop_data(ctx.shop)
    return {"reset": True, **result}


@router.patch("/shops/{shop}/market-analysis/proposals/{product_id:path}")
async def patch_market_analysis_proposals(
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
    product_id: str,
    body: dict[str, Any],
) -> dict[str, Any]:
    """Update editable proposal fields without writing them to Shopify."""
    allowed_keys = {
        "proposed_meta_title",
        "proposed_meta_description",
        "proposed_product_description",
        "proposed_faq",
        "proposed_blog_title",
        "proposed_blog_intro",
        "proposed_blog_outline",
        "proposed_blog_ideas",
        "proposed_image_alts",
    }
    proposals = {k: v for k, v in body.items() if k in allowed_keys}
    if proposals:
        proposals["content_quality"] = {
            "publish_ready": False,
            "issues": ["merchant_edit_requires_revalidation"],
        }
    # Per-product auto-publish checkbox selection — a toggle, not a content edit,
    # so it does not trigger content revalidation.
    if "auto_publish_fields" in body and isinstance(body["auto_publish_fields"], list):
        proposals["auto_publish_fields"] = [
            f for f in body["auto_publish_fields"] if f in _APPLYABLE_FIELDS
        ]
    found = patch_product_proposals(ctx.shop, product_id, proposals)
    if not found:
        raise HTTPException(
            status_code=404, detail=f"Product {product_id} not found in latest analysis"
        )

    return {"saved": True, "faq_sync": None}


@router.post("/shops/{shop}/market-analysis/proposals/{product_id:path}/schema-facts/sync")
async def sync_market_analysis_schema_facts(
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
    product_id: str,
) -> dict[str, Any]:
    """Publish confirmed market-analysis facts to the storefront schema metafield."""
    result = load_latest_result(ctx.shop)
    if result is None:
        raise HTTPException(status_code=404, detail="Aucune analyse précédente disponible")
    product = next(
        (p for p in (result.get("products") or []) if p.get("product_id") == product_id),
        None,
    )
    if not isinstance(product, dict):
        raise HTTPException(
            status_code=404, detail=f"Product {product_id} not found in latest analysis"
        )
    pack = (
        product.get("content_test_pack")
        if isinstance(product.get("content_test_pack"), dict)
        else {}
    )
    confirmed_facts = pack.get("confirmed_facts") if isinstance(pack, dict) else []
    sync_result = await asyncio.to_thread(
        apply_schema_facts_to_shopify,
        ctx.shop,
        product_id,
        confirmed_facts if isinstance(confirmed_facts, list) else [],
    )
    if not sync_result.get("applied"):
        return {"saved": False, "schema_facts_sync": sync_result}
    patch_product_proposals(ctx.shop, product_id, {"schema_facts_sync": sync_result})
    record_applied_change(
        shop=ctx.shop,
        resource_type="product",
        resource_id=product_id,
        resource_title=str(product.get("product_title") or product_id),
        resource_handle=str(product.get("product_handle") or ""),
        action_type="faq_metafield_sync",
        field="schema_facts",
        old_value=None,
        new_value=confirmed_facts if isinstance(confirmed_facts, list) else [],
    )
    return {"saved": True, "schema_facts_sync": sync_result}


class ApplyProposalsRequest(BaseModel):
    fields: list[str]
    confirm_live_write: bool = False


def _apply_proposals_core(
    shop: str,
    access_token: str | None,
    product: dict[str, Any],
    fields: list[str],
) -> dict[str, Any]:
    """Write the selected market-analysis proposals to Shopify (sync).

    Shared by the manual apply endpoint and the auto-publish hook. Records each
    successful write in the GEO ledger (feeds learning) and persists
    ``applied_fields``. Returns ``{"results": ..., "applied_fields": ...}``.
    """
    product_id = str(product.get("product_id") or "")
    pack = product.get("content_test_pack") or {}
    writer = ShopifyWriter(shop, access_token)
    results: dict[str, Any] = {}
    resource_title = str(product.get("product_title") or product_id)
    resource_handle = str(product.get("product_handle") or "")

    seo_fields = [f for f in fields if f in {"meta_title", "meta_description"}]
    if seo_fields:
        title = str(pack.get("proposed_meta_title") or "") if "meta_title" in seo_fields else None
        desc = (
            str(pack.get("proposed_meta_description") or "")
            if "meta_description" in seo_fields
            else None
        )
        r = writer.apply_product_seo(product_id, title or None, desc or None)
        for f in seo_fields:
            results[f] = {"applied": r.applied, "error": r.error}
            if r.applied:
                record_applied_change(
                    shop=shop,
                    resource_type="product",
                    resource_id=product_id,
                    resource_title=resource_title,
                    resource_handle=resource_handle,
                    action_type=f,
                    field=f,
                    old_value=pack.get(f"current_{f}"),
                    new_value=title if f == "meta_title" else desc,
                )

    if "description" in fields:
        proposed_description = str(pack.get("proposed_product_description") or "")
        r = writer.apply_product_description(product_id, proposed_description)
        results["description"] = {"applied": r.applied, "error": r.error}
        if r.applied:
            record_applied_change(
                shop=shop,
                resource_type="product",
                resource_id=product_id,
                resource_title=resource_title,
                resource_handle=resource_handle,
                action_type="product_description",
                field="product_description",
                old_value=pack.get("current_product_description_summary"),
                new_value=proposed_description,
            )

    if "image_alts" in fields:
        image_alts = pack.get("proposed_image_alts") or []
        current_images = {
            str(img.get("id") or ""): img.get("current_alt")
            for img in (pack.get("current_product_images") or [])
            if isinstance(img, dict)
        }
        alt_errors: list[str] = []
        applied_alts: list[dict[str, Any]] = []
        for alt_item in image_alts if isinstance(image_alts, list) else []:
            image_id = str(alt_item.get("image_id") or "")
            proposed_alt = str(alt_item.get("proposed_alt") or "")
            if image_id and proposed_alt:
                r = writer.apply_image_alt(product_id, image_id, proposed_alt)
                if r.applied:
                    applied_alts.append(
                        {
                            "image_id": image_id,
                            "old_alt": current_images.get(image_id),
                            "new_alt": proposed_alt,
                        }
                    )
                elif r.error:
                    alt_errors.append(r.error)
        results["image_alts"] = {
            "applied": bool(applied_alts),
            "applied_count": len(applied_alts),
            "error": "; ".join(alt_errors) if alt_errors else None,
        }
        if applied_alts:
            record_applied_change(
                shop=shop,
                resource_type="product",
                resource_id=product_id,
                resource_title=resource_title,
                resource_handle=resource_handle,
                action_type="alt_text",
                field="alt_text",
                old_value=[item["old_alt"] for item in applied_alts],
                new_value=[item["new_alt"] for item in applied_alts],
            )

    applied_ok = [f for f, r in results.items() if r.get("applied")]
    applied_fields = dict(pack.get("applied_fields") or {})
    if applied_ok:
        now_iso = datetime.now(UTC).isoformat()
        applied_fields.update({f: now_iso for f in applied_ok})
        patch_product_proposals(shop, product_id, {"applied_fields": applied_fields})

    return {"results": results, "applied_fields": applied_fields}


_APPLYABLE_FIELDS = ("meta_title", "meta_description", "description", "image_alts")


def _proposed_text(pack: dict[str, Any], field: str) -> str:
    if field == "meta_title":
        return str(pack.get("proposed_meta_title") or "")
    if field == "meta_description":
        return str(pack.get("proposed_meta_description") or "")
    if field == "description":
        return str(pack.get("proposed_product_description") or "")
    if field == "image_alts":
        alts = pack.get("proposed_image_alts") or []
        return " | ".join(str(a.get("proposed_alt") or "") for a in alts if isinstance(a, dict))
    return ""


def _current_text(pack: dict[str, Any], field: str) -> str:
    if field == "meta_title":
        return str(pack.get("current_meta_title") or "")
    if field == "meta_description":
        return str(pack.get("current_meta_description") or "")
    if field == "description":
        return str(pack.get("current_product_description_summary") or "")
    return ""


def _default_auto_publish_fields(pack: dict[str, Any]) -> list[str]:
    """Fields that have a proposal — the merchant's chosen default (all proposed)."""
    return [f for f in _APPLYABLE_FIELDS if _proposed_text(pack, f)]


# Merchant-facing scope names (learning settings) → applyable field names.
_SCOPE_TO_FIELD = {
    "meta_title": "meta_title",
    "meta_description": "meta_description",
    "alt_text": "image_alts",
    "product_description": "description",
}


def _normalized(text: str) -> str:
    return " ".join(text.split()).casefold()


def _is_noop(pack: dict[str, Any], field: str) -> bool:
    """True when the proposal would not change what is already live."""
    if field == "image_alts":
        current = {
            str(img.get("id") or ""): _normalized(str(img.get("current_alt") or ""))
            for img in (pack.get("current_product_images") or [])
            if isinstance(img, dict)
        }
        proposed = [
            alt
            for alt in (pack.get("proposed_image_alts") or [])
            if isinstance(alt, dict) and str(alt.get("proposed_alt") or "")
        ]
        if not proposed:
            return True
        return all(
            _normalized(str(alt.get("proposed_alt") or ""))
            == current.get(str(alt.get("image_id") or ""), "")
            for alt in proposed
        )
    return _normalized(_proposed_text(pack, field)) == _normalized(_current_text(pack, field))


def _in_cooldown(pack: dict[str, Any], field: str, now: datetime) -> bool:
    """True when the field was auto-applied less than one measurement window ago.

    Re-applying before J+28 recaptures the baseline and the learning window never
    matures — auto mode must wait; a manual apply remains always possible.
    """
    applied_at = (pack.get("applied_fields") or {}).get(field)
    if not applied_at:
        return False
    try:
        applied_dt = datetime.fromisoformat(str(applied_at))
    except ValueError:
        return False
    return (now - applied_dt).days < PRIMARY_WINDOW_DAYS


def _validate_field(
    field: str,
    proposed: str,
    pack: dict[str, Any],
    *,
    forbidden_promises: list[str],
    do_not_say: list[str],
) -> tuple[bool, list[str]]:
    """Validate a field's proposal. image_alts validates each alt individually."""
    if field == "image_alts":
        reasons: list[str] = []
        for alt in pack.get("proposed_image_alts") or []:
            if not isinstance(alt, dict):
                continue
            text = str(alt.get("proposed_alt") or "")
            if not text:
                continue
            safe, alt_reasons = validate_proposal_text(
                "alt_text", text, forbidden_promises=forbidden_promises, do_not_say=do_not_say
            )
            if not safe:
                reasons.extend(alt_reasons)
        return (len(reasons) == 0, sorted(set(reasons)))
    return validate_proposal_text(
        field, proposed, forbidden_promises=forbidden_promises, do_not_say=do_not_say
    )


def auto_publish_checked_proposals(
    shop: str,
    completed_data: dict[str, Any],
    niche_hypothesis: dict[str, Any] | None,
    *,
    db_path: Path | None = None,
    access_token: str | None = None,
) -> dict[str, Any]:
    """Auto-publish the per-product checked proposals when the shop is in auto mode.

    For each product, the checked fields (``auto_publish_fields`` or, if unset,
    all fields with a proposal) are published to Shopify — but only when the
    proposal passes safety validation and differs from the current value.
    Fields that fail validation are held (``auto_publish_held``) for manual
    review and regenerated at the next analysis. No-op when the shop is in
    manual mode or has no Shopify token. Fail-open: never raises.

    ``access_token`` (the string token the caller already holds, e.g. the
    re-analysis job) is preferred; otherwise it is read from the token store.
    ``get_token`` returns a *record dict*, so its ``access_token`` field must be
    extracted — passing the dict straight to ShopifyWriter breaks every write.
    """
    import logging  # noqa: PLC0415

    logger = logging.getLogger(__name__)
    summary = {
        "published": 0,
        "held": 0,
        "products": 0,
        "mode": "manual",
        "skipped_out_of_scope": 0,
        "skipped_cooldown": 0,
        "skipped_noop": 0,
    }
    try:
        settings = get_settings(shop, db_path=db_path)
        if settings.mode != LearningMode.AUTO_APPLY:
            return summary
        summary["mode"] = "auto"
        allowed_fields = {
            _SCOPE_TO_FIELD[scope]
            for scope in settings.auto_publish_scopes
            if scope in _SCOPE_TO_FIELD
        }
        token = access_token
        if not token:
            record = get_token(shop)
            token = record.get("access_token") if isinstance(record, dict) else record
        if not token:
            summary["skipped_reason"] = "no_token"
            return summary

        niche = niche_hypothesis or {}
        forbidden_promises = list(niche.get("forbidden_promises") or [])
        do_not_say = list((niche.get("brand_voice") or {}).get("do_not_say") or [])

        now = datetime.now(UTC)
        for product in completed_data.get("products") or []:
            if not isinstance(product, dict):
                continue
            pack = product.get("content_test_pack") or {}
            if "auto_publish_fields" in pack:
                selected = [f for f in pack["auto_publish_fields"] if f in _APPLYABLE_FIELDS]
            else:
                selected = _default_auto_publish_fields(pack)

            fields_to_apply: list[str] = []
            held: dict[str, list[str]] = {}
            for field in selected:
                proposed = _proposed_text(pack, field)
                if not proposed:
                    continue
                if field not in allowed_fields:
                    summary["skipped_out_of_scope"] += 1
                    continue  # stays a proposal for manual review
                if _is_noop(pack, field):
                    summary["skipped_noop"] += 1
                    continue  # identical → re-publishing would only reset the baseline
                if _in_cooldown(pack, field, now):
                    summary["skipped_cooldown"] += 1
                    continue
                safe, reasons = _validate_field(
                    field,
                    proposed,
                    pack,
                    forbidden_promises=forbidden_promises,
                    do_not_say=do_not_say,
                )
                if safe:
                    fields_to_apply.append(field)
                else:
                    held[field] = reasons

            if fields_to_apply:
                outcome = _apply_proposals_core(shop, token, product, fields_to_apply)
                results = outcome.get("results") or {}
                summary["published"] += sum(
                    1 for r in results.values() if isinstance(r, dict) and r.get("applied")
                )
            patch_product_proposals(shop, str(product.get("product_id") or ""), {"auto_publish_held": held})
            summary["held"] += len(held)
            summary["products"] += 1

        if summary["products"]:
            # An auto-apply cycle IS a run: without this, effectiveness reports
            # NO_RUNS even though changes were applied to the store.
            record_run(
                shop=shop,
                status="completed",
                observations_created=0,
                weights_updated=0,
                actions_reprioritized=0,
                approvals_created=0,
                auto_applied_count=int(summary["published"]),
                errors=[],
                db_path=db_path,
            )
    except Exception:
        logger.exception("auto_publish_checked_proposals failed for shop=%s", shop)
    return summary


@router.post("/shops/{shop}/market-analysis/proposals/{product_id:path}/apply-to-shopify")
async def apply_market_analysis_proposals_to_shopify(
    shop: str,
    product_id: str,
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
    body: ApplyProposalsRequest,
) -> dict[str, Any]:
    """Apply selected market-analysis proposals directly to Shopify."""
    result = load_latest_result(ctx.shop)
    if result is None:
        raise HTTPException(status_code=404, detail="No analysis found")
    product = next(
        (p for p in (result.get("products") or []) if p.get("product_id") == product_id),
        None,
    )
    if not isinstance(product, dict):
        raise HTTPException(
            status_code=404, detail=f"Product {product_id} not found in latest analysis"
        )
    if not body.confirm_live_write:
        return {
            "dry_run": True,
            "shop": ctx.shop,
            "product_id": product_id,
            "fields_requested": body.fields,
        }

    core = await asyncio.to_thread(
        _apply_proposals_core, ctx.shop, ctx.access_token, product, body.fields
    )
    return {
        "shop": ctx.shop,
        "product_id": product_id,
        "results": core["results"],
        "applied_fields": core["applied_fields"],
    }


@router.post("/shops/{shop}/market-analysis/products/remove")
async def remove_market_analysis_products(
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
    body: dict[str, Any],
) -> dict[str, Any]:
    """Remove stale products from the persisted analysis (no longer active in the store)."""
    product_ids = {str(p) for p in body.get("product_ids", []) if p}
    if not product_ids:
        return {"removed": 0}
    removed = remove_products_from_analysis(ctx.shop, product_ids)
    return {"removed": removed}


# ── Competitors (manual entry, used by market analysis) ─────────────────────


@router.get("/shops/{shop}/market-analysis/competitors")
async def list_competitors(
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
) -> dict[str, Any]:
    """Return the manual competitor list and excluded domains for this shop."""
    return {
        "competitors": load_competitors(ctx.shop),
        "excluded": sorted(load_excluded_competitors(ctx.shop)),
    }


@router.put("/shops/{shop}/market-analysis/competitors")
async def replace_competitors(
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
    body: dict[str, Any],
) -> dict[str, Any]:
    """Replace the merchant competitor list and/or excluded domains.

    Body: {"competitors"?: [...], "excluded"?: [...]}. Only the keys present
    are updated, so older clients sending only "competitors" keep working.
    """
    if "competitors" in body:
        raw = body.get("competitors", [])
        if not isinstance(raw, list):
            raise HTTPException(status_code=400, detail="competitors must be a list")
        save_competitors(ctx.shop, raw)
    if "excluded" in body:
        raw_excluded = body.get("excluded", [])
        if not isinstance(raw_excluded, list):
            raise HTTPException(status_code=400, detail="excluded must be a list")
        save_excluded_competitors(ctx.shop, raw_excluded)
    return {
        "competitors": load_competitors(ctx.shop),
        "excluded": sorted(load_excluded_competitors(ctx.shop)),
    }


def _gather_analysis_inputs(ctx: ShopContext) -> dict[str, Any]:
    """Gather snapshot, GSC, and merchant-context data needed by `run_market_analysis`.

    Shared by the legacy synchronous endpoint and the scheduled re-analysis
    pipeline (Task 7), which has no FastAPI request to read this from.
    """
    snapshot = _load_snapshot(ctx)
    products = snapshot.get("products", [])
    shop_info = snapshot.get("shop")
    shop_domain = shop_info.get("domain", ctx.shop) if isinstance(shop_info, dict) else ctx.shop

    niche_hypothesis = get_validated_niche_hypothesis(ctx.shop)
    crawl_findings = _load_crawl_findings(ctx.shop)

    # Auto-refresh GSC (same fail-open behaviour as the full-analysis endpoint).
    ensure_fresh_gsc(ctx.shop)

    gsc_page_rows: dict[str, dict[str, Any]] = {}
    gsc_path = _find_gsc_file(ctx.shop)
    if gsc_path:
        try:
            gsc_page_rows = _parse_gsc_csv(gsc_path.read_text(encoding="utf-8"))
        except OSError:
            pass

    gsc_query_rows = _load_gsc_query_rows(ctx.shop)
    ga4_page_rows = _load_ga4_page_rows(ctx.shop)
    identifications = load_identifications(ctx.shop)  # {} if none saved yet
    merchant_facts = load_merchant_facts(ctx.shop)
    retired_questions = load_retired_questions(ctx.shop)
    business_profile = load_business_profile(ctx.shop)
    # Merge snapshot articles with published blog articles so the internal-linking
    # engine sees articles we've already published (parity with the /jobs path).
    merged_articles = list(snapshot.get("articles") or []) + _published_articles_as_snapshot(shop_domain)

    return {
        "snapshot": snapshot,
        "products": products,
        "shop_domain": shop_domain,
        "niche_hypothesis": niche_hypothesis,
        "crawl_findings": crawl_findings,
        "gsc_page_rows": gsc_page_rows,
        "gsc_query_rows": gsc_query_rows,
        "ga4_page_rows": ga4_page_rows,
        "identifications": identifications,
        "merchant_facts": merchant_facts,
        "retired_questions": retired_questions,
        "business_profile": business_profile,
        "merged_articles": merged_articles,
    }


# Legacy synchronous endpoint kept for backward compatibility
@router.post("/shops/{shop}/market-analysis/run")
async def run_market_analysis_endpoint(
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
    max_products: int = Query(default=10, ge=1, le=20),
    plan: str | None = Query(default=None),
) -> dict[str, Any]:
    """Synchronous analysis (legacy). Prefer the async /jobs endpoint for all products."""
    inputs = _gather_analysis_inputs(ctx)
    snapshot = inputs["snapshot"]
    business_profile = inputs["business_profile"]

    try:
        result = run_market_analysis(
            inputs["products"],
            inputs["shop_domain"],
            inputs["gsc_page_rows"],
            inputs["gsc_query_rows"],
            niche_hypothesis=inputs["niche_hypothesis"],
            crawl_findings=inputs["crawl_findings"] or None,
            max_products=max_products,
            plan=plan,
            merchant_facts_by_product=inputs["merchant_facts"] or None,
            retired_questions_by_product=inputs["retired_questions"] or None,
            business_profile=business_profile,
            collections=snapshot.get("collections") or [],
            articles=snapshot.get("articles") or [],
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Erreur analyse marché : {exc}") from exc

    age = _snapshot_age_days(snapshot)
    enriched = _attach_business_profile_context_status(result, business_profile)
    enriched = enrich_market_analysis_result(ctx.shop, enriched, persist_tags=True)
    return {
        **enriched,
        "snapshot_age_days": age,
    }
