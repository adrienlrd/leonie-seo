"""Shopify webhook handlers — required for App Store compliance."""

import os

from fastapi import APIRouter, Header, HTTPException, Request

from app.oauth.hmac_validator import verify_webhook_hmac
from app.oauth.token_store import delete_token

router = APIRouter()


@router.post("/app/uninstalled")
async def app_uninstalled(
    request: Request,
    x_shopify_hmac_sha256: str | None = Header(default=None),
    x_shopify_shop_domain: str | None = Header(default=None),
) -> dict:
    """Remove the merchant's access token when they uninstall the app.

    Shopify guarantees this webhook is sent on uninstall. Storing tokens
    after that is both unnecessary and a compliance risk.
    """
    secret = os.getenv("SHOPIFY_CLIENT_SECRET")
    if not secret:
        raise HTTPException(status_code=500, detail="SHOPIFY_CLIENT_SECRET not set")

    body = await request.body()
    if not verify_webhook_hmac(body, x_shopify_hmac_sha256, secret):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    if not x_shopify_shop_domain:
        raise HTTPException(status_code=400, detail="Missing X-Shopify-Shop-Domain header")

    delete_token(x_shopify_shop_domain)
    return {"status": "uninstalled", "shop": x_shopify_shop_domain}
