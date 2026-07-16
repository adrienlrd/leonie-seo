"""Tests for the merchant-selected managed-products store and filter."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from app.managed_products import (
    ManagedProductsCapExceeded,
    filter_managed_products,
    get_managed_product_ids,
    set_managed_product_ids,
)

SHOP = "test.myshopify.com"


@pytest.fixture(autouse=True)
def _use_tmp_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db = tmp_path / "test.db"
    monkeypatch.setattr("app.shop_config_store.DB_PATH", db)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    from app.db import init_db

    init_db(db_path=db)


@pytest.fixture(autouse=True)
def _cap_three(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.managed_products.product_cap", lambda shop, db_path=None: 3)


def _product(pid: str, status: str = "ACTIVE") -> dict:
    return {
        "id": f"gid://shopify/Product/{pid}",
        "title": f"Produit {pid}",
        "status": status,
        "publishedOnCurrentPublication": True,
    }


def test_get_returns_none_when_never_configured() -> None:
    assert get_managed_product_ids(SHOP) is None


def test_set_and_get_roundtrip_dedupes_and_strips() -> None:
    set_managed_product_ids(SHOP, ["gid://shopify/Product/1", "gid://shopify/Product/1", " gid://shopify/Product/2 "])
    assert get_managed_product_ids(SHOP) == [
        "gid://shopify/Product/1",
        "gid://shopify/Product/2",
    ]


def test_set_empty_selection_is_allowed_and_distinct_from_none() -> None:
    set_managed_product_ids(SHOP, [])
    assert get_managed_product_ids(SHOP) == []


def test_set_raises_over_plan_cap() -> None:
    with pytest.raises(ManagedProductsCapExceeded) as exc:
        set_managed_product_ids(SHOP, [f"gid://shopify/Product/{i}" for i in range(4)])
    assert exc.value.requested == 4
    assert exc.value.cap == 3


def test_filter_keeps_only_selected_products_in_snapshot_order() -> None:
    set_managed_product_ids(SHOP, ["gid://shopify/Product/3", "gid://shopify/Product/1"])
    products = [_product("1"), _product("2"), _product("3")]
    result = filter_managed_products(SHOP, products)
    assert [p["id"] for p in result] == [
        "gid://shopify/Product/1",
        "gid://shopify/Product/3",
    ]


def test_filter_fallback_inherits_last_analysis_and_persists_selection() -> None:
    latest = {
        "products": [
            {"product_id": "gid://shopify/Product/2"},
            {"product_id": "gid://shopify/Product/3"},
        ]
    }
    products = [_product("1"), _product("2"), _product("3")]
    with patch("app.market_analysis.jobs.load_latest_result", return_value=latest):
        result = filter_managed_products(SHOP, products)
    assert [p["id"] for p in result] == [
        "gid://shopify/Product/2",
        "gid://shopify/Product/3",
    ]
    # Inheritance is persisted: subsequent reads no longer need the fallback.
    assert get_managed_product_ids(SHOP) == [
        "gid://shopify/Product/2",
        "gid://shopify/Product/3",
    ]


def test_filter_fallback_without_analysis_keeps_historical_active_slice() -> None:
    products = [_product("1"), _product("2", status="DRAFT"), _product("3"), _product("4"), _product("5")]
    with patch("app.market_analysis.jobs.load_latest_result", return_value=None):
        result = filter_managed_products(SHOP, products)
    # Active-only, head-sliced to the cap of 3 — and nothing persisted.
    assert [p["id"] for p in result] == [
        "gid://shopify/Product/1",
        "gid://shopify/Product/3",
        "gid://shopify/Product/4",
    ]
    assert get_managed_product_ids(SHOP) is None


def test_filter_caps_selection_even_if_stored_list_is_larger() -> None:
    """Downgrade path: a pro shop with 5 selected products dropping to free
    (cap 3) must only get 3 products analyzed, without erroring."""
    import app.managed_products as mp

    with patch.object(mp, "product_cap", lambda shop, db_path=None: 5):
        set_managed_product_ids(SHOP, [f"gid://shopify/Product/{i}" for i in range(1, 6)])
    products = [_product(str(i)) for i in range(1, 6)]
    result = filter_managed_products(SHOP, products)
    assert len(result) == 3
