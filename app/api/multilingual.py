"""Multilingual meta generation API."""

from __future__ import annotations

import json
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator

from app.api.deps import ShopContext, get_shop_context
from app.llm.multilingual import SUPPORTED_LOCALES, generate_meta_all_locales

router = APIRouter(prefix="/api", tags=["multilingual"])


class MultilingualMetaRequest(BaseModel):
    product_id: str
    locales: list[str]

    @field_validator("locales")
    @classmethod
    def validate_locales(cls, v: list[str]) -> list[str]:
        invalid = [l for l in v if l not in SUPPORTED_LOCALES]  # noqa: E741
        if invalid:
            raise ValueError(
                f"Unsupported locales: {invalid}. Supported: {list(SUPPORTED_LOCALES)}"
            )
        if not v:
            raise ValueError("At least one locale is required.")
        return list(dict.fromkeys(v))  # deduplicate preserving order


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


@router.post("/shops/{shop}/multilingual/meta")
async def generate_multilingual_meta(
    shop: str,
    body: MultilingualMetaRequest,
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
) -> dict:
    """Generate SEO meta title and description for a product in multiple locales.

    Uses the LLM to write native content (not translations) optimised for each
    target market's search intent and vocabulary.

    Args:
        shop: Shopify shop domain.
        body: product_id and list of target locales (fr, en, de, nl).
    """
    import asyncio  # noqa: PLC0415

    snapshot = _load_snapshot(ctx)
    products = snapshot.get("products", [])
    product = next((p for p in products if str(p.get("id", "")) == body.product_id), None)
    if product is None:
        raise HTTPException(
            status_code=404,
            detail=f"Product {body.product_id} not found in snapshot.",
        )

    from app.llm import get_router  # noqa: PLC0415
    from app.tenant_config import find_tenant_by_shop_domain  # noqa: PLC0415

    tenant = find_tenant_by_shop_domain(shop)
    brand = tenant.brand if tenant else None

    llm_router = get_router(shop=shop)
    results = await asyncio.to_thread(
        generate_meta_all_locales,
        product,
        body.locales,
        llm_router,
        brand=brand,
    )

    return {
        "product_id": body.product_id,
        "product_title": product.get("title", ""),
        "results": [
            {
                "locale": r.locale,
                "locale_name": r.locale_name,
                "title": r.title,
                "description": r.description,
                "provider": r.provider,
                "success": r.success,
                "error": r.error,
            }
            for r in results
        ],
    }


@router.get("/shops/{shop}/multilingual/locales")
async def list_supported_locales(
    shop: str,
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
) -> dict:
    """Return the list of supported locales for multilingual generation."""
    return {"locales": [{"code": code, "name": name} for code, name in SUPPORTED_LOCALES.items()]}
