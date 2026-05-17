"""Alt text generation and apply endpoint — read/dry-run by default."""

from __future__ import annotations

import asyncio
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.api.deps import ShopContext, get_shop_context
from app.api.rollback import log_seo_change
from app.api.snapshot_store import load_snapshot_from_file_or_db
from app.apply.shopify_writer import ShopifyWriter
from app.safety import require_shopify_write_allowed

router = APIRouter(tags=["alt_text"])

_ALT_MAX_LEN = 125
_ACCESSIBILITY_PREFIXES = ("image", "photo", "picture", "img", "screenshot")


def _suggest_alt(product_title: str, image_index: int = 0) -> str:
    """Generate alt text: product title with optional view suffix. Max 125 chars."""
    suffix = f" — vue {image_index + 1}" if image_index > 0 else ""
    max_title = _ALT_MAX_LEN - len(suffix)
    return f"{product_title[:max_title].rstrip()}{suffix}"


def _quality_ok(alt: str) -> bool:
    clean = alt.strip().lower()
    if not clean or len(alt) > _ALT_MAX_LEN:
        return False
    return not any(clean.startswith(p) for p in _ACCESSIBILITY_PREFIXES)


def _build_suggestions(products: list[dict]) -> list[dict]:
    rows: list[dict] = []
    for p in products:
        images = (p.get("images") or {}).get("edges", [])
        img_idx = 0
        for edge in images:
            img = edge.get("node", {})
            old_alt = img.get("altText") or ""
            if old_alt.strip():
                continue  # already has alt text
            suggested = _suggest_alt(p["title"], img_idx)
            rows.append(
                {
                    "product_id": p["id"],
                    "product_name": p["title"],
                    "image_id": img["id"],
                    "image_url": img.get("url", ""),
                    "old_alt": old_alt or None,
                    "suggested_alt": suggested,
                    "char_count": len(suggested),
                    "quality_ok": _quality_ok(suggested),
                }
            )
            img_idx += 1
    return rows


# ---------------------------------------------------------------------------
# GET — suggestions
# ---------------------------------------------------------------------------


@router.get("/api/shops/{shop}/audit/alt-text")
async def get_alt_text_suggestions(
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
) -> dict:
    """Return product images missing alt text, with generated suggestions.

    Read-only — no Shopify writes. Requires a Shopify snapshot.
    """
    snapshot = load_snapshot_from_file_or_db(ctx.shop, ctx.snapshot_path)
    if snapshot is None:
        raise HTTPException(
            status_code=404,
            detail="No Shopify snapshot found. Run an SEO audit first.",
        )

    products = snapshot.get("products", [])
    rows = _build_suggestions(products)

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


class AltTextItem(BaseModel):
    product_id: str
    image_id: str
    alt_text: str


class AltTextApplyRequest(BaseModel):
    items: list[AltTextItem]
    dry_run: bool = True
    confirm_live_write: bool = False


@router.post("/api/shops/{shop}/audit/alt-text/apply")
async def apply_alt_text(
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
    body: AltTextApplyRequest,
) -> dict:
    """Apply approved alt text suggestions to Shopify product images.

    Dry-run by default. Set dry_run=false and confirm_live_write=true to write.
    """
    if not body.items:
        raise HTTPException(status_code=422, detail="No items provided")

    require_shopify_write_allowed(
        action="apply_alt_text",
        dry_run=body.dry_run,
        confirmed=body.confirm_live_write,
    )

    # Validate each alt text before touching Shopify
    for item in body.items:
        alt = item.alt_text.strip()
        if not alt:
            raise HTTPException(
                status_code=422,
                detail=f"Empty alt text for image {item.image_id}",
            )
        if len(alt) > _ALT_MAX_LEN:
            raise HTTPException(
                status_code=422,
                detail=f"Alt text too long ({len(alt)} chars) for image {item.image_id}",
            )

    results = []

    if body.dry_run:
        for item in body.items:
            results.append(
                {
                    "image_id": item.image_id,
                    "product_id": item.product_id,
                    "status": "preview",
                    "detail": f"Would set alt text: {item.alt_text!r}",
                }
            )
        return {"dry_run": True, "total": len(results), "results": results}

    snapshot = load_snapshot_from_file_or_db(ctx.shop, ctx.snapshot_path)
    old_alts: dict[str, str | None] = {}
    if snapshot:
        for p in snapshot.get("products", []):
            for edge in (p.get("images") or {}).get("edges", []):
                node = edge.get("node", {})
                old_alts[node.get("id", "")] = node.get("altText")

    writer = ShopifyWriter(ctx.shop, ctx.access_token)

    for item in body.items:
        result = await asyncio.to_thread(
            lambda i=item: writer.apply_image_alt(i.product_id, i.image_id, i.alt_text)
        )
        if result.applied:
            log_seo_change(
                ctx.shop,
                resource_type="image",
                resource_id=item.image_id,
                field="image.alt_text",
                old_value=old_alts.get(item.image_id),
                new_value=item.alt_text,
            )
        results.append(
            {
                "image_id": item.image_id,
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
