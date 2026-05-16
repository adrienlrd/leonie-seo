"""Google Search Console API endpoints for embedded Shopify workflows."""

from __future__ import annotations

from typing import Annotated

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from app.api.deps import ShopContext, get_shop_context
from app.gsc.client import (
    _DATA_DIR,
    GSCConfigurationError,
    build_authorization_url,
    default_site_url,
    exchange_code_for_token,
    google_oauth_configured,
    latest_import_status,
    save_credentials,
)
from app.gsc.oauth_state import GoogleOAuthStateError, create_state, verify_state
from app.gsc.token_store import get_google_token
from app.jobs.store import enqueue
from app.shop_config_store import delete_shop_config, get_shop_config, set_shop_config

router = APIRouter(tags=["gsc"])


class GSCImportRequest(BaseModel):
    days: int = Field(default=90, ge=1, le=180)
    site_url: str | None = None


@router.get("/api/shops/{shop}/gsc/status")
async def gsc_status(ctx: Annotated[ShopContext, Depends(get_shop_context)]) -> dict:
    """Return Google Search Console connection and data freshness status."""
    token = get_google_token(ctx.shop)
    import_status = latest_import_status(ctx.shop)
    return {
        "shop": ctx.shop,
        "configured": google_oauth_configured(),
        "connected": token is not None,
        "email": token.get("email") if token else None,
        "site_url": default_site_url(ctx.shop),
        "latest_import": import_status,
        "action_required": None
        if token
        else "Connect Google Search Console to import real query and page data.",
    }


_PKCE_CONFIG_KEY = "gsc_pkce_verifier"


@router.post("/api/shops/{shop}/gsc/authorize")
async def gsc_authorize(ctx: Annotated[ShopContext, Depends(get_shop_context)]) -> dict:
    """Return the Google OAuth consent URL for the current shop."""
    try:
        state = create_state(ctx.shop)
        authorization_url, code_verifier = build_authorization_url(state)
    except (GoogleOAuthStateError, GSCConfigurationError) as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    if code_verifier:
        set_shop_config(ctx.shop, _PKCE_CONFIG_KEY, code_verifier)
    return {"authorization_url": authorization_url}


@router.post("/api/shops/{shop}/gsc/import", status_code=202)
async def gsc_import(
    body: GSCImportRequest,
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
) -> dict:
    """Enqueue a Search Console import job for the current shop."""
    if get_google_token(ctx.shop) is None:
        raise HTTPException(status_code=409, detail="Google Search Console is not connected")
    job_id = enqueue(
        "gsc_import",
        {"days": body.days, "site_url": body.site_url},
        shop=ctx.shop,
        max_retries=2,
    )
    return {"job_id": job_id, "status": "pending"}


@router.get("/api/shops/{shop}/gsc/opportunities")
async def gsc_opportunities(
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
    min_impressions: int = 10,
    top: int = 20,
) -> dict:
    """Return prioritized SEO opportunities from the latest shop-scoped GSC export."""
    from scripts.audit.detect_gsc_opportunities import detect_opportunities

    gsc_path = _DATA_DIR / ctx.shop / "gsc_performance.csv"
    if not gsc_path.exists():
        return {
            "shop": ctx.shop,
            "available": False,
            "opportunities": [],
            "summary": {"total": 0, "total_estimated_gain_clicks": 0, "by_zone": {}},
            "message": "Connect Google Search Console and import data first.",
        }

    df = pd.read_csv(gsc_path)
    opportunities = detect_opportunities(df, min_impressions=min_impressions, top=top)
    by_zone: dict[str, int] = {}
    for opportunity in opportunities:
        zone = str(opportunity["zone"])
        by_zone[zone] = by_zone.get(zone, 0) + 1

    return {
        "shop": ctx.shop,
        "available": True,
        "opportunities": opportunities,
        "summary": {
            "total": len(opportunities),
            "total_estimated_gain_clicks": sum(
                int(item["estimated_gain_clicks"]) for item in opportunities
            ),
            "by_zone": by_zone,
        },
    }


@router.get("/api/google/gsc/callback", response_class=HTMLResponse)
async def gsc_callback(
    code: Annotated[str, Query()],
    state: Annotated[str, Query()],
) -> str:
    """Handle the Google OAuth callback and store encrypted credentials."""
    try:
        shop = verify_state(state)
        code_verifier = get_shop_config(shop, _PKCE_CONFIG_KEY)
        credentials = exchange_code_for_token(code, code_verifier=code_verifier)
        save_credentials(shop, credentials)
        if code_verifier:
            delete_shop_config(shop, _PKCE_CONFIG_KEY)
    except (GoogleOAuthStateError, GSCConfigurationError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return """
    <!doctype html>
    <html lang="fr">
      <head><meta charset="utf-8"><title>Google Search Console connectée</title></head>
      <body>
        <h1>Google Search Console connectée</h1>
        <p>Vous pouvez fermer cet onglet et revenir dans Léonie SEO.</p>
      </body>
    </html>
    """
