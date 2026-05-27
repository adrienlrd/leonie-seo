"""Business profile API — async job-based niche and brand analysis."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException

from app.api.audit import _load_snapshot
from app.api.deps import ShopContext, get_shop_context
from app.business_profile.analyzer import analyze_business_profile
from app.business_profile.jobs import (
    load_business_profile,
    load_business_profile_job,
    save_business_profile,
    save_business_profile_job,
)
from app.market_analysis.jobs import create_job, get_job, update_job
from app.niche.understanding import get_validated_niche_hypothesis

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
) -> None:
    """Background task: run business profile analysis and persist the result."""
    try:
        update_job(job_id, status="running")
        profile = analyze_business_profile(
            shop=shop,
            snapshot=snapshot,
            gsc_query_rows=gsc_query_rows,
            niche_hypothesis=niche_hypothesis,
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
        update_job(job_id, status="failed", error=str(exc))


@router.post("/shops/{shop}/business-profile/analyze")
async def start_business_profile_analysis(
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
    background_tasks: BackgroundTasks,
) -> dict[str, Any]:
    """Start an async job to analyze the business profile (niche, brand, personas, content style)."""
    snapshot = _load_snapshot(ctx)
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


@router.get("/shops/{shop}/business-profile/latest")
async def get_latest_business_profile(
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
) -> dict[str, Any]:
    """Return the last validated business profile, or the last completed job result."""
    validated = load_business_profile(ctx.shop)
    if validated is not None:
        return validated

    job_result = load_business_profile_job(ctx.shop)
    if job_result is not None and job_result.get("status") == "completed":
        profile = job_result.get("profile")
        if isinstance(profile, dict):
            return profile

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
