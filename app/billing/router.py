"""Billing API endpoints — plan listing, subscription management, confirm callback."""

from __future__ import annotations

import os
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from app.api.deps import ShopContext, get_shop_context
from app.api.plans import plan_summary
from app.billing.client import BILLING_PLANS, BillingError, cancel_subscription, create_subscription
from app.billing.subscription_store import (
    get_plan_for_shop,
    get_subscription,
    update_subscription_status,
    upsert_subscription,
)

router = APIRouter(prefix="/api/shops/{shop}", tags=["billing"])


class SubscribeRequest(BaseModel):
    plan: str  # "pro" or "agency"


@router.get("/billing/plans")
async def list_plans(shop: str) -> dict:
    """Return available plans with prices and features."""
    current_plan = get_plan_for_shop(shop)
    plans = [
        {
            "id": "free",
            "display_name": "Free",
            "price": 0,
            "currency": "USD",
            "features": ["Audit & detection", "SEO score", "1 store"],
            "current": current_plan == "free",
        }
    ]
    for plan_id, cfg in BILLING_PLANS.items():
        plans.append(
            {
                "id": plan_id,
                "display_name": cfg["display_name"],
                "price": float(cfg["price"]),
                "currency": cfg["currency"],
                "features": cfg["features"],
                "current": current_plan == plan_id,
            }
        )
    return {"plans": plans, "current_plan": current_plan}


@router.post("/billing/subscribe")
async def subscribe(
    body: SubscribeRequest,
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
) -> dict:
    """Create a Shopify recurring subscription and return the confirmation URL.

    The merchant must visit the confirmation URL to approve the charge.
    """
    if body.plan not in BILLING_PLANS:
        raise HTTPException(status_code=400, detail=f"Unknown plan: '{body.plan}'")

    app_url = os.getenv("APP_URL", "")
    return_url = f"{app_url}/billing/confirm?shop={ctx.shop}"

    try:
        result = create_subscription(ctx.shop, ctx.access_token, body.plan, return_url)
    except BillingError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    upsert_subscription(
        shop=ctx.shop,
        plan=body.plan,
        status="pending",
        subscription_id=result["subscription_id"],
    )
    return {"confirmation_url": result["confirmation_url"]}


@router.get("/billing/status")
async def billing_status(
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
) -> dict:
    """Return the current plan and subscription status for a shop."""
    sub = get_subscription(ctx.shop)
    plan = get_plan_for_shop(ctx.shop)
    return {
        **plan_summary(plan),
        "subscription_id": sub["subscription_id"] if sub else None,
        "subscription_status": sub["status"] if sub else None,
    }


@router.post("/billing/cancel")
async def cancel(
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
) -> dict:
    """Cancel the active subscription and downgrade the shop to Free."""
    sub = get_subscription(ctx.shop)
    if not sub or sub["status"] != "active" or not sub["subscription_id"]:
        raise HTTPException(status_code=404, detail="No active subscription found.")

    try:
        new_status = cancel_subscription(ctx.shop, ctx.access_token, sub["subscription_id"])
    except BillingError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    update_subscription_status(sub["subscription_id"], new_status)
    return {"status": new_status, "plan": "free"}


# ── Confirm callback (Shopify redirects here after merchant approves) ─────────

billing_confirm_router = APIRouter(tags=["billing"])


@billing_confirm_router.get("/billing/confirm")
async def billing_confirm(shop: str) -> RedirectResponse:
    """Activate a pending subscription after Shopify merchant approval.

    Shopify redirects here after the merchant approves the charge.
    We mark the pending subscription as active and redirect to the dashboard.
    """
    sub = get_subscription(shop)
    if sub and sub["status"] == "pending" and sub["subscription_id"]:
        update_subscription_status(sub["subscription_id"], "active")

    app_url = os.getenv("APP_URL", "http://localhost:5173")
    return RedirectResponse(url=f"{app_url}/?shop={shop}&billing=confirmed")
