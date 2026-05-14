"""Billing API endpoints — plan listing, subscription management, confirm callback."""

from __future__ import annotations

import logging
import os
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from app.api.deps import ShopContext, get_shop_context
from app.api.plans import plan_summary
from app.billing.client import (
    BILLING_PLANS,
    BillingError,
    cancel_subscription,
    create_subscription,
    get_active_subscriptions,
)
from app.billing.subscription_store import (
    get_plan_for_shop,
    get_subscription,
    update_subscription_status,
    upsert_subscription,
)
from app.oauth.token_store import get_token

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/shops/{shop}", tags=["billing"])


class SubscribeRequest(BaseModel):
    plan: str  # "pro" or "agency"


def _billing_mode() -> str:
    return os.getenv("LEONIE_BILLING_MODE", "live").strip().lower()


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
    if _billing_mode() == "disabled":
        raise HTTPException(status_code=403, detail="Billing is disabled for this environment.")

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
async def billing_confirm(shop: str, charge_id: str | None = None) -> RedirectResponse:
    """Activate a pending subscription after Shopify merchant approval.

    Security model — Shopify redirects here after the merchant approves the
    charge; the URL is not HMAC-signed, so we MUST re-query Shopify with the
    shop's OAuth token to verify the subscription is actually active.

    Steps:
    1. Look up the pending subscription stored for this shop.
    2. Resolve the OAuth token for the shop from token_store.
    3. Query Shopify's currentAppInstallation.activeSubscriptions.
    4. Confirm the stored subscription_id appears in the active list with
       status == "ACTIVE". Only then activate locally.

    Without this verification, any unauthenticated request to
    /billing/confirm?shop=foo.myshopify.com would activate a pending plan
    without payment — a billing bypass.

    Args:
        shop: Shopify shop domain (from Shopify's redirect query string).
        charge_id: Shopify's charge identifier (informational; included by
                   Shopify but not trusted as proof on its own).
    """
    app_url = os.getenv("APP_URL", "http://localhost:5173")

    sub = get_subscription(shop)
    if not sub or sub["status"] != "pending" or not sub["subscription_id"]:
        logger.info(
            "billing.confirm: no pending subscription for shop=%s (charge_id=%s)",
            shop,
            charge_id,
        )
        return RedirectResponse(url=f"{app_url}/?shop={shop}&billing=no_pending")

    # Resolve OAuth token to query Shopify Billing API
    token_record = get_token(shop)
    if not token_record:
        logger.warning("billing.confirm: no OAuth token for shop=%s", shop)
        return RedirectResponse(url=f"{app_url}/?shop={shop}&billing=auth_missing")

    try:
        active = get_active_subscriptions(shop, token_record["access_token"])
    except BillingError as exc:
        logger.error("billing.confirm: Shopify API error for shop=%s: %s", shop, exc)
        return RedirectResponse(url=f"{app_url}/?shop={shop}&billing=verify_failed")

    expected_id = sub["subscription_id"]
    matched = next(
        (s for s in active if s.get("id") == expected_id and s.get("status") == "ACTIVE"),
        None,
    )
    if matched is None:
        logger.warning(
            "billing.confirm: subscription %s not active on Shopify for shop=%s",
            expected_id,
            shop,
        )
        return RedirectResponse(url=f"{app_url}/?shop={shop}&billing=not_active")

    update_subscription_status(expected_id, "active")
    logger.info("billing.confirm: activated subscription %s for shop=%s", expected_id, shop)
    return RedirectResponse(url=f"{app_url}/?shop={shop}&billing=confirmed")
