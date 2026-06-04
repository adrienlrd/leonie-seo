"""Market analysis API — async job-based SEO/GEO analysis per active product."""

from __future__ import annotations

import asyncio
import json
from typing import Annotated, Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel

from app.api.audit import _load_crawl_findings, _load_snapshot, _snapshot_age_days
from app.api.deps import ShopContext, get_shop_context
from app.apply.apply_faq import apply_schema_facts_to_shopify
from app.apply.shopify_writer import ShopifyWriter
from app.blog.auto_draft import auto_create_orphan_drafts
from app.blog.store import list_drafts
from app.business_profile.context import (
    build_business_profile_context_meta,
    resolve_business_profile_context_status,
)
from app.business_profile.jobs import load_business_profile
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
from app.market_analysis.competitors import load_competitors, save_competitors
from app.market_analysis.engine import run_market_analysis
from app.market_analysis.identifier import generate_product_labels
from app.market_analysis.jobs import (
    create_job,
    get_job,
    load_identification_job,
    load_identifications,
    load_latest_result,
    load_merchant_facts,
    load_question_metadata,
    load_retired_questions,
    patch_product_proposals,
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
from app.paths import data_dir
from app.snapshot.scope import filter_products_by_scope

router = APIRouter(prefix="/api", tags=["market_analysis"])

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
        labels = generate_product_labels(products, shop_domain, niche_summary)
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


def _leonie_articles_as_snapshot(shop: str) -> list[dict[str, Any]]:
    """Convert published Léonie blog drafts to the snapshot article format.

    The returned dicts match the format expected by build_recommendations():
    { handle, title, keywords[], linked_product_handles[] }
    """
    import logging  # noqa: PLC0415

    logger = logging.getLogger(__name__)
    try:
        drafts = list_drafts(shop)
    except Exception as exc:
        logger.warning("_leonie_articles_as_snapshot: could not load drafts for %s: %s", shop, exc)
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
    persist_product_results: bool = False,
    business_profile: dict[str, Any] | None = None,
    collections: list[dict[str, Any]] | None = None,
    articles: list[dict[str, Any]] | None = None,
    reflection_test: bool = True,
) -> None:
    """Background task: runs the full analysis and updates the job store incrementally."""

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

        retired_labels = get_shop_retired_tags(shop_domain)
        retired_lower = {lbl.lower().strip() for lbl in retired_labels}

        # Merge snapshot articles with Léonie-published blog articles so the
        # internal-linking engine sees articles we've already published.
        merged_articles = list(articles or []) + _leonie_articles_as_snapshot(shop_domain)

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
            business_profile=business_profile,
            progress_callback=_on_progress,
            collections=collections,
            articles=merged_articles,
            reflection_test=reflection_test,
        )

        if retired_lower:
            for _p in result.get("products") or []:
                _p["seo_keywords"] = [
                    kw for kw in (_p.get("seo_keywords") or [])
                    if kw.get("query", "").lower().strip() not in retired_lower
                ]

        # Inject merchant-added keyword tags into seo_keywords if absent — ensures
        # deliberately committed keywords survive re-analysis even if the LLM didn't pick them.
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
            )
            save_latest_result(shop_domain, completed_data)
            _auto_sync_schema_facts(shop_domain, completed_data["products"])
            auto_create_orphan_drafts(shop_domain, completed_data)
        elif persist_product_results:
            for product_result in completed_data["products"]:
                replace_product_analysis(shop_domain, product_result, result["analyzed_at"])
            _auto_sync_schema_facts(shop_domain, completed_data["products"])
            completed_data = enrich_market_analysis_result(
                shop_domain,
                completed_data,
                persist_tags=True,
            )
        else:
            completed_data = enrich_market_analysis_result(shop_domain, completed_data)
        update_job(job_id, **{k: v for k, v in completed_data.items() if k != "job_id"})
    except Exception as exc:
        import logging  # noqa: PLC0415

        logging.getLogger(__name__).exception("Market analysis job %s failed", job_id)
        update_job(job_id, status="failed", error=str(exc))


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
) -> dict[str, Any]:
    """Save confirmed merchant answers for generation only, without a Shopify write."""
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
    saved = save_merchant_facts(ctx.shop, product_id, answers)
    return {"saved": len(answers), "facts": saved, "shopify_write": False}


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
    snapshot = _load_snapshot(ctx)
    products = snapshot.get("products", [])
    persist = True
    if product_ids:
        pid_set = set(product_ids)
        products = [p for p in products if str(p.get("id", "")) in pid_set]
        persist = False
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
    products = enriched.get("products") or []
    for product in products:
        if not isinstance(product, dict):
            continue
        pid = str(product.get("product_id") or "")
        retired_keys = retired_by_product.get(pid, [])
        pack = product.get("content_test_pack")
        if isinstance(pack, dict):
            # Save current question metadata for future display of retired questions
            active_qs = pack.get("enrichment_questions") or []
            if active_qs:
                save_question_metadata(ctx.shop, pid, active_qs)
                meta_by_product = load_question_metadata(ctx.shop)
            # Build retired questions list from saved metadata
            retired_qs = [
                meta_by_product.get(pid, {}).get(k)
                for k in retired_keys
                if meta_by_product.get(pid, {}).get(k)
            ]
            pack["retired_question_keys"] = retired_keys
            pack["retired_questions"] = [q for q in retired_qs if q]
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
    return {"saved": True, "schema_facts_sync": sync_result}


class ApplyProposalsRequest(BaseModel):
    fields: list[str]
    confirm_live_write: bool = False


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
    pack = product.get("content_test_pack") or {}
    if not body.confirm_live_write:
        return {"dry_run": True, "shop": ctx.shop, "product_id": product_id, "fields_requested": body.fields}

    writer = ShopifyWriter(ctx.shop, ctx.access_token)
    results: dict[str, Any] = {}

    seo_fields = [f for f in body.fields if f in {"meta_title", "meta_description"}]
    if seo_fields:
        title = str(pack.get("proposed_meta_title") or "") if "meta_title" in seo_fields else None
        desc = str(pack.get("proposed_meta_description") or "") if "meta_description" in seo_fields else None
        r = await asyncio.to_thread(writer.apply_product_seo, product_id, title or None, desc or None)
        for f in seo_fields:
            results[f] = {"applied": r.applied, "error": r.error}

    if "description" in body.fields:
        r = await asyncio.to_thread(
            writer.apply_product_description, product_id, str(pack.get("proposed_product_description") or "")
        )
        results["description"] = {"applied": r.applied, "error": r.error}

    if "image_alts" in body.fields:
        image_alts = pack.get("proposed_image_alts") or []
        alt_errors: list[str] = []
        applied_count = 0
        for alt_item in (image_alts if isinstance(image_alts, list) else []):
            image_id = str(alt_item.get("image_id") or "")
            proposed_alt = str(alt_item.get("proposed_alt") or "")
            if image_id and proposed_alt:
                r = await asyncio.to_thread(writer.apply_image_alt, product_id, image_id, proposed_alt)
                if r.applied:
                    applied_count += 1
                elif r.error:
                    alt_errors.append(r.error)
        results["image_alts"] = {
            "applied": applied_count > 0,
            "applied_count": applied_count,
            "error": "; ".join(alt_errors) if alt_errors else None,
        }

    return {"shop": ctx.shop, "product_id": product_id, "results": results}


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
    """Return the manual competitor list for this shop."""
    return {"competitors": load_competitors(ctx.shop)}


@router.put("/shops/{shop}/market-analysis/competitors")
async def replace_competitors(
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
    body: dict[str, Any],
) -> dict[str, Any]:
    """Replace the merchant competitor list. Body: {"competitors": [...]}"""
    raw = body.get("competitors", [])
    if not isinstance(raw, list):
        raise HTTPException(status_code=400, detail="competitors must be a list")
    save_competitors(ctx.shop, raw)
    return {"competitors": load_competitors(ctx.shop)}


# Legacy synchronous endpoint kept for backward compatibility
@router.post("/shops/{shop}/market-analysis/run")
async def run_market_analysis_endpoint(
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
    max_products: int = Query(default=10, ge=1, le=20),
    plan: str | None = Query(default=None),
) -> dict[str, Any]:
    """Synchronous analysis (legacy). Prefer the async /jobs endpoint for all products."""
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
    merchant_facts = load_merchant_facts(ctx.shop)
    retired_questions = load_retired_questions(ctx.shop)
    business_profile = load_business_profile(ctx.shop)

    try:
        result = run_market_analysis(
            products,
            shop_domain,
            gsc_page_rows,
            gsc_query_rows,
            niche_hypothesis=niche_hypothesis,
            crawl_findings=crawl_findings or None,
            max_products=max_products,
            plan=plan,
            merchant_facts_by_product=merchant_facts or None,
            retired_questions_by_product=retired_questions or None,
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
