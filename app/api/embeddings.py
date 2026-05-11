"""Embeddings API — index products and semantic similarity search."""

from __future__ import annotations

import json
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import ShopContext, get_shop_context
from app.embeddings.store import search_similar_products, upsert_product_embedding

router = APIRouter(prefix="/api", tags=["embeddings"])


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


@router.post("/shops/{shop}/embeddings/index-products")
async def index_products(
    shop: str,
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
) -> dict:
    """Encode all products from the crawl snapshot and store their embeddings.

    Uses intfloat/multilingual-e5-base (768 dims). The model is downloaded
    on first call (~400 MB, cached in ~/.cache/huggingface/).

    Args:
        shop: Shopify shop domain.

    Returns:
        Dict with indexed product count and any skipped entries.
    """
    import asyncio  # noqa: PLC0415

    from app.embeddings.encoder import encode_passage  # noqa: PLC0415

    snapshot = _load_snapshot(ctx)
    products = snapshot.get("products", [])
    if not products:
        return {"indexed": 0, "skipped": 0, "message": "No products in snapshot."}

    indexed = 0
    skipped = 0

    loop = asyncio.get_event_loop()

    for product in products:
        product_id = str(product.get("id", ""))
        title = product.get("title", "")
        if not product_id or not title:
            skipped += 1
            continue

        text = title
        if product.get("body_html"):
            import re  # noqa: PLC0415

            description = re.sub(r"<[^>]+>", " ", product["body_html"]).strip()
            text = f"{title}. {description}"[:512]

        embedding = await loop.run_in_executor(None, lambda t=text: encode_passage(t))
        upsert_product_embedding(shop, product_id, title, embedding)
        indexed += 1

    return {"indexed": indexed, "skipped": skipped}


@router.get("/shops/{shop}/embeddings/search")
async def search_products(
    shop: str,
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
    query: Annotated[str, Query(min_length=1, max_length=200)],
    top_k: Annotated[int, Query(ge=1, le=20)] = 5,
) -> dict:
    """Find the most semantically similar products to a free-text query.

    Args:
        shop: Shopify shop domain.
        query: Free-text search query (e.g. a GSC search query or keyword gap).
        top_k: Number of results to return (1–20, default 5).

    Returns:
        Dict with query, results list (product_id, title, similarity score 0–1).
    """
    import asyncio  # noqa: PLC0415

    from app.embeddings.encoder import encode_query  # noqa: PLC0415

    loop = asyncio.get_event_loop()
    query_embedding = await loop.run_in_executor(None, lambda: encode_query(query))
    results = search_similar_products(shop, query_embedding, top_k=top_k)
    return {"query": query, "top_k": top_k, "results": results}
