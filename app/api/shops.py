"""Shop management endpoints."""

from fastapi import APIRouter, HTTPException

from app.api.deps import ShopContext, get_shop_context
from app.oauth.token_store import list_tokens

router = APIRouter(prefix="/api", tags=["shops"])


@router.get("/shops")
async def list_shops() -> list[dict]:
    """List all shops that have completed OAuth installation."""
    return list_tokens()


@router.get("/shops/{shop}/status")
async def shop_status(shop: str) -> dict:
    """Return shop auth status and whether crawl data is available."""
    ctx: ShopContext = get_shop_context(shop)
    snapshot_exists = ctx.snapshot_path.exists()
    snapshot_date: str | None = None

    if snapshot_exists:
        import json

        try:
            data = json.loads(ctx.snapshot_path.read_text())
            snapshot_date = data.get("snapshot_date")
            product_count = len(data.get("products", []))
            collection_count = len(data.get("collections", []))
        except (json.JSONDecodeError, OSError):
            raise HTTPException(status_code=500, detail="Snapshot file is corrupted")
    else:
        product_count = 0
        collection_count = 0

    return {
        "shop": shop,
        "installed": True,
        "snapshot_available": snapshot_exists,
        "snapshot_date": snapshot_date,
        "product_count": product_count,
        "collection_count": collection_count,
    }
