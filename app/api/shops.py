"""Shop management endpoints."""

import json
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import ShopContext, get_shop_context, require_internal_secret
from app.api.plans import plan_summary
from app.oauth.token_store import list_tokens

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
    snapshot_exists = ctx.snapshot_path.exists()
    snapshot_date: str | None = None
    product_count = 0
    collection_count = 0

    if snapshot_exists:
        try:
            data = json.loads(ctx.snapshot_path.read_text())
        except (json.JSONDecodeError, OSError) as exc:
            raise HTTPException(status_code=500, detail="Snapshot file is corrupted") from exc
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
        **plan_summary(ctx.plan),
    }
