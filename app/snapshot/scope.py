"""Product scope filters for Shopify catalog snapshots."""

from __future__ import annotations

from typing import Any, Literal

ProductScope = Literal["active", "draft", "unlisted", "archived", "all"]

_VALID_SCOPES: set[str] = {"active", "draft", "unlisted", "archived", "all"}


def normalize_product_scope(scope: str | None) -> ProductScope:
    """Return a supported product scope name.

    Args:
        scope: User-provided scope value.

    Raises:
        ValueError: If the scope is not one of the supported V1 scopes.
    """
    normalized = (scope or "active").strip().lower()
    if normalized not in _VALID_SCOPES:
        raise ValueError(f"Unsupported product scope: {scope!r}")
    return normalized  # type: ignore[return-value]


def is_online_store_published(product: dict[str, Any]) -> bool:
    """Return whether a product is published to the Online Store channel.

    Legacy snapshots did not include an Online Store publication field. When no
    explicit publication signal is present, products remain eligible so existing
    catalogs are not silently emptied until the next Shopify snapshot refresh.
    """
    if "onlineStoreUrl" in product:
        return bool(product.get("onlineStoreUrl"))

    if "onlineStorePublication" in product:
        publication = product.get("onlineStorePublication")
        if isinstance(publication, dict):
            if "isPublished" in publication:
                return bool(publication.get("isPublished"))
            if "publication" in publication:
                return publication.get("publication") is not None
            return bool(publication)
        return bool(publication)

    if "publishedAt" in product:
        return bool(product.get("publishedAt"))
    if "published_at" in product:
        return bool(product.get("published_at"))

    published_scope = product.get("published_scope")
    if published_scope is not None:
        return str(published_scope).lower() in {"web", "global"}

    return True


def is_active_online_store_product(product: dict[str, Any]) -> bool:
    """Return whether a product belongs to the default public V1 scope."""
    status = str(product.get("status") or "ACTIVE").upper()
    return status == "ACTIVE" and is_online_store_published(product)


def filter_products_by_scope(
    products: list[dict[str, Any]],
    scope: str | None = "active",
) -> list[dict[str, Any]]:
    """Filter Shopify snapshot products by public V1 scope.

    Args:
        products: Product dicts from a Shopify catalog snapshot.
        scope: ``active``, ``draft``, ``unlisted``, ``archived`` or ``all``.

    Returns:
        A new list containing only products matching the requested scope.
    """
    normalized = normalize_product_scope(scope)
    if normalized == "all":
        return list(products)
    if normalized == "active":
        return [product for product in products if is_active_online_store_product(product)]
    if normalized == "draft":
        return [product for product in products if str(product.get("status") or "").upper() == "DRAFT"]
    if normalized == "archived":
        return [product for product in products if str(product.get("status") or "").upper() == "ARCHIVED"]
    return [
        product
        for product in products
        if str(product.get("status") or "").upper() == "ACTIVE"
        and not is_online_store_published(product)
    ]


def summarize_product_scopes(products: list[dict[str, Any]], requested_scope: str | None = "active") -> dict[str, Any]:
    """Summarize catalog membership across the V1 product scopes."""
    scope = normalize_product_scope(requested_scope)
    counts = {
        "active": len(filter_products_by_scope(products, "active")),
        "draft": len(filter_products_by_scope(products, "draft")),
        "unlisted": len(filter_products_by_scope(products, "unlisted")),
        "archived": len(filter_products_by_scope(products, "archived")),
        "all": len(products),
    }
    return {
        "requested": scope,
        "included_products": counts[scope],
        "total_products": len(products),
        "counts": counts,
    }
