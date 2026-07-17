"""Billing API endpoints — plan listing, subscription management, confirm callback."""

from __future__ import annotations

import hmac
import logging
import os
import time
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from app.api.deps import ShopContext, get_shop_context
from app.api.plans import plan_summary
from app.apply.theme_entitlement import set_theme_entitlement
from app.billing.client import (
    BILLING_PLANS,
    BillingError,
    cancel_subscription,
    create_subscription,
    get_active_subscriptions,
)
from app.billing.quotas import get_quotas, get_usage, is_plan_upgrade, reset_analysis_usage
from app.billing.subscription_store import (
    get_plan_for_shop,
    get_subscription,
    update_subscription_status,
    upsert_subscription,
)
from app.oauth.token_store import get_token
from app.safety import require_billing_write_allowed
from app.shop_config_store import get_shop_config, set_shop_config

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/shops/{shop}", tags=["billing"])


class SubscribeRequest(BaseModel):
    plan: str  # "pro" or "agency"


class RedeemCodeRequest(BaseModel):
    code: str


# Anti-brute-force on access codes: max failed attempts per shop per window.
_REDEEM_MAX_FAILURES = 10
_REDEEM_WINDOW_SECONDS = 3600
_redeem_failures: dict[str, list[float]] = {}


def _enforce_redeem_rate_limit(shop: str) -> None:
    now = time.monotonic()
    attempts = [t for t in _redeem_failures.get(shop, []) if now - t < _REDEEM_WINDOW_SECONDS]
    _redeem_failures[shop] = attempts
    if len(attempts) >= _REDEEM_MAX_FAILURES:
        raise HTTPException(status_code=429, detail="Too many attempts. Try again later.")


def _record_redeem_failure(shop: str) -> None:
    _redeem_failures.setdefault(shop, []).append(time.monotonic())


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
            "currency": "EUR",
            "features": [],
            "quotas": get_quotas("free"),
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
                "quotas": get_quotas(plan_id),
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
    require_billing_write_allowed(action="billing_subscribe")

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
        "quotas": get_quotas(plan),
        "usage": {
            "analysis": get_usage(ctx.shop, "analysis"),
            "blog": get_usage(ctx.shop, "blog"),
        },
        "override": get_shop_config(ctx.shop, "plan_override") is not None,
        "subscription_id": sub["subscription_id"] if sub else None,
        "subscription_status": sub["status"] if sub else None,
    }


@router.post("/billing/redeem-code")
async def redeem_code(
    body: RedeemCodeRequest,
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
) -> dict:
    """Grant a plan via a partner access code (entitlement override, no charge)."""
    _enforce_redeem_rate_limit(ctx.shop)
    submitted = body.code.strip().upper()
    if not submitted:
        raise HTTPException(status_code=400, detail="Empty code.")
    codes = {
        "pro": os.getenv("LEONIE_ACCESS_CODE_PRO", ""),
        "agency": os.getenv("LEONIE_ACCESS_CODE_AGENCY", ""),
    }
    for plan, expected in codes.items():
        if expected and hmac.compare_digest(submitted, expected.strip().upper()):
            old_plan = get_plan_for_shop(ctx.shop)
            set_shop_config(ctx.shop, "plan_override", plan)
            set_theme_entitlement(ctx.shop, True)
            if is_plan_upgrade(old_plan, plan):
                cleared = reset_analysis_usage(ctx.shop)
                logger.info(
                    "billing.redeem: %s upgraded %s→%s, %d analysis usage events reset",
                    ctx.shop, old_plan, plan, cleared,
                )
            logger.info("billing.redeem: shop=%s granted plan=%s via access code", ctx.shop, plan)
            return {"plan": plan, "override": True}
    _record_redeem_failure(ctx.shop)
    raise HTTPException(status_code=400, detail="Invalid code.")


@router.post("/billing/cancel")
async def cancel(
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
) -> dict:
    """Cancel the active subscription and downgrade the shop to Free."""
    sub = get_subscription(ctx.shop)
    if not sub or sub["status"] != "active" or not sub["subscription_id"]:
        raise HTTPException(status_code=404, detail="No active subscription found.")
    require_billing_write_allowed(action="billing_cancel")

    try:
        new_status = cancel_subscription(ctx.shop, ctx.access_token, sub["subscription_id"])
    except BillingError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    update_subscription_status(sub["subscription_id"], new_status)
    set_theme_entitlement(ctx.shop, get_plan_for_shop(ctx.shop) != "free")
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

    # Compare before/after plans BEFORE activating: the pending row's plan is
    # the upgrade target, get_plan_for_shop still reflects the old entitlement.
    old_plan = get_plan_for_shop(shop)
    update_subscription_status(expected_id, "active")
    set_theme_entitlement(shop, True)
    if is_plan_upgrade(old_plan, str(sub["plan"])):
        cleared = reset_analysis_usage(shop)
        logger.info(
            "billing.confirm: %s upgraded %s→%s, %d analysis usage events reset",
            shop, old_plan, sub["plan"], cleared,
        )
    logger.info("billing.confirm: activated subscription %s for shop=%s", expected_id, shop)
    return RedirectResponse(url=f"{app_url}/?shop={shop}&billing=confirmed")
