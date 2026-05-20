"""Tests for Shopify product scope filtering."""

from __future__ import annotations

import pytest

from app.snapshot.scope import (
    filter_products_by_scope,
    is_active_online_store_product,
    normalize_product_scope,
    summarize_product_scopes,
)


def _product(
    pid: str,
    *,
    status: str | None = "ACTIVE",
    online_store_url: str | None = "https://example.com/products/p",
    include_online_store_url: bool = True,
) -> dict:
    product = {
        "id": pid,
        "title": f"Product {pid}",
        "handle": f"product-{pid}",
    }
    if status is not None:
        product["status"] = status
    if include_online_store_url:
        product["onlineStoreUrl"] = online_store_url
    return product


def test_filter_products_by_scope_returns_active_online_store_when_default() -> None:
    products = [
        _product("active"),
        _product("unlisted", online_store_url=None),
        _product("draft", status="DRAFT", online_store_url=None),
        _product("archived", status="ARCHIVED", online_store_url=None),
    ]

    result = filter_products_by_scope(products)

    assert [product["id"] for product in result] == ["active"]


def test_filter_products_by_scope_keeps_legacy_products_when_publication_signal_missing() -> None:
    product = _product("legacy", status=None, include_online_store_url=False)

    assert is_active_online_store_product(product) is True
    assert filter_products_by_scope([product], "active") == [product]


def test_filter_products_by_scope_returns_dedicated_views_when_requested() -> None:
    products = [
        _product("active"),
        _product("unlisted", online_store_url=None),
        _product("draft", status="DRAFT", online_store_url=None),
        _product("archived", status="ARCHIVED", online_store_url=None),
    ]

    assert [product["id"] for product in filter_products_by_scope(products, "draft")] == ["draft"]
    assert [product["id"] for product in filter_products_by_scope(products, "unlisted")] == ["unlisted"]
    assert [product["id"] for product in filter_products_by_scope(products, "archived")] == ["archived"]
    assert [product["id"] for product in filter_products_by_scope(products, "all")] == [
        "active",
        "unlisted",
        "draft",
        "archived",
    ]


def test_summarize_product_scopes_returns_counts_when_catalog_has_mixed_statuses() -> None:
    products = [
        _product("active"),
        _product("unlisted", online_store_url=None),
        _product("draft", status="DRAFT", online_store_url=None),
        _product("archived", status="ARCHIVED", online_store_url=None),
    ]

    summary = summarize_product_scopes(products)

    assert summary["requested"] == "active"
    assert summary["included_products"] == 1
    assert summary["counts"] == {
        "active": 1,
        "draft": 1,
        "unlisted": 1,
        "archived": 1,
        "all": 4,
    }


def test_normalize_product_scope_raises_when_scope_is_unknown() -> None:
    with pytest.raises(ValueError, match="Unsupported product scope"):
        normalize_product_scope("published")
