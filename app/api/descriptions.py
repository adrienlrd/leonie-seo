"""Product description rewrite endpoint — generate, review, and apply."""

from __future__ import annotations

import asyncio
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.api.deps import ShopContext, get_shop_context
from app.api.snapshot_store import load_snapshot_from_file_or_db
from app.apply.shopify_writer import ShopifyWriter
from app.safety import require_shopify_write_allowed
from scripts.apply.rewrite_descriptions import (
    build_description,
    classify_product,
    strip_html,
)

router = APIRouter(tags=["descriptions"])

_MIN_WORD_COUNT = 50
_MAX_WORD_COUNT = 400


def _plain_to_html(text: str) -> str:
    """Convert plain text (double newlines) to HTML paragraphs."""
    return text.replace("\n\n", "<br><br>")


def _build_rows(products: list[dict]) -> list[dict]:
    rows = []
    for p in products:
        title = p.get("title", "")
        if not title:
            continue
        existing_html = p.get("description") or p.get("descriptionHtml") or ""
        existing_plain = strip_html(existing_html)
        category = classify_product(title, existing_plain)
        suggested = build_description(title, category)
        word_count = len(suggested.split())
        rows.append(
            {
                "product_id": p["id"],
                "handle": p.get("handle", ""),
                "title": title,
                "category": category,
                "old_description": existing_plain or None,
                "suggested_description": suggested,
                "word_count": word_count,
                "quality_ok": _MIN_WORD_COUNT <= word_count <= _MAX_WORD_COUNT,
            }
        )
    return rows


# ---------------------------------------------------------------------------
# GET — suggestions
# ---------------------------------------------------------------------------


@router.get("/api/shops/{shop}/audit/descriptions")
async def get_description_suggestions(
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
) -> dict:
    """Return product description suggestions for review.

    Classifies each product, generates a template-based description,
    and returns the old vs new content for human review.
    Read-only — no Shopify writes.
    """
    snapshot = load_snapshot_from_file_or_db(ctx.shop, ctx.snapshot_path)
    if snapshot is None:
        raise HTTPException(
            status_code=404,
            detail="No Shopify snapshot found. Run an SEO audit first.",
        )

    products = snapshot.get("products", [])
    rows = _build_rows(products)

    return {
        "shop": ctx.shop,
        "available": True,
        "total": len(rows),
        "quality_issues": sum(1 for r in rows if not r["quality_ok"]),
        "rows": rows,
    }


# ---------------------------------------------------------------------------
# POST — apply (dry_run=True by default)
# ---------------------------------------------------------------------------


class DescriptionItem(BaseModel):
    product_id: str
    description: str  # plain text; will be converted to HTML on apply


class DescriptionApplyRequest(BaseModel):
    items: list[DescriptionItem]
    dry_run: bool = True
    confirm_live_write: bool = False


@router.post("/api/shops/{shop}/audit/descriptions/apply")
async def apply_descriptions(
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
    body: DescriptionApplyRequest,
) -> dict:
    """Apply approved description rewrites to Shopify products.

    Dry-run by default. Set dry_run=false + confirm_live_write=true to write.
    Plain text paragraphs (double newlines) are converted to HTML before push.
    """
    if not body.items:
        raise HTTPException(status_code=422, detail="No items provided")

    require_shopify_write_allowed(
        action="apply_descriptions",
        dry_run=body.dry_run,
        confirmed=body.confirm_live_write,
    )

    for item in body.items:
        word_count = len(item.description.split())
        if word_count < _MIN_WORD_COUNT:
            raise HTTPException(
                status_code=422,
                detail=f"Description too short ({word_count} words) for {item.product_id}. Min {_MIN_WORD_COUNT}.",
            )
        if word_count > _MAX_WORD_COUNT:
            raise HTTPException(
                status_code=422,
                detail=f"Description too long ({word_count} words) for {item.product_id}. Max {_MAX_WORD_COUNT}.",
            )

    results = []

    if body.dry_run:
        for item in body.items:
            words = len(item.description.split())
            results.append(
                {
                    "product_id": item.product_id,
                    "status": "preview",
                    "detail": f"Would update description ({words} mots)",
                }
            )
        return {"dry_run": True, "total": len(results), "results": results}

    writer = ShopifyWriter(ctx.shop, ctx.access_token)

    for item in body.items:
        description_html = _plain_to_html(item.description)
        result = await asyncio.to_thread(
            lambda i=item, h=description_html: writer.apply_product_description(
                i.product_id, h
            )
        )
        results.append(
            {
                "product_id": item.product_id,
                "status": "applied" if result.applied else "error",
                "detail": result.error,
            }
        )

    applied = sum(1 for r in results if r["status"] == "applied")
    errors = sum(1 for r in results if r["status"] == "error")

    return {
        "dry_run": False,
        "total": len(results),
        "applied": applied,
        "errors": errors,
        "results": results,
    }
