"""Shop management endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import ShopContext, get_shop_context, require_internal_secret
from app.api.plans import plan_summary
from app.api.snapshot_store import load_snapshot_from_file_or_db
from app.oauth.token_store import list_tokens
from app.safety import is_pilot_safe_mode

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
