"""Shopify OAuth install/callback handlers."""

import os
import re
from typing import Annotated

import httpx
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import RedirectResponse

from app.oauth.hmac_validator import validate_hmac
from app.oauth.state_store import consume_state, issue_state
from app.oauth.token_store import save_token

router = APIRouter()

_SHOP_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9\-]*\.myshopify\.com$")


def _env(key: str) -> str:
    val = os.getenv(key)
    if not val:
        raise HTTPException(
            status_code=500,
            detail=f"Server misconfigured — missing environment variable: {key}",
        )
    return val


def _is_valid_shop(shop: str) -> bool:
    return bool(_SHOP_RE.match(shop))


@router.get("/install")
async def install(shop: Annotated[str, Query()]) -> RedirectResponse:
    """Step 1 — redirect the merchant to Shopify's OAuth consent screen."""
    if not _is_valid_shop(shop):
        raise HTTPException(status_code=400, detail="Invalid shop domain")

    client_id = _env("SHOPIFY_CLIENT_ID")
    scopes = _env("SHOPIFY_SCOPES")
    redirect_uri = _env("APP_URL").rstrip("/") + "/shopify/callback"

    state = issue_state()

    auth_url = (
        f"https://{shop}/admin/oauth/authorize"
        f"?client_id={client_id}"
        f"&scope={scopes}"
        f"&redirect_uri={redirect_uri}"
        f"&state={state}"
    )
    return RedirectResponse(url=auth_url)


@router.get("/callback")
async def callback(
    shop: Annotated[str, Query()],
    code: Annotated[str, Query()],
    state: Annotated[str, Query()],
    hmac: Annotated[str, Query()],
    timestamp: Annotated[str, Query()] = "",
    host: Annotated[str, Query()] = "",
) -> dict:
    """Step 2 — validate Shopify callback, exchange code for access token."""
    # Defense in depth: the HMAC check below is the real gatekeeper, but
    # validating the shop format first prevents spurious upstream calls.
    if not _is_valid_shop(shop):
        raise HTTPException(status_code=400, detail="Invalid shop domain")

    client_secret = _env("SHOPIFY_CLIENT_SECRET")
    client_id = _env("SHOPIFY_CLIENT_ID")

    params: dict[str, str] = {"shop": shop, "code": code, "state": state, "hmac": hmac}
    if timestamp:
        params["timestamp"] = timestamp
    if host:
        params["host"] = host

    if not validate_hmac(params, client_secret):
        raise HTTPException(status_code=403, detail="Invalid HMAC signature")

    if not consume_state(state):
        raise HTTPException(status_code=403, detail="Invalid or expired state parameter")

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"https://{shop}/admin/oauth/access_token",
            json={"client_id": client_id, "client_secret": client_secret, "code": code},
        )

    if resp.status_code != 200:
        raise HTTPException(status_code=502, detail="Token exchange with Shopify failed")

    data = resp.json()
    access_token: str = data["access_token"]
    scope: str = data.get("scope", "")

    save_token(shop=shop, access_token=access_token, scope=scope)

    return {"status": "installed", "shop": shop, "scope": scope}
