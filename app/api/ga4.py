"""GA4 organic funnel API — OAuth2 user credentials + legacy service-account fallback."""

from __future__ import annotations

import asyncio
import os
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from app.api.deps import ShopContext, get_shop_context
from app.ga4.client import GA4Client, GA4Error
from app.ga4.funnel import build_funnel, summarize_funnel
from app.ga4.oauth import (
    GA4OAuthError,
    build_authorization_url,
    disconnect,
    exchange_code,
    ga4_oauth_configured,
    get_credentials,
    list_properties,
    save_credentials,
)
from app.ga4.queries import get_organic_by_page
from app.gsc.oauth_state import GoogleOAuthStateError, create_state, verify_state
from app.gsc.token_store import get_google_token
from app.impact.report import _find_gsc_file, _parse_gsc_csv
from app.shop_config_store import delete_shop_config, get_shop_config, set_shop_config

router = APIRouter(prefix="/api", tags=["ga4"])

_PKCE_CONFIG_KEY = "ga4_pkce_verifier"
_PROPERTY_ID_KEY = "ga4_property_id"
_PROPERTY_NAME_KEY = "ga4_property_name"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _build_ga4_client(shop: str) -> GA4Client:
    """Return an authenticated GA4Client, preferring stored OAuth over env vars."""
    # OAuth path — token stored for this shop
    creds = get_credentials(shop)
    if creds is not None:
        property_id = get_shop_config(shop, _PROPERTY_ID_KEY)
        if not property_id:
            raise HTTPException(
                status_code=409,
                detail="GA4 connected but no property selected. Choose a property first.",
            )
        return GA4Client(property_id, token=creds.token)

    # Legacy service-account fallback (self-hosted / env-var mode)
    property_id = os.getenv("GA4_PROPERTY_ID")
    if not property_id:
        raise HTTPException(
            status_code=503,
            detail="GA4 not connected. Connect via Google OAuth or set GA4_PROPERTY_ID.",
        )
    return GA4Client(property_id)


# ---------------------------------------------------------------------------
# OAuth flow endpoints
# ---------------------------------------------------------------------------


@router.post("/shops/{shop}/ga4/authorize")
async def ga4_authorize(
    shop: str,
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
) -> dict:
    """Return the Google OAuth consent URL for GA4.

    Args:
        shop: Shopify shop domain.
    """
    if not ga4_oauth_configured():
        raise HTTPException(
            status_code=503,
            detail="Google OAuth is not configured (missing GOOGLE_OAUTH_CLIENT_CONFIG).",
        )
    try:
        state = create_state(ctx.shop)
        authorization_url, code_verifier = build_authorization_url(state)
    except (GoogleOAuthStateError, GA4OAuthError) as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    if code_verifier:
        set_shop_config(ctx.shop, _PKCE_CONFIG_KEY, code_verifier)
    return {"authorization_url": authorization_url}


@router.get("/google/ga4/callback", response_class=HTMLResponse)
async def ga4_callback(
    code: Annotated[str, Query()],
    state: Annotated[str, Query()],
) -> str:
    """Handle the Google OAuth callback, store credentials, and confirm to the user."""
    import logging  # noqa: PLC0415

    log = logging.getLogger(__name__)
    try:
        shop = verify_state(state)
        code_verifier = get_shop_config(shop, _PKCE_CONFIG_KEY)
        credentials = exchange_code(code, code_verifier=code_verifier)
        save_credentials(shop, credentials)
        if code_verifier:
            delete_shop_config(shop, _PKCE_CONFIG_KEY)
    except (GoogleOAuthStateError, GA4OAuthError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        log.exception("GA4 OAuth callback failed")
        return HTMLResponse(
            content=f"""
            <!doctype html>
            <html lang="fr">
              <head><meta charset="utf-8"><title>Erreur GA4</title></head>
              <body style="font-family:sans-serif;padding:2rem;max-width:600px;margin:auto">
                <h1>Erreur lors de la connexion GA4</h1>
                <pre style="background:#fee;padding:1rem;border-radius:4px;overflow:auto">{exc.__class__.__name__}: {exc}</pre>
                <p>Fermez cet onglet et réessayez depuis Léonie SEO.</p>
              </body>
            </html>
            """,
            status_code=500,
        )
    return """
    <!doctype html>
    <html lang="fr">
      <head><meta charset="utf-8"><title>Google Analytics connecté</title></head>
      <body style="font-family:sans-serif;padding:2rem;max-width:480px;margin:auto">
        <h1>Google Analytics connecté ✓</h1>
        <p>Vos credentials Google Analytics ont été enregistrés.</p>
        <p>Retournez dans Léonie SEO, sélectionnez votre propriété GA4 et enregistrez.</p>
        <p><small>Vous pouvez fermer cet onglet.</small></p>
      </body>
    </html>
    """


@router.get("/shops/{shop}/ga4/properties")
async def ga4_list_properties(
    shop: str,
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
) -> dict:
    """List GA4 properties accessible to the connected Google account.

    Args:
        shop: Shopify shop domain.
    """
    try:
        props = list_properties(ctx.shop)
    except GA4OAuthError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"shop": ctx.shop, "properties": props}


class PropertySettings(BaseModel):
    property_id: str
    property_name: str = ""


@router.post("/shops/{shop}/ga4/settings")
async def ga4_save_settings(
    shop: str,
    body: PropertySettings,
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
) -> dict:
    """Persist the chosen GA4 property for a shop.

    Args:
        shop: Shopify shop domain.
        body: property_id (numeric) and optional property_name.
    """
    if not body.property_id.strip():
        raise HTTPException(status_code=422, detail="property_id is required")
    set_shop_config(ctx.shop, _PROPERTY_ID_KEY, body.property_id.strip())
    if body.property_name:
        set_shop_config(ctx.shop, _PROPERTY_NAME_KEY, body.property_name)
    return {
        "shop": ctx.shop,
        "property_id": body.property_id,
        "property_name": body.property_name,
        "saved": True,
    }


@router.delete("/shops/{shop}/ga4/disconnect")
async def ga4_disconnect(
    shop: str,
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
) -> dict:
    """Remove stored GA4 credentials and property settings for a shop.

    Args:
        shop: Shopify shop domain.
    """
    disconnect(ctx.shop)
    delete_shop_config(ctx.shop, _PROPERTY_ID_KEY)
    delete_shop_config(ctx.shop, _PROPERTY_NAME_KEY)
    return {"shop": ctx.shop, "disconnected": True}


# ---------------------------------------------------------------------------
# Status
# ---------------------------------------------------------------------------


@router.get("/shops/{shop}/ga4/status")
async def get_ga4_status(
    shop: str,
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
) -> dict:
    """Check GA4 integration status for a shop.

    Returns OAuth connection state, selected property, and whether the
    legacy service-account env vars are set.

    Args:
        shop: Shopify shop domain.
    """
    token_record = get_google_token(ctx.shop)
    # A token exists only if GA4 scope was explicitly granted — GSC uses the same
    # table but saves scope "webmasters.readonly". We check for "analytics" to
    # avoid showing "Connecté" when only GSC is connected.
    scopes_str = (token_record or {}).get("scopes") or ""
    oauth_connected = token_record is not None and "analytics" in scopes_str
    property_id = get_shop_config(ctx.shop, _PROPERTY_ID_KEY)
    property_name = get_shop_config(ctx.shop, _PROPERTY_NAME_KEY)

    # Legacy env-var mode
    env_property_id = os.getenv("GA4_PROPERTY_ID")
    env_creds = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")

    ready = (oauth_connected and bool(property_id)) or bool(env_property_id and env_creds)
    return {
        "shop": ctx.shop,
        "oauth_connected": oauth_connected,
        "oauth_configured": ga4_oauth_configured(),
        "email": token_record.get("email") if token_record else None,
        "property_id": property_id or env_property_id,
        "property_name": property_name,
        "ready": ready,
        # Legacy fields — kept for backward compatibility
        "ga4_property_id_set": bool(property_id or env_property_id),
        "credentials_file_set": bool(oauth_connected or env_creds),
    }


# ---------------------------------------------------------------------------
# Data endpoints
# ---------------------------------------------------------------------------


@router.get("/shops/{shop}/ga4/funnel")
async def get_organic_funnel(
    shop: str,
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
    days: Annotated[int, Query(ge=1, le=365)] = 30,
) -> dict:
    """Return the organic search funnel: impressions → clicks → sessions → conversions → revenue.

    Joins GSC data (from cached snapshot) with GA4 organic data (live API call).

    Args:
        shop: Shopify shop domain.
        days: Lookback window in days (1–365, default 30).
    """
    gsc_file = _find_gsc_file(shop)
    if gsc_file is None:
        raise HTTPException(
            status_code=404,
            detail="No GSC data found. Run 'leonie-seo audit gsc' first.",
        )
    gsc_rows = _parse_gsc_csv(gsc_file.read_text())

    client = _build_ga4_client(ctx.shop)
    try:
        ga4_rows = await asyncio.to_thread(get_organic_by_page, client, days=days)
    except GA4Error as exc:
        raise HTTPException(status_code=502, detail=f"GA4 API error: {exc}") from exc

    funnel = build_funnel(gsc_rows, ga4_rows)
    summary = summarize_funnel(funnel)

    return {
        "shop": shop,
        "days": days,
        "summary": summary,
        "by_url": funnel,
    }
