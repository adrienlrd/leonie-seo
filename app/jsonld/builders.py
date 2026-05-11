"""Schema.org JSON-LD builders — mirrors the Liquid blocks in the Theme App Extension.

Used for preview API and tests. Accepts Shopify REST snapshot format.
"""

from __future__ import annotations

import re


def _strip_html(html: str) -> str:
    return re.sub(r"<[^>]+>", " ", html).strip()


def _shop_url(shop: dict) -> str:
    domain = shop.get("domain") or shop.get("myshopify_domain", "")
    return f"https://{domain}"


def build_product_jsonld(product: dict, shop: dict) -> dict:
    """Build Schema.org Product JSON-LD dict from Shopify snapshot product data.

    Args:
        product: Shopify REST product dict (id, title, handle, body_html, images, variants).
        shop: Shopify REST shop dict (name, domain, currency, country_code).

    Returns:
        JSON-serialisable dict conforming to Schema.org/Product.
    """
    base_url = _shop_url(shop)
    handle = product.get("handle", "")
    product_url = f"{base_url}/products/{handle}"

    variants = product.get("variants", [])
    first_variant = variants[0] if variants else {}
    price = str(first_variant.get("price", "0.00"))
    sku = first_variant.get("sku", "")

    in_stock = (
        any(
            (v.get("inventory_quantity") or 0) > 0 or v.get("inventory_management") is None
            for v in variants
        )
        if variants
        else False
    )
    availability = "https://schema.org/InStock" if in_stock else "https://schema.org/OutOfStock"

    images = [img["src"] for img in product.get("images", []) if img.get("src")]
    description = _strip_html(product.get("body_html", ""))[:500]

    data: dict = {
        "@context": "https://schema.org/",
        "@type": "Product",
        "name": product.get("title", ""),
        "url": product_url,
        "description": description,
        "brand": {
            "@type": "Brand",
            "name": shop.get("name", ""),
        },
        "offers": {
            "@type": "Offer",
            "priceCurrency": shop.get("currency", "EUR"),
            "price": price,
            "availability": availability,
            "url": product_url,
        },
        "breadcrumb": {
            "@type": "BreadcrumbList",
            "itemListElement": [
                {"@type": "ListItem", "position": 1, "name": "Accueil", "item": base_url},
                {
                    "@type": "ListItem",
                    "position": 2,
                    "name": product.get("title", ""),
                    "item": product_url,
                },
            ],
        },
    }

    if images:
        data["image"] = images
    if sku:
        data["sku"] = sku

    return data


def build_collection_jsonld(collection: dict, shop: dict) -> dict:
    """Build Schema.org CollectionPage JSON-LD dict.

    Args:
        collection: Shopify REST collection dict (title, handle, body_html, image).
        shop: Shopify REST shop dict (name, domain).

    Returns:
        JSON-serialisable dict conforming to Schema.org/CollectionPage.
    """
    base_url = _shop_url(shop)
    handle = collection.get("handle", "")
    collection_url = f"{base_url}/collections/{handle}"
    description = _strip_html(collection.get("body_html", ""))[:300]

    data: dict = {
        "@context": "https://schema.org/",
        "@type": "CollectionPage",
        "name": collection.get("title", ""),
        "url": collection_url,
        "breadcrumb": {
            "@type": "BreadcrumbList",
            "itemListElement": [
                {"@type": "ListItem", "position": 1, "name": "Accueil", "item": base_url},
                {
                    "@type": "ListItem",
                    "position": 2,
                    "name": collection.get("title", ""),
                    "item": collection_url,
                },
            ],
        },
    }

    if description:
        data["description"] = description

    image_src = collection.get("image", {})
    if isinstance(image_src, dict):
        image_src = image_src.get("src", "")
    if image_src:
        data["image"] = image_src

    return data


def build_organization_jsonld(shop: dict) -> dict:
    """Build Schema.org Organization JSON-LD dict for the homepage.

    Args:
        shop: Shopify REST shop dict (name, domain, email, phone, address, country_code).

    Returns:
        JSON-serialisable dict conforming to Schema.org/Organization.
    """
    base_url = _shop_url(shop)
    data: dict = {
        "@context": "https://schema.org",
        "@type": "Organization",
        "name": shop.get("name", ""),
        "url": base_url,
    }

    if shop.get("email"):
        data["email"] = shop["email"]
    if shop.get("phone"):
        data["telephone"] = shop["phone"]

    country = shop.get("country_code") or shop.get("address", {}).get("country_code", "")
    if country:
        address: dict = {"@type": "PostalAddress", "addressCountry": country}
        city = shop.get("city") or shop.get("address", {}).get("city", "")
        zip_code = shop.get("zip") or shop.get("address", {}).get("zip", "")
        if city:
            address["addressLocality"] = city
        if zip_code:
            address["postalCode"] = zip_code
        data["address"] = address

    social = [s for s in shop.get("social", []) if s]
    if social:
        data["sameAs"] = social

    return data
