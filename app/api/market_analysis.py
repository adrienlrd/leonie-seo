"""Market analysis API — async job-based SEO/GEO analysis per active product."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query

from app.api.audit import _load_crawl_findings, _load_snapshot, _snapshot_age_days
from app.api.deps import ShopContext, get_shop_context
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
    patch_product_proposals,
    remove_products_from_analysis,
    save_identification_job,
    save_identifications,
    save_latest_result,
    update_job,
)
from app.market_analysis.providers.dataforseo_provider import DataForSEOProvider
from app.market_analysis.providers.google_ads_provider import GoogleAdsKeywordProvider
from app.niche.understanding import get_validated_niche_hypothesis
from app.snapshot.scope import filter_products_by_scope

router = APIRouter(prefix="/api", tags=["market_analysis"])

_DATA_DIR = Path(__file__).parents[2] / "data" / "raw"


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
                normalised.append({
                    "query": query,
                    "impressions": row.get("impressions", 0),
                    "clicks": row.get("clicks", 0),
                    "position": row.get("position", row.get("avg_position", 0)),
                })
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
                len(r.get("seo_keywords", [])) + len(r.get("geo_questions", []))
                for r in partial
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
        update_job(job_id, status="running", total=active_count, progress=0, provider_status=early_provider_status)

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
            progress_callback=_on_progress,
        )
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
            "products": result["products"],
            "progress": result["analyzed_product_count"],
            "total": result["analyzed_product_count"],
            "error": None,
        }
        if persist:
            save_latest_result(shop_domain, completed_data)
        update_job(job_id, **{k: v for k, v in completed_data.items() if k != "job_id"})
    except Exception as exc:
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


@router.post("/shops/{shop}/market-analysis/jobs")
async def start_market_analysis_job(
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
    background_tasks: BackgroundTasks,
    product_ids: list[str] | None = Query(default=None),
    plan: str | None = Query(default=None),
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
    )

    age = _snapshot_age_days(snapshot)
    return {"job_id": job_id, "status": "pending", "snapshot_age_days": age}


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
    return result


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
    }
    proposals = {k: v for k, v in body.items() if k in allowed_keys}
    if proposals:
        proposals["content_quality"] = {
            "publish_ready": False,
            "issues": ["merchant_edit_requires_revalidation"],
        }
    found = patch_product_proposals(ctx.shop, product_id, proposals)
    if not found:
        raise HTTPException(status_code=404, detail=f"Product {product_id} not found in latest analysis")

    return {"saved": True, "faq_sync": None}


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

    gsc_page_rows: dict[str, dict[str, Any]] = {}
    gsc_path = _find_gsc_file(ctx.shop)
    if gsc_path:
        try:
            gsc_page_rows = _parse_gsc_csv(gsc_path.read_text(encoding="utf-8"))
        except OSError:
            pass

    gsc_query_rows = _load_gsc_query_rows(ctx.shop)

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
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Erreur analyse marché : {exc}") from exc

    age = _snapshot_age_days(snapshot)
    return {**result, "snapshot_age_days": age}
