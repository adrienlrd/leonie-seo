"""Build schema.org JSON-LD blocks deterministically from confirmed product data.

Why this lives in Python and not in the LLM prompt:
- structured data is high-stakes — a hallucinated `aggregateRating` or wrong
  `availability` can trigger a Google rich-result penalty;
- the inputs (Shopify snapshot + merchant-confirmed facts) are stable, typed,
  and easy to test; the LLM adds zero value here.

Outputs are plain dicts ready to be serialized as JSON-LD into the storefront
(`<script type="application/ld+json">`).
"""

from __future__ import annotations

from typing import Any

_SCHEMA_CTX = "https://schema.org"


def build_product_schema(
    *,
    product: dict[str, Any],
    confirmed_facts: list[dict[str, Any]],
    shop: str,
    meta_description: str,
) -> dict[str, Any]:
    """Build a `Product` JSON-LD object from snapshot + confirmed facts.

    Optional fields are only set when the corresponding fact is `confirmed`,
    so no hallucinated material, origin, or certification ever ships.
    """
    handle = str(product.get("handle") or "")
    title = str(product.get("title") or "")
    shop_origin = _shop_origin(shop)

    schema: dict[str, Any] = {
        "@context": _SCHEMA_CTX,
        "@type": "Product",
        "name": title,
        "url": f"{shop_origin}/products/{handle}",
    }
    if meta_description:
        schema["description"] = meta_description

    images = _extract_image_urls(product.get("images") or [])
    if images:
        schema["image"] = images

    vendor = str(product.get("vendor") or "").strip()
    if vendor:
        schema["brand"] = {"@type": "Brand", "name": vendor}

    offers = _build_offers(product)
    if offers:
        schema["offers"] = offers

    facts_by_key = {
        str(f.get("key") or ""): f
        for f in confirmed_facts
        if isinstance(f, dict) and str(f.get("confidence") or "") == "confirmed"
    }
    materials = _string_value(facts_by_key.get("materials"))
    if materials:
        schema["material"] = materials
    origins = _string_value(facts_by_key.get("origins"))
    if origins:
        schema["countryOfOrigin"] = origins

    return schema


def build_faq_schema(faq: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Build an `FAQPage` JSON-LD from a list of `{q, a}` entries.

    Returns `None` when no valid entry exists, so callers can omit the block
    rather than emit an empty schema.
    """
    entities: list[dict[str, Any]] = []
    for entry in faq or []:
        question = str(entry.get("q") or "").strip()
        answer = str(entry.get("a") or "").strip()
        if not question or not answer:
            continue
        entities.append(
            {
                "@type": "Question",
                "name": question,
                "acceptedAnswer": {"@type": "Answer", "text": answer},
            }
        )
    if not entities:
        return None
    return {
        "@context": _SCHEMA_CTX,
        "@type": "FAQPage",
        "mainEntity": entities,
    }


def build_breadcrumb_schema(
    *,
    product: dict[str, Any],
    shop: str,
    collection_handle: str | None,
    collection_title: str | None,
    home_label: str = "Accueil",
) -> dict[str, Any]:
    """Build a `BreadcrumbList` JSON-LD: Home → Collection (optional) → Product."""
    shop_origin = _shop_origin(shop)
    handle = str(product.get("handle") or "")
    title = str(product.get("title") or "")
    items: list[dict[str, Any]] = [
        {
            "@type": "ListItem",
            "position": 1,
            "name": home_label,
            "item": shop_origin,
        }
    ]
    position = 2
    if collection_handle and collection_title:
        items.append(
            {
                "@type": "ListItem",
                "position": position,
                "name": collection_title,
                "item": f"{shop_origin}/collections/{collection_handle}",
            }
        )
        position += 1
    items.append(
        {
            "@type": "ListItem",
            "position": position,
            "name": title,
            "item": f"{shop_origin}/products/{handle}",
        }
    )
    return {
        "@context": _SCHEMA_CTX,
        "@type": "BreadcrumbList",
        "itemListElement": items,
    }


def _shop_origin(shop: str) -> str:
    domain = (shop or "").strip()
    if not domain:
        return ""
    if domain.startswith("http://") or domain.startswith("https://"):
        return domain.rstrip("/")
    return f"https://{domain}"


def _extract_image_urls(images: list[Any]) -> list[str]:
    out: list[str] = []
    for img in images:
        if isinstance(img, str):
            out.append(img)
        elif isinstance(img, dict):
            src = img.get("src") or img.get("url")
            if src:
                out.append(str(src))
    return out


def _build_offers(product: dict[str, Any]) -> dict[str, Any] | None:
    variants = product.get("variants") or []
    if not variants:
        return None
    first = variants[0] if isinstance(variants[0], dict) else {}
    price = first.get("price")
    if price is None:
        return None
    qty_raw = first.get("inventory_quantity")
    if qty_raw is None:
        qty_raw = first.get("inventoryQuantity")
    availability = "https://schema.org/InStock"
    try:
        if qty_raw is not None and int(qty_raw) <= 0:
            availability = "https://schema.org/OutOfStock"
    except (TypeError, ValueError):
        pass
    return {
        "@type": "Offer",
        "price": str(price),
        "priceCurrency": "EUR",
        "availability": availability,
    }


def _string_value(fact: dict[str, Any] | None) -> str:
    if not fact:
        return ""
    value = fact.get("value")
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list) and value:
        return ", ".join(str(v).strip() for v in value if str(v).strip())
    return ""
