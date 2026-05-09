import os
import re
import time
import uuid
from typing import Annotated

import httpx
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import RedirectResponse

from app.oauth.hmac_validator import validate_hmac
from app.oauth.token_store import init_token_table, save_token

router = APIRouter()

_SHOP_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9\-]*\.myshopify\.com$")

# In-memory CSRF state store: state_token -> monotonic timestamp
_pending_states: dict[str, float] = {}
_STATE_TTL = 600  # 10 minutes


def _env(key: str) -> str:
    val = os.getenv(key)
    if not val:
        raise RuntimeError(f"Missing required environment variable: {key}")
    return val


@router.get("/install")
async def install(shop: Annotated[str, Query()]) -> RedirectResponse:
    """Step 1 — redirect the merchant to Shopify's OAuth consent screen."""
    if not _SHOP_RE.match(shop):
        raise HTTPException(status_code=400, detail="Invalid shop domain")

    client_id = _env("SHOPIFY_CLIENT_ID")
    scopes = _env("SHOPIFY_SCOPES")
    redirect_uri = _env("APP_URL").rstrip("/") + "/shopify/callback"

    state = str(uuid.uuid4())
    _pending_states[state] = time.monotonic()

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
    client_secret = _env("SHOPIFY_CLIENT_SECRET")
    client_id = _env("SHOPIFY_CLIENT_ID")

    # Build the exact param dict Shopify signed
    params: dict[str, str] = {"shop": shop, "code": code, "state": state, "hmac": hmac}
    if timestamp:
        params["timestamp"] = timestamp
    if host:
        params["host"] = host

    if not validate_hmac(params, client_secret):
        raise HTTPException(status_code=403, detail="Invalid HMAC signature")

    ts = _pending_states.pop(state, None)
    if ts is None or (time.monotonic() - ts) > _STATE_TTL:
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

    init_token_table()
    save_token(shop=shop, access_token=access_token, scope=scope)

    # Never return the access_token in the response body
    return {"status": "installed", "shop": shop, "scope": scope}
