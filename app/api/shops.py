"""Shop management endpoints."""

import asyncio
import re
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.api.deps import ShopContext, get_shop_context, require_internal_secret
from app.api.plans import plan_summary
from app.api.snapshot_store import load_snapshot_from_file_or_db
from app.billing.quotas import product_cap
from app.impact.report import _find_gsc_file, _parse_gsc_csv
from app.managed_products import (
    ManagedProductsCapExceeded,
    get_managed_product_ids,
    set_managed_product_ids,
)
from app.oauth.token_store import list_tokens, save_token
from app.safety import is_pilot_safe_mode
from app.snapshot.scope import filter_products_by_scope

router = APIRouter(prefix="/api", tags=["shops"])

_SHOP_DOMAIN_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9\-]*\.myshopify\.com$")


class ShopTokenSync(BaseModel):
    access_token: str
    scope: str = ""


@router.post("/shops/{shop}/internal/token", dependencies=[Depends(require_internal_secret)])
def sync_shop_token(shop: str, body: ShopTokenSync) -> dict:
    """Internal: persist the Remix-issued offline access token for a shop.

    The embedded app authenticates via shopify-app-remix (token exchange) and
    stores its token in the Remix session storage. The Python backend reads
    ``shop_tokens`` for admin writes and webhook-triggered jobs, so the Remix
    ``afterAuth`` hook calls this endpoint to keep that token current. Without
    it, the backend relies on a stale/empty token and Shopify writes 401.
    """
    if not _SHOP_DOMAIN_RE.match(shop):
        raise HTTPException(status_code=400, detail="Invalid shop domain")
    if not body.access_token:
        raise HTTPException(status_code=400, detail="Missing access_token")
    save_token(shop, body.access_token, body.scope)
    return {"saved": True}

# Level-1 indexing diagnosis tuning.
_RECENT_PUBLISH_DAYS = 14  # below this, Google may simply not have crawled yet
_THIN_DESCRIPTION_CHARS = 120  # below this, content is too thin to rank


def _diagnose_visibility_issues(product: dict) -> list[str]:
    """Return heuristic reasons an active product may not be indexed in Google.

    Returns stable issue codes (not localized text) — the frontend maps each
    code to a translated string. Only meaningful for products that have no GSC
    impressions. Codes are ordered from most to least likely root cause.
    """
    issues: list[str] = []

    published_at = product.get("publishedAt") or product.get("published_at")
    if published_at:
        try:
            published = datetime.fromisoformat(str(published_at).replace("Z", "+00:00"))
            if (datetime.now(UTC) - published).days < _RECENT_PUBLISH_DAYS:
                issues.append("recently_published")
        except (ValueError, TypeError):
            pass

    description = str(product.get("description") or "").strip()
    if len(description) < _THIN_DESCRIPTION_CHARS:
        issues.append("thin_content")

    images = product.get("images") or {}
    image_edges = images.get("edges", []) if isinstance(images, dict) else []
    if not image_edges:
        issues.append("no_images")

    seo = product.get("seo") or {}
    has_seo_title = bool(str(seo.get("title") or "").strip())
    has_seo_desc = bool(str(seo.get("description") or "").strip())
    if not has_seo_title and not has_seo_desc:
        issues.append("no_seo_meta")

    collections = product.get("collections") or {}
    coll_edges = collections.get("edges", []) if isinstance(collections, dict) else []
    if not coll_edges:
        issues.append("no_collection")

    return issues


@router.get("/shops", dependencies=[Depends(require_internal_secret)])
async def list_shops() -> list[dict]:
    """List all shops that have completed OAuth installation.

    Admin endpoint — requires X-Internal-Secret. Returns the multi-tenant
    install registry, so it must never be reachable from the public internet
    without the internal secret.
    """
    return list_tokens()


@router.get("/shops/{shop}/status")
async def shop_status(ctx: Annotated[ShopContext, Depends(get_shop_context)]) -> dict:
    """Return shop auth status and whether crawl data is available."""
    snapshot_date: str | None = None
    product_count = 0
    collection_count = 0

    try:
        data = load_snapshot_from_file_or_db(ctx.shop, ctx.snapshot_path)
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    snapshot_exists = data is not None
    if data is not None:
        snapshot_date = data.get("snapshot_date")
        product_count = len(data.get("products", []))
        collection_count = len(data.get("collections", []))

    return {
        "shop": ctx.shop,
        "installed": True,
        "snapshot_available": snapshot_exists,
        "snapshot_date": snapshot_date,
        "product_count": product_count,
        "collection_count": collection_count,
        "pilot_safe_mode": is_pilot_safe_mode(),
        **plan_summary(ctx.plan),
    }


@router.get("/shops/{shop}/products/active")
async def list_active_products(ctx: Annotated[ShopContext, Depends(get_shop_context)]) -> list[dict]:
    """Return active (ACTIVE + published) products from the latest snapshot.

    Returns a lightweight list of {id, title, handle, image_url} for each active
    product. Used by the dashboard to display the active catalog at a glance.
    """
    try:
        result = await asyncio.to_thread(_build_active_products, ctx)
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return result


def _build_active_products(ctx: ShopContext) -> list[dict]:
    """Blocking: snapshot read/parse can be a 10-100MB file, must not run on the event loop."""
    data = load_snapshot_from_file_or_db(ctx.shop, ctx.snapshot_path)

    if data is None:
        return []

    products = filter_products_by_scope(data.get("products", []), "active")

    # Build GSC visibility map: product URL → has impressions in GSC
    # Use primaryDomain.host (custom domain) so URLs match GSC records.
    # Fall back to myshopifyDomain, then the shop auth identifier.
    shop_obj = data.get("shop") or {}
    shop_domain = (
        (shop_obj.get("primaryDomain") or {}).get("host")
        or str(shop_obj.get("myshopifyDomain") or ctx.shop)
    )
    gsc_page_rows: dict[str, dict] = {}
    gsc_file = _find_gsc_file(ctx.shop)
    if gsc_file:
        try:
            gsc_page_rows = _parse_gsc_csv(gsc_file.read_text(encoding="utf-8"))
        except Exception:
            pass

    # True when GSC data exists for this shop — used by the UI to decide
    # whether to show visibility badges independently of per-product matches.
    gsc_connected = bool(gsc_page_rows)

    result = []
    for p in products:
        image_url: str | None = None
        images = p.get("images") or {}
        edges = images.get("edges", []) if isinstance(images, dict) else []
        if edges and isinstance(edges[0], dict):
            node = edges[0].get("node", {})
            image_url = node.get("url") or node.get("src")

        handle = str(p.get("handle") or "")
        url = f"https://{shop_domain}/products/{handle}".rstrip("/")
        path = "/" + url.split("/", 3)[-1] if "/" in url.split("://", 1)[-1] else ""
        gsc_visible = any(
            (url == row_url or path == "/" + row_url.split("/", 3)[-1])
            and int(row.get("impressions", 0) or 0) > 0
            for row_url, row in gsc_page_rows.items()
        )

        gsc_issues = [] if gsc_visible else _diagnose_visibility_issues(p)

        result.append({
            "id": str(p.get("id", "")),
            "title": p.get("title", ""),
            "handle": handle,
            "image_url": image_url,
            "gsc_visible": gsc_visible,
            "gsc_connected": gsc_connected,
            "gsc_issues": gsc_issues,
        })
    return result


class ManagedProductsUpdate(BaseModel):
    product_ids: list[str]


class QuotaCodeRedeem(BaseModel):
    code: str


@router.post("/shops/{shop}/quota-code/redeem")
async def redeem_quota_code_endpoint(
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
    body: QuotaCodeRedeem,
) -> dict:
    """Redeem a single-use quota reset code (any plan). See app/billing/quota_codes.py."""
    from app.billing.quota_codes import (  # noqa: PLC0415
        InvalidQuotaCode,
        QuotaCodeAlreadyUsed,
        redeem_quota_code,
    )

    try:
        result = redeem_quota_code(ctx.shop, body.code)
    except InvalidQuotaCode as exc:
        raise HTTPException(status_code=400, detail=f"invalid_code: {exc}") from exc
    except QuotaCodeAlreadyUsed as exc:
        raise HTTPException(status_code=409, detail="code_already_used") from exc
    return {"redeemed": True, **result}


@router.get("/shops/{shop}/managed-products")
async def get_managed_products(ctx: Annotated[ShopContext, Depends(get_shop_context)]) -> dict:
    """Return the merchant's managed-products selection + the pickable catalog.

    `selected_ids` is null when never configured (legacy shop that hasn't gone
    through selection yet) — the analysis pipeline then falls back to
    inheriting the last analysis's products (see `filter_managed_products`).
    """
    available = await asyncio.to_thread(_build_active_products, ctx)
    return {
        "selected_ids": get_managed_product_ids(ctx.shop),
        "cap": product_cap(ctx.shop),
        "plan": ctx.plan,
        "available_products": available,
    }


@router.put("/shops/{shop}/managed-products")
async def put_managed_products(
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
    body: ManagedProductsUpdate,
) -> dict:
    """Persist the merchant's managed-products selection (plan-capped)."""
    try:
        set_managed_product_ids(ctx.shop, body.product_ids)
    except ManagedProductsCapExceeded as exc:
        raise HTTPException(
            status_code=402,
            detail={
                "error": "quota_exceeded",
                "kind": "products",
                "plan": ctx.plan,
                "used": exc.requested,
                "quota": exc.cap,
                "upgrade": "pro" if ctx.plan == "free" else "agency",
            },
        ) from exc
    return {"saved": True, "selected_ids": get_managed_product_ids(ctx.shop)}
