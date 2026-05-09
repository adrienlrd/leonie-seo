"""Apply endpoints — push SEO changes to Shopify (dry_run=True by default)."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.api.deps import ShopContext, get_shop_context
from scripts.apply.update_meta import update_product_seo

router = APIRouter(prefix="/api", tags=["apply"])


class MetaUpdate(BaseModel):
    product_id: str  # Shopify GID — e.g. gid://shopify/Product/123
    title: str | None = None
    description: str | None = None


class MetaUpdateResult(BaseModel):
    product_id: str
    status: str  # "preview" | "applied" | "error"
    detail: str | None = None


@router.post("/shops/{shop}/apply/meta")
async def apply_meta(
    shop: str,
    updates: list[MetaUpdate],
    dry_run: bool = True,
) -> list[dict]:
    """Update meta titles and descriptions on Shopify products.

    Set dry_run=false to apply changes. Default is dry_run=true (preview only).
    A human confirmation step is required before any write operation.
    """
    if not updates:
        raise HTTPException(status_code=422, detail="No updates provided")

    ctx: ShopContext = get_shop_context(shop)
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
            update_product_seo(
                product_id=upd.product_id,
                seo_title=upd.title,
                seo_description=upd.description,
                endpoint=ctx.graphql_endpoint,
                headers=ctx.graphql_headers,
            )
            results.append(
                MetaUpdateResult(
                    product_id=upd.product_id,
                    status="applied",
                ).model_dump()
            )
        except Exception as exc:
            results.append(
                MetaUpdateResult(
                    product_id=upd.product_id,
                    status="error",
                    detail=str(exc),
                ).model_dump()
            )

    return results
