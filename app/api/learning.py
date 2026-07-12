"""Learning engine API endpoints."""

from __future__ import annotations

import asyncio
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.deps import ShopContext, get_shop_context, require_internal_secret
from app.billing.quotas import auto_analysis_allowed
from app.db_adapter import DB_PATH
from app.learning.approvals import (
    apply_approval,
    bulk_approve_safe,
    edit_approval,
    reject_approval,
)
from app.learning.models import LearningMode
from app.learning.scheduler import run_all_installed_shops, run_learning_cycle, status_snapshot
from app.learning.store import (
    get_settings,
    list_decisions,
    list_observations,
    list_pending_approvals,
    list_weights,
    update_settings,
)

router = APIRouter(prefix="/api", tags=["learning"])


class LearningSettingsRequest(BaseModel):
    enabled: bool | None = None
    mode: LearningMode | None = None
    allow_bulk_approval: bool | None = None
    max_auto_actions_per_cycle: int | None = Field(default=None, ge=0, le=50)
    min_confidence_to_auto_apply: int | None = Field(default=None, ge=0, le=100)
    min_confidence_to_suggest: int | None = Field(default=None, ge=0, le=100)
    require_approval_for_medium_risk: bool | None = None
    reanalysis_frequency_days: int | None = None
    auto_publish_scopes: list[str] | None = None


class LearningRunRequest(BaseModel):
    confirm_live_write: bool = False
    max_actions: int = Field(default=5, ge=1, le=20)


class ApprovalEditRequest(BaseModel):
    proposed_value: str = Field(min_length=1)


def _settings_payload(settings) -> dict[str, Any]:
    return settings.__dict__ | {"mode": settings.mode.value}


@router.get("/shops/{shop}/learning/status")
async def get_learning_status(
    shop: str,
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
) -> dict[str, Any]:
    """Return compact learning status for one shop."""
    return {"shop": ctx.shop, "available": True, **status_snapshot(ctx.shop, db_path=DB_PATH)}


@router.get("/shops/{shop}/learning/weights")
async def get_learning_weights(
    shop: str,
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
    limit: int = 200,
) -> dict[str, Any]:
    """Return merchant-specific and anonymized global weights."""
    return {"shop": ctx.shop, "weights": list_weights(ctx.shop, limit=limit, db_path=DB_PATH)}


@router.get("/shops/{shop}/learning/observations")
async def get_learning_observations(
    shop: str,
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
    limit: int = 200,
) -> dict[str, Any]:
    """Return observed learning outcomes."""
    return {
        "shop": ctx.shop,
        "observations": list_observations(ctx.shop, limit=limit, db_path=DB_PATH),
    }


@router.get("/shops/{shop}/learning/decisions")
async def get_learning_decisions(
    shop: str,
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
    limit: int = 100,
) -> dict[str, Any]:
    """Return recent policy decisions."""
    return {"shop": ctx.shop, "decisions": list_decisions(ctx.shop, limit=limit, db_path=DB_PATH)}


@router.post("/shops/{shop}/learning/run")
async def run_learning_for_shop(
    shop: str,
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
    body: LearningRunRequest,
) -> dict[str, Any]:
    """Run one learning cycle for the authenticated shop."""
    result = await asyncio.to_thread(
        run_learning_cycle,
        ctx.shop,
        access_token=ctx.access_token,
        plan=ctx.plan,
        confirm_live_write=body.confirm_live_write,
        max_actions=body.max_actions,
        db_path=DB_PATH,
    )
    return {"shop": ctx.shop, "available": True, **result}


@router.post("/internal/learning/run", dependencies=[Depends(require_internal_secret)])
async def run_learning_internal() -> dict[str, Any]:
    """Run learning for every installed shop. Suitable for Render Cron."""
    return await asyncio.to_thread(run_all_installed_shops, db_path=DB_PATH)


@router.put("/shops/{shop}/learning/settings")
async def put_learning_settings(
    shop: str,
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
    body: LearningSettingsRequest,
) -> dict[str, Any]:
    """Update merchant learning settings."""
    patch = body.model_dump(exclude_none=True)
    if patch.get("mode") == LearningMode.AUTO_APPLY and not auto_analysis_allowed(ctx.shop):
        raise HTTPException(
            status_code=402,
            detail={
                "error": "quota_exceeded",
                "kind": "auto_analysis",
                "plan": "free",
                "upgrade": "pro",
            },
        )
    settings = update_settings(ctx.shop, patch, db_path=DB_PATH)
    return {"shop": ctx.shop, "settings": _settings_payload(settings)}


@router.get("/shops/{shop}/learning/pending-approvals")
async def get_learning_pending_approvals(
    shop: str,
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
    include_closed: bool = False,
    limit: int = 100,
) -> dict[str, Any]:
    """Return learning-generated actions waiting for merchant validation."""
    return {
        "shop": ctx.shop,
        "approvals": list_pending_approvals(
            ctx.shop,
            include_closed=include_closed,
            limit=limit,
            db_path=DB_PATH,
        ),
    }


@router.post("/shops/{shop}/learning/approvals/{approval_id}/approve")
async def approve_learning_action(
    shop: str,
    approval_id: int,
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
    body: LearningRunRequest | None = None,
) -> dict[str, Any]:
    """Apply one safe learning approval via existing Shopify writers."""
    try:
        result = await asyncio.to_thread(
            apply_approval,
            shop=ctx.shop,
            approval_id=approval_id,
            access_token=ctx.access_token,
            confirm_live_write=(body.confirm_live_write if body else True),
            db_path=DB_PATH,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"shop": ctx.shop, **result}


@router.post("/shops/{shop}/learning/approvals/{approval_id}/reject")
async def reject_learning_action(
    shop: str,
    approval_id: int,
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
) -> dict[str, Any]:
    """Reject one learning approval."""
    try:
        result = reject_approval(shop=ctx.shop, approval_id=approval_id, db_path=DB_PATH)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"shop": ctx.shop, "approval": result}


@router.patch("/shops/{shop}/learning/approvals/{approval_id}/edit")
async def edit_learning_action(
    shop: str,
    approval_id: int,
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
    body: ApprovalEditRequest,
) -> dict[str, Any]:
    """Edit one proposed action before applying it."""
    try:
        result = edit_approval(
            shop=ctx.shop,
            approval_id=approval_id,
            proposed_value=body.proposed_value,
            db_path=DB_PATH,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"shop": ctx.shop, "approval": result}


@router.post("/shops/{shop}/learning/approvals/bulk-approve-safe")
async def bulk_approve_learning_actions(
    shop: str,
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
    body: LearningRunRequest | None = None,
) -> dict[str, Any]:
    """Apply all safe pending learning approvals."""
    result = await asyncio.to_thread(
        bulk_approve_safe,
        shop=ctx.shop,
        access_token=ctx.access_token,
        confirm_live_write=(body.confirm_live_write if body else True),
        db_path=DB_PATH,
    )
    return {"shop": ctx.shop, **result}


@router.get("/shops/{shop}/learning/settings")
async def get_learning_settings(
    shop: str,
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
) -> dict[str, Any]:
    """Return merchant learning settings."""
    return {
        "shop": ctx.shop,
        "settings": _settings_payload(get_settings(ctx.shop, db_path=DB_PATH)),
    }
