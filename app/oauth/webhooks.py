"""Shopify webhook handlers — required for App Store compliance."""

from __future__ import annotations

import json
import os

from fastapi import APIRouter, Header, HTTPException, Request

from app.apply.theme_entitlement import set_theme_entitlement
from app.billing.subscription_store import (
    get_plan_for_shop,
    get_subscription_by_id,
    update_subscription_status,
)
from app.oauth.hmac_validator import verify_webhook_hmac
from app.oauth.token_store import delete_token

router = APIRouter()


def _require_hmac(body: bytes, header_hmac: str | None) -> None:
    secret = os.getenv("SHOPIFY_CLIENT_SECRET")
    if not secret:
        raise HTTPException(status_code=500, detail="SHOPIFY_CLIENT_SECRET not set")
    if not verify_webhook_hmac(body, header_hmac, secret):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")


@router.post("/app/uninstalled")
async def app_uninstalled(
    request: Request,
    x_shopify_hmac_sha256: str | None = Header(default=None),
    x_shopify_shop_domain: str | None = Header(default=None),
) -> dict:
    """Remove the merchant's access token when they uninstall the app."""
    body = await request.body()
    _require_hmac(body, x_shopify_hmac_sha256)
    if not x_shopify_shop_domain:
        raise HTTPException(status_code=400, detail="Missing X-Shopify-Shop-Domain header")
    delete_token(x_shopify_shop_domain)
    return {"status": "uninstalled", "shop": x_shopify_shop_domain}


@router.post("/app_subscriptions/update")
async def app_subscriptions_update(
    request: Request,
    x_shopify_hmac_sha256: str | None = Header(default=None),
) -> dict:
    """Sync subscription status from Shopify Billing API events.

    Shopify sends this when a subscription status changes:
    PENDING → ACTIVE (approved), ACTIVE → CANCELLED, ACTIVE → FROZEN, etc.
    """
    body = await request.body()
    _require_hmac(body, x_shopify_hmac_sha256)

    try:
        event = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    subscription_gid = event.get("admin_graphql_api_id")
    raw_status = event.get("status", "")
    status = raw_status.lower()

    if subscription_gid and status:
        updated = update_subscription_status(subscription_gid, status)
        _sync_theme_entitlement(subscription_gid)
        return {"updated": updated, "subscription_id": subscription_gid, "status": status}

    return {"updated": False}


def _sync_theme_entitlement(subscription_gid: str) -> None:
    """Grant or revoke the theme-extension entitlement after a status change.

    Best-effort: a metafield write failure must not fail the webhook.
    """
    row = get_subscription_by_id(subscription_gid)
    if not row:
        return
    shop = row["shop"]
    plan = get_plan_for_shop(shop)
    set_theme_entitlement(shop, plan != "free")
