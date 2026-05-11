"""JSON-LD preview API — generate structured data for Shopify resources."""

from __future__ import annotations

import json
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import ShopContext, get_shop_context
from app.jsonld.builders import (
    build_collection_jsonld,
    build_organization_jsonld,
    build_product_jsonld,
)

router = APIRouter(prefix="/api", tags=["jsonld"])


def _load_snapshot(ctx: ShopContext) -> dict:
    path = ctx.snapshot_path
    if not path.exists():
        raise HTTPException(
            status_code=404,
            detail="No crawl data found. Run 'leonie-seo audit crawl' first.",
        )
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError) as exc:
        raise HTTPException(status_code=500, detail=f"Snapshot unreadable: {exc}") from exc


@router.get("/shops/{shop}/jsonld/organization")
async def get_organization_jsonld(
    shop: str,
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
) -> dict:
    """Return Schema.org Organization JSON-LD for a shop.

    Uses the cached snapshot shop metadata.

    Args:
        shop: Shopify shop domain.
    """
    snapshot = _load_snapshot(ctx)
    shop_data = snapshot.get("shop", {})
    if not shop_data:
        raise HTTPException(status_code=404, detail="Shop metadata not found in snapshot.")
    return build_organization_jsonld(shop_data)


@router.get("/shops/{shop}/jsonld/product/{product_id}")
async def get_product_jsonld(
    shop: str,
    product_id: int,
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
) -> dict:
    """Return Schema.org Product JSON-LD for a single product.

    Args:
        shop: Shopify shop domain.
        product_id: Numeric Shopify product ID.
    """
    snapshot = _load_snapshot(ctx)
    shop_data = snapshot.get("shop", {})
    products = snapshot.get("products", [])
    product = next((p for p in products if p.get("id") == product_id), None)
    if product is None:
        raise HTTPException(status_code=404, detail=f"Product {product_id} not found in snapshot.")
    return build_product_jsonld(product, shop_data)


@router.get("/shops/{shop}/jsonld/collection/{collection_id}")
async def get_collection_jsonld(
    shop: str,
    collection_id: int,
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
) -> dict:
    """Return Schema.org CollectionPage JSON-LD for a single collection.

    Args:
        shop: Shopify shop domain.
        collection_id: Numeric Shopify collection ID.
    """
    snapshot = _load_snapshot(ctx)
    shop_data = snapshot.get("shop", {})
    collections = snapshot.get("collections", [])
    collection = next((c for c in collections if c.get("id") == collection_id), None)
    if collection is None:
        raise HTTPException(
            status_code=404,
            detail=f"Collection {collection_id} not found in snapshot.",
        )
    return build_collection_jsonld(collection, shop_data)
