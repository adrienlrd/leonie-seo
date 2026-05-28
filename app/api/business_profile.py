"""Business profile API — async job-based niche and brand analysis."""

from __future__ import annotations

import json
import logging
import traceback
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, BackgroundTasks, Body, Depends, HTTPException

from app.api.deps import ShopContext, get_shop_context
from app.api.snapshot_store import load_snapshot_from_file_or_db
from app.business_profile.analyzer import _PLACEHOLDER_BRAND_NAMES, analyze_business_profile
from app.business_profile.jobs import (
    load_business_profile,
    load_business_profile_job,
    save_business_profile,
    save_business_profile_job,
)
from app.market_analysis.jobs import create_job, get_job, update_job
from app.niche.understanding import get_validated_niche_hypothesis

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["business_profile"])

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


def _run_business_profile_background(
    job_id: str,
    shop: str,
    snapshot: dict[str, Any],
    gsc_query_rows: list[dict[str, Any]],
    niche_hypothesis: dict[str, Any] | None,
    shop_name_hint: str = "",
    focus_keywords: list[str] | None = None,
) -> None:
    """Background task: run business profile analysis and persist the result."""
    try:
        update_job(job_id, status="running")
        profile = analyze_business_profile(
            shop=shop,
            snapshot=snapshot,
            gsc_query_rows=gsc_query_rows,
            niche_hypothesis=niche_hypothesis,
            shop_name_hint=shop_name_hint,
            focus_keywords=focus_keywords,
        )
        completed_data: dict[str, Any] = {
            "job_id": job_id,
            "shop": shop,
            "status": "completed",
            "profile": profile,
            "error": None,
        }
        update_job(job_id, **{k: v for k, v in completed_data.items() if k != "job_id"})
        save_business_profile_job(shop, completed_data)
    except Exception as exc:
        tb = traceback.format_exc()
        logger.error("Business profile job %s failed:\n%s", job_id, tb)
        update_job(job_id, status="failed", error=f"{type(exc).__name__}: {exc}\n{tb}")


def _load_snapshot_safe(ctx: ShopContext) -> dict[str, Any]:
    """Load the Shopify snapshot without raising on missing data."""
    try:
        result = load_snapshot_from_file_or_db(ctx.shop, ctx.snapshot_path)
        return result or {}
    except Exception:
        return {}


@router.post("/shops/{shop}/business-profile/analyze")
async def start_business_profile_analysis(
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
    background_tasks: BackgroundTasks,
    body: dict[str, Any] = Body(default={}),
) -> dict[str, Any]:
    """Start an async job to analyze the business profile (niche, brand, personas, content style)."""
    shop_name_hint = str(body.get("shop_name") or "").strip()
    focus_keywords: list[str] = [str(k) for k in (body.get("focus_keywords") or []) if k]

    snapshot = _load_snapshot_safe(ctx)
    gsc_query_rows = _load_gsc_query_rows(ctx.shop)
    niche_hypothesis = get_validated_niche_hypothesis(ctx.shop)

    job_id = create_job(ctx.shop)
    background_tasks.add_task(
        _run_business_profile_background,
        job_id,
        ctx.shop,
        snapshot,
        gsc_query_rows,
        niche_hypothesis,
        shop_name_hint,
        focus_keywords,
    )
    return {"job_id": job_id, "status": "pending"}


@router.get("/shops/{shop}/business-profile/job/{job_id}")
async def get_business_profile_job(
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
    job_id: str,
) -> dict[str, Any]:
    """Poll the status of a business profile analysis job."""
    job = get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job {job_id} introuvable")
    return job


def _good_brand(name: Any, domain_prefix: str) -> str:
    """Return the name if it is a usable brand (not empty/placeholder/bare domain), else ''."""
    n = str(name or "").strip()
    if not n or n.lower() in _PLACEHOLDER_BRAND_NAMES or n.lower() == domain_prefix.lower():
        return ""
    return n


def _repair_brand_name(profile: dict[str, Any], ctx: ShopContext) -> dict[str, Any]:
    """Backfill a real brand name when a stored profile shows a placeholder or the bare domain.

    Sources, in order: the snapshot store name, then the latest analysis job's
    LLM-inferred name. Never downgrades to the myshopify subdomain.
    """
    domain_prefix = ctx.shop.removesuffix(".myshopify.com")
    if _good_brand(profile.get("brand_name"), domain_prefix):
        return profile

    snapshot = _load_snapshot_safe(ctx)
    snapshot_name = _good_brand((snapshot.get("shop") or {}).get("name"), domain_prefix)

    job = load_business_profile_job(ctx.shop) or {}
    job_profile = job.get("profile") if isinstance(job.get("profile"), dict) else {}
    job_name = _good_brand(job_profile.get("brand_name"), domain_prefix)

    repaired = snapshot_name or job_name
    if repaired:
        profile["brand_name"] = repaired
    return profile


@router.get("/shops/{shop}/business-profile/latest")
async def get_latest_business_profile(
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
) -> dict[str, Any]:
    """Return the last validated business profile, or the last completed job result."""
    validated = load_business_profile(ctx.shop)
    if validated is not None:
        return _repair_brand_name(validated, ctx)

    job_result = load_business_profile_job(ctx.shop)
    if job_result is not None and job_result.get("status") == "completed":
        profile = job_result.get("profile")
        if isinstance(profile, dict):
            return _repair_brand_name(profile, ctx)

    raise HTTPException(status_code=404, detail="Aucun profil entreprise disponible")


@router.post("/shops/{shop}/business-profile")
async def save_validated_business_profile(
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
    body: dict[str, Any],
) -> dict[str, Any]:
    """Persist the merchant-validated business profile."""
    profile = {**body, "status": "validated"}
    save_business_profile(ctx.shop, profile)
    return profile
