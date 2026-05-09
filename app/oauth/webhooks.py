"""Shopify webhook handlers — required for App Store compliance."""

import base64
import hashlib
import hmac as hmac_lib
import os

from fastapi import APIRouter, Header, HTTPException, Request

from app.oauth.token_store import delete_token

router = APIRouter()


def _verify_webhook_hmac(body: bytes, header_hmac: str | None, client_secret: str) -> bool:
    """Shopify webhook HMAC: base64(HMAC-SHA256(secret, raw_body))."""
    if not header_hmac:
        return False
    digest = hmac_lib.new(client_secret.encode(), body, hashlib.sha256).digest()
    expected = base64.b64encode(digest).decode()
    return hmac_lib.compare_digest(expected, header_hmac)


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
    if not _verify_webhook_hmac(body, x_shopify_hmac_sha256, secret):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    if not x_shopify_shop_domain:
        raise HTTPException(status_code=400, detail="Missing X-Shopify-Shop-Domain header")

    delete_token(x_shopify_shop_domain)
    return {"status": "uninstalled", "shop": x_shopify_shop_domain}
