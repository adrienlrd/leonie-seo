"""Market analysis API — async job-based SEO/GEO analysis per active product (read-only)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query

from app.api.audit import _load_crawl_findings, _load_snapshot, _snapshot_age_days
from app.api.deps import ShopContext, get_shop_context
from app.impact.report import _find_gsc_file, _parse_gsc_csv
from app.market_analysis.engine import run_market_analysis
from app.market_analysis.jobs import create_job, get_job, update_job
from app.niche.understanding import get_validated_niche_hypothesis

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


def _run_analysis_background(
    job_id: str,
    products: list[dict[str, Any]],
    shop_domain: str,
    gsc_page_rows: dict[str, dict[str, Any]],
    gsc_query_rows: list[dict[str, Any]],
    niche_hypothesis: dict[str, Any] | None,
    crawl_findings: list[dict[str, Any]] | None,
) -> None:
    """Background task: runs the full analysis and updates the job store incrementally."""

    def _on_progress(done: int, total: int, partial: list[dict[str, Any]]) -> None:
        update_job(
            job_id,
            progress=done,
            total=total,
            status="running",
            products=list(partial),
            analyzed_product_count=done,
            total_opportunity_count=sum(
                len(r.get("seo_keywords", [])) + len(r.get("geo_questions", []))
                for r in partial
            ),
        )

    try:
        result = run_market_analysis(
            products,
            shop_domain,
            gsc_page_rows,
            gsc_query_rows,
            niche_hypothesis=niche_hypothesis,
            crawl_findings=crawl_findings or None,
            max_products=0,  # no cap — analyse all active products
            progress_callback=_on_progress,
        )
        update_job(
            job_id,
            status="completed",
            analyzed_at=result["analyzed_at"],
            active_product_count=result["active_product_count"],
            analyzed_product_count=result["analyzed_product_count"],
            total_opportunity_count=result["total_opportunity_count"],
            sources_used=result["sources_used"],
            products=result["products"],
            progress=result["analyzed_product_count"],
            total=result["analyzed_product_count"],
        )
    except Exception as exc:
        update_job(job_id, status="failed", error=str(exc))


@router.post("/shops/{shop}/market-analysis/jobs")
async def start_market_analysis_job(
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
    background_tasks: BackgroundTasks,
) -> dict[str, Any]:
    """Start an async market analysis job. Returns immediately with job_id."""
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

    job_id = create_job(ctx.shop)

    background_tasks.add_task(
        _run_analysis_background,
        job_id,
        products,
        shop_domain,
        gsc_page_rows,
        gsc_query_rows,
        niche_hypothesis,
        crawl_findings,
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


# Legacy synchronous endpoint kept for backward compatibility
@router.post("/shops/{shop}/market-analysis/run")
async def run_market_analysis_endpoint(
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
    max_products: int = Query(default=10, ge=1, le=20),
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
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Erreur analyse marché : {exc}") from exc

    age = _snapshot_age_days(snapshot)
    return {**result, "snapshot_age_days": age}
