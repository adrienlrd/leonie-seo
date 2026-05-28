"""Shop management endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import ShopContext, get_shop_context, require_internal_secret
from app.api.plans import plan_summary
from app.api.snapshot_store import load_snapshot_from_file_or_db
from app.impact.report import _find_gsc_file, _parse_gsc_csv
from app.oauth.token_store import list_tokens
from app.safety import is_pilot_safe_mode
from app.snapshot.scope import filter_products_by_scope

router = APIRouter(prefix="/api", tags=["shops"])


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
        data = load_snapshot_from_file_or_db(ctx.shop, ctx.snapshot_path)
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    if data is None:
        return []

    products = filter_products_by_scope(data.get("products", []), "active")

    # Build GSC visibility map: product URL → has impressions in GSC
    shop_domain = str((data.get("shop") or {}).get("domain") or ctx.shop)
    gsc_page_rows: dict[str, dict] = {}
    gsc_file = _find_gsc_file(ctx.shop)
    if gsc_file:
        try:
            gsc_page_rows = _parse_gsc_csv(gsc_file.read_text(encoding="utf-8"))
        except Exception:
            pass

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

        result.append({
            "id": str(p.get("id", "")),
            "title": p.get("title", ""),
            "handle": handle,
            "image_url": image_url,
            "gsc_visible": gsc_visible,
        })
    return result
