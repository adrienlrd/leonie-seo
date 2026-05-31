"""Shared deterministic helpers for GEO crawlability and llms.txt generation.

These helpers were extracted from ``crawlability.py`` so the llms.txt generator
can reuse the exact same snapshot parsing and page-selection rules without
duplicating logic or importing a sibling module's private symbols.
"""

from __future__ import annotations

import re
from typing import Any

from app.geo.readiness import score_product_readiness

POLICY_PATHS: tuple[tuple[str, str], ...] = (
    ("/policies/privacy-policy", "Privacy policy"),
    ("/policies/refund-policy", "Refund policy"),
    ("/policies/shipping-policy", "Shipping policy"),
    ("/pages/contact", "Contact"),
)


def strip_html(value: str | None) -> str:
    return re.sub(r"<[^>]+>", " ", value or "").strip()


def product_description(product: dict[str, Any]) -> str:
    return strip_html(
        product.get("descriptionHtml")
        or product.get("body_html")
        or product.get("description")
        or ""
    )


def shop_domain(shop: str, snapshot: dict[str, Any]) -> str:
    shop_meta = snapshot.get("shop", {}) or {}
    primary = shop_meta.get("primaryDomain", {}) or {}
    domain = str(
        primary.get("host") or shop_meta.get("myshopifyDomain") or shop_meta.get("domain") or shop
    ).strip()
    return domain.replace("https://", "").replace("http://", "").strip("/")


def absolute_url(domain: str, path: str) -> str:
    return f"https://{domain}{path}"


def resource_row(
    *,
    resource_type: str,
    title: str,
    path: str,
    reason: str,
    priority: str,
) -> dict[str, str]:
    return {
        "resource_type": resource_type,
        "title": title,
        "path": path,
        "reason": reason,
        "priority": priority,
    }


def product_rows(
    products: list[dict[str, Any]],
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    included: list[dict[str, str]] = []
    excluded: list[dict[str, str]] = []
    scored = []
    for product in products:
        title = str(product.get("title") or "").strip()
        handle = str(product.get("handle") or "").strip()
        if not title or not handle:
            excluded.append(
                resource_row(
                    resource_type="product",
                    title=title or "Untitled product",
                    path="",
                    reason="Missing title or handle, so the page cannot be safely listed.",
                    priority="exclude",
                )
            )
            continue
        readiness = score_product_readiness(product)
        description_words = len(product_description(product).split())
        if description_words < 8:
            excluded.append(
                resource_row(
                    resource_type="product",
                    title=title,
                    path=f"/products/{handle}",
                    reason="Product copy is too thin for useful AI crawl guidance.",
                    priority="review",
                )
            )
            continue
        scored.append((readiness["readiness_score"], title, handle))

    scored.sort(key=lambda item: (-item[0], item[1]))
    for score, title, handle in scored:
        priority = "high" if score >= 70 else "medium" if score >= 45 else "review"
        included.append(
            resource_row(
                resource_type="product",
                title=title,
                path=f"/products/{handle}",
                reason=f"Product page with AI Search readiness {score}/100.",
                priority=priority,
            )
        )
    return included, excluded


def collection_rows(
    collections: list[dict[str, Any]],
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    included: list[dict[str, str]] = []
    excluded: list[dict[str, str]] = []
    for collection in collections:
        title = str(collection.get("title") or "").strip()
        handle = str(collection.get("handle") or "").strip()
        if not title or not handle:
            excluded.append(
                resource_row(
                    resource_type="collection",
                    title=title or "Untitled collection",
                    path="",
                    reason="Missing title or handle, so the collection cannot be safely listed.",
                    priority="exclude",
                )
            )
            continue
        included.append(
            resource_row(
                resource_type="collection",
                title=title,
                path=f"/collections/{handle}",
                reason="Collection page can help AI crawlers understand product grouping and buying intent.",
                priority="medium",
            )
        )
    included.sort(key=lambda item: item["title"])
    return included, excluded
