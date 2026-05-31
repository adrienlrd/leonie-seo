"""REST endpoints for the llms.txt / llms-full.txt generator and publisher."""

from __future__ import annotations

import json
import logging
import re
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.api.deps import ShopContext, get_shop_context, require_internal_secret
from app.api.snapshot_store import load_snapshot_from_file_or_db
from app.apply.shopify_theme_files import ShopifyThemeError, ShopifyThemeScopeError
from app.business_profile.jobs import load_business_profile
from app.geo.llms_txt import LlmsTxtGenerationError, build_llms_payload
from app.llms_txt import publisher, store
from app.oauth.token_store import get_token
from app.paths import data_dir

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["llms-txt"])

_SHOP_DOMAIN_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9\-]*\.myshopify\.com$")


def _load_snapshot_or_404(ctx: ShopContext) -> dict:
    snapshot = load_snapshot_from_file_or_db(ctx.shop, ctx.snapshot_path)
    if not snapshot:
        raise HTTPException(
            status_code=404,
            detail="No Shopify snapshot available. Run an audit first.",
        )
    return snapshot


def _build_payload_or_422(ctx: ShopContext, snapshot: dict) -> dict:
    business_profile = load_business_profile(ctx.shop)
    try:
        return build_llms_payload(ctx.shop, snapshot, business_profile)
    except LlmsTxtGenerationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/shops/{shop}/llms-txt/generate")
def generate_llms_txt(
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
) -> dict:
    """Generate both files from the latest snapshot. Does NOT publish."""
    snapshot = _load_snapshot_or_404(ctx)
    payload = _build_payload_or_422(ctx, snapshot)

    shop_dir = data_dir() / ctx.shop
    shop_dir.mkdir(parents=True, exist_ok=True)
    (shop_dir / "llms_txt.json").write_text(
        json.dumps(payload, ensure_ascii=False), encoding="utf-8"
    )
    return payload


@router.post("/shops/{shop}/llms-txt/publish")
def publish_llms_txt(
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
) -> dict:
    """Publish the three AI templates (agents.md / llms.txt / llms-full.txt)."""
    snapshot = _load_snapshot_or_404(ctx)
    business_profile = load_business_profile(ctx.shop)
    try:
        return publisher.publish(ctx.shop, ctx.access_token, snapshot, business_profile)
    except LlmsTxtGenerationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ShopifyThemeScopeError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except (ShopifyThemeError, publisher.LlmsPublishError) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/shops/{shop}/llms-txt/unpublish")
def unpublish_llms_txt(
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
) -> dict:
    """Remove the three AI templates, reverting to Shopify's default content."""
    try:
        return publisher.unpublish(ctx.shop, ctx.access_token)
    except ShopifyThemeScopeError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ShopifyThemeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/shops/{shop}/llms-txt/status")
def llms_txt_status(
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
) -> dict:
    """Return the current publication state and snapshot divergence."""
    record = store.get_publication(ctx.shop)
    is_published = bool(record and record.get("is_published"))

    divergent = False
    current_hash: str | None = None
    snapshot = load_snapshot_from_file_or_db(ctx.shop, ctx.snapshot_path)
    if snapshot:
        business_profile = load_business_profile(ctx.shop)
        try:
            current_hash = build_llms_payload(ctx.shop, snapshot, business_profile)["content_hash"]
        except LlmsTxtGenerationError:
            current_hash = None
        if is_published and current_hash and record:
            divergent = current_hash != record.get("llms_hash")

    return {
        "is_published": is_published,
        "content_hash": record.get("llms_hash") if record else None,
        "current_content_hash": current_hash,
        "divergent": divergent,
        "theme_id": record.get("theme_id") if record else None,
        "public_url": f"https://{ctx.shop}{publisher.LLMS_TXT_PATH}",
        "public_full_url": f"https://{ctx.shop}{publisher.LLMS_FULL_TXT_PATH}",
        "public_agents_url": f"https://{ctx.shop}{publisher.AGENTS_PATH}",
        "last_published_at": record.get("last_published_at") if record else None,
        "last_webhook_tick_at": record.get("last_webhook_tick_at") if record else None,
    }


class WebhookTickRequest(BaseModel):
    shop: str


@router.post(
    "/shops/{shop}/llms-txt/webhook-tick",
    dependencies=[Depends(require_internal_secret)],
)
def llms_txt_webhook_tick(shop: str, body: WebhookTickRequest) -> dict:
    """Internal: debounced republish triggered by catalogue webhooks."""
    if body.shop != shop or not _SHOP_DOMAIN_RE.match(shop):
        raise HTTPException(status_code=400, detail="Invalid shop")

    record = get_token(shop)
    if not record:
        raise HTTPException(status_code=403, detail="Shop is not installed")

    snapshot_path = data_dir() / shop / "shopify_snapshot.json"
    snapshot = load_snapshot_from_file_or_db(shop, snapshot_path)
    if not snapshot:
        return {"regenerated": False, "reason": "no_snapshot"}

    business_profile = load_business_profile(shop)
    try:
        return publisher.handle_webhook_tick(
            shop, record["access_token"], snapshot, business_profile
        )
    except (LlmsTxtGenerationError, publisher.LlmsPublishError) as exc:
        logger.warning("Webhook tick republish failed for %s: %s", shop, exc)
        return {"regenerated": False, "reason": "publish_failed", "error": str(exc)}
