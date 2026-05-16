"""JSON-LD preview API — generate structured data for Shopify resources."""

from __future__ import annotations

import json
import re
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import ShopContext, get_shop_context
from app.api.snapshot_store import load_snapshot_from_file_or_db
from app.jsonld.builders import (
    build_collection_jsonld,
    build_organization_jsonld,
    build_product_jsonld,
)

router = APIRouter(prefix="/api", tags=["jsonld"])

# ---------------------------------------------------------------------------
# Helpers for GraphQL-format snapshot (used by /status endpoint)
# ---------------------------------------------------------------------------

_REQUIRED_FIELDS: dict[str, list[str]] = {
    "Product": ["@type", "name", "url", "offers"],
    "CollectionPage": ["@type", "name", "url"],
    "Organization": ["@type", "name", "url"],
}


def _strip_html(html: str) -> str:
    return re.sub(r"<[^>]+>", " ", html or "").strip()


def _validate_jsonld(data: dict) -> tuple[bool, list[str]]:
    """Check required Schema.org fields. Returns (valid, missing_fields)."""
    schema_type = data.get("@type", "")
    required = _REQUIRED_FIELDS.get(schema_type, ["@type", "name", "url"])
    missing = [f for f in required if not data.get(f)]
    return len(missing) == 0, missing


def _product_jsonld_from_gql(product: dict[str, Any], base_url: str) -> dict:
    handle = product.get("handle", "")
    title = product.get("title", "")
    url = f"{base_url}/products/{handle}"
    description = _strip_html(
        product.get("description") or product.get("descriptionHtml") or ""
    )[:500]
    images = [
        e["node"]["url"]
        for e in (product.get("images") or {}).get("edges", [])
        if e.get("node", {}).get("url")
    ]
    jsonld: dict[str, Any] = {
        "@context": "https://schema.org/",
        "@type": "Product",
        "name": title,
        "url": url,
        "offers": {
            "@type": "Offer",
            "priceCurrency": "EUR",
            "availability": "https://schema.org/InStock",
        },
    }
    if description:
        jsonld["description"] = description
    if images:
        jsonld["image"] = images
    return jsonld


def _collection_jsonld_from_gql(collection: dict[str, Any], base_url: str) -> dict:
    handle = collection.get("handle", "")
    title = collection.get("title", "")
    url = f"{base_url}/collections/{handle}"
    description = _strip_html(
        collection.get("description") or collection.get("descriptionHtml") or ""
    )[:300]
    jsonld: dict[str, Any] = {
        "@context": "https://schema.org/",
        "@type": "CollectionPage",
        "name": title,
        "url": url,
    }
    if description:
        jsonld["description"] = description
    return jsonld


def _organization_jsonld_from_shop(shop: str) -> dict:
    base_url = f"https://{shop}"
    return {
        "@context": "https://schema.org",
        "@type": "Organization",
        "name": shop.replace(".myshopify.com", "").replace("-", " ").title(),
        "url": base_url,
    }


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


@router.get("/shops/{shop}/jsonld/status")
async def get_jsonld_status(
    shop: str,
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
) -> dict:
    """Return JSON-LD preview and validation status for all resources.

    Works with the GraphQL-format snapshot produced by the SEO audit job.
    Returns per-resource status: valid/invalid, missing fields, JSON-LD preview.
    """
    snapshot = load_snapshot_from_file_or_db(ctx.shop, ctx.snapshot_path)

    base_url = f"https://{ctx.shop}"
    resources: list[dict[str, Any]] = []

    # Organization (always generated from shop domain)
    org_jsonld = _organization_jsonld_from_shop(ctx.shop)
    org_valid, org_missing = _validate_jsonld(org_jsonld)
    resources.append(
        {
            "resource_type": "organization",
            "resource_id": ctx.shop,
            "title": org_jsonld["name"],
            "valid": org_valid,
            "missing_fields": org_missing,
            "jsonld": org_jsonld,
        }
    )

    if snapshot:
        for p in snapshot.get("products", []):
            if not p.get("handle") or not p.get("title"):
                continue
            pjsonld = _product_jsonld_from_gql(p, base_url)
            valid, missing = _validate_jsonld(pjsonld)
            resources.append(
                {
                    "resource_type": "product",
                    "resource_id": p.get("id", ""),
                    "handle": p.get("handle", ""),
                    "title": p.get("title", ""),
                    "valid": valid,
                    "missing_fields": missing,
                    "jsonld": pjsonld,
                }
            )

        for c in snapshot.get("collections", []):
            if not c.get("handle") or not c.get("title"):
                continue
            cjsonld = _collection_jsonld_from_gql(c, base_url)
            valid, missing = _validate_jsonld(cjsonld)
            resources.append(
                {
                    "resource_type": "collection",
                    "resource_id": c.get("id", ""),
                    "handle": c.get("handle", ""),
                    "title": c.get("title", ""),
                    "valid": valid,
                    "missing_fields": missing,
                    "jsonld": cjsonld,
                }
            )

    total = len(resources)
    valid_count = sum(1 for r in resources if r["valid"])

    return {
        "shop": ctx.shop,
        "available": snapshot is not None,
        "total": total,
        "valid": valid_count,
        "invalid": total - valid_count,
        "extension_note": (
            "Activez le Theme App Extension 'leonie-seo-jsonld' dans l'éditeur de thème Shopify "
            "pour injecter ces balises sur votre vitrine."
        ),
        "resources": resources,
    }
