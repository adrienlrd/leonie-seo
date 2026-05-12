"""Apply endpoints — push SEO changes to Shopify (dry_run=True by default)."""

import asyncio
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.api.deps import ShopContext, require_feature
from app.apply.shopify_writer import ApplyResult, ShopifyWriter

router = APIRouter(prefix="/api", tags=["apply"])


class MetaUpdate(BaseModel):
    product_id: str  # Shopify GID — e.g. gid://shopify/Product/123
    title: str | None = None
    description: str | None = None


class MetaUpdateResult(BaseModel):
    product_id: str
    status: str  # "preview" | "applied" | "error"
    detail: str | None = None


def _from_apply_result(result: ApplyResult) -> MetaUpdateResult:
    """Map a writer result to a structured API response."""
    if result.applied:
        return MetaUpdateResult(product_id=result.resource_id, status="applied")
    return MetaUpdateResult(
        product_id=result.resource_id,
        status="error",
        detail=result.error or "Shopify update was not applied",
    )


def _classify_error(exc: OSError, product_id: str) -> MetaUpdateResult:
    """Map a transport failure to a structured user-facing error."""
    if isinstance(exc, OSError):
        return MetaUpdateResult(
            product_id=product_id,
            status="error",
            detail=f"Network error reaching Shopify: {exc}",
        )
    raise exc


@router.post("/shops/{shop}/apply/meta")
async def apply_meta(
    ctx: Annotated[ShopContext, Depends(require_feature("apply"))],
    updates: list[MetaUpdate],
    dry_run: bool = True,
) -> list[dict]:
    """Update meta titles and descriptions on Shopify products.

    Set dry_run=false to apply changes. Default is dry_run=true (preview only).
    """
    if not updates:
        raise HTTPException(status_code=422, detail="No updates provided")

    results: list[dict] = []

    for upd in updates:
        if dry_run:
            results.append(
                MetaUpdateResult(
                    product_id=upd.product_id,
                    status="preview",
                    detail=f"Would set title={upd.title!r}, description={upd.description!r}",
                ).model_dump()
            )
            continue

        try:
            # ShopifyWriter is sync (uses requests). Run in a thread to
            # avoid blocking the event loop during Shopify's response window.
            result = await asyncio.to_thread(
                lambda: ShopifyWriter(ctx.shop, ctx.access_token).apply_product_seo(
                    upd.product_id,
                    upd.title,
                    upd.description,
                )
            )
            results.append(_from_apply_result(result).model_dump())
        except OSError as exc:
            results.append(_classify_error(exc, upd.product_id).model_dump())

    return results
