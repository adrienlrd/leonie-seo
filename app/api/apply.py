"""Apply endpoints — push SEO changes to Shopify (dry_run=True by default)."""

import asyncio
from typing import Annotated

import requests
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.api.deps import ShopContext, require_feature
from scripts.apply.update_meta import ShopifyUserError, update_product_seo

router = APIRouter(prefix="/api", tags=["apply"])


class MetaUpdate(BaseModel):
    product_id: str  # Shopify GID — e.g. gid://shopify/Product/123
    title: str | None = None
    description: str | None = None


class MetaUpdateResult(BaseModel):
    product_id: str
    status: str  # "preview" | "applied" | "error"
    detail: str | None = None


def _classify_error(exc: Exception, product_id: str) -> MetaUpdateResult:
    """Map a Shopify call failure to a structured user-facing error."""
    if isinstance(exc, ShopifyUserError):
        return MetaUpdateResult(product_id=product_id, status="error", detail=str(exc))
    if isinstance(exc, requests.HTTPError):
        return MetaUpdateResult(
            product_id=product_id,
            status="error",
            detail=f"Shopify HTTP {exc.response.status_code if exc.response else '?'}: {exc}",
        )
    if isinstance(exc, requests.Timeout | requests.ConnectionError):
        return MetaUpdateResult(
            product_id=product_id,
            status="error",
            detail=f"Network error reaching Shopify: {exc}",
        )
    # Unexpected — re-raise so it surfaces in logs rather than silently swallowed
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
            # update_product_seo is sync (uses requests). Run in a thread to
            # avoid blocking the event loop during Shopify's response window.
            await asyncio.to_thread(
                update_product_seo,
                product_id=upd.product_id,
                seo_title=upd.title,
                seo_description=upd.description,
                endpoint=ctx.graphql_endpoint,
                headers=ctx.graphql_headers,
            )
            results.append(
                MetaUpdateResult(product_id=upd.product_id, status="applied").model_dump()
            )
        except (
            ShopifyUserError,
            requests.HTTPError,
            requests.Timeout,
            requests.ConnectionError,
        ) as exc:
            results.append(_classify_error(exc, upd.product_id).model_dump())

    return results
