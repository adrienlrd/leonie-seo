"""Tests for market analysis job persistence helpers."""

from __future__ import annotations

import pytest


@pytest.fixture()
def analysis_with_products(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    import importlib

    import app.market_analysis.jobs as jobs_mod

    importlib.reload(jobs_mod)

    data = {
        "status": "completed",
        "products": [
            {"product_id": "gid://shopify/Product/1", "product_handle": "product-a"},
            {"product_id": "gid://shopify/Product/2", "product_handle": "product-b"},
            {"product_id": "gid://shopify/Product/3", "product_handle": "product-c"},
        ],
    }
    jobs_mod.save_latest_result("shop.myshopify.com", data)
    return jobs_mod, tmp_path


def test_remove_products_returns_zero_when_no_analysis(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    import importlib

    import app.market_analysis.jobs as jobs_mod

    importlib.reload(jobs_mod)

    removed = jobs_mod.remove_products_from_analysis(
        "shop.myshopify.com", {"gid://shopify/Product/1"}
    )
    assert removed == 0


def test_remove_products_filters_matching_ids(analysis_with_products):
    jobs_mod, _ = analysis_with_products

    removed = jobs_mod.remove_products_from_analysis(
        "shop.myshopify.com", {"gid://shopify/Product/1", "gid://shopify/Product/3"}
    )
    assert removed == 2

    result = jobs_mod.load_latest_result("shop.myshopify.com")
    assert result is not None
    remaining_ids = [p["product_id"] for p in result["products"]]
    assert remaining_ids == ["gid://shopify/Product/2"]


def test_remove_products_no_op_when_ids_not_present(analysis_with_products):
    jobs_mod, _ = analysis_with_products

    removed = jobs_mod.remove_products_from_analysis(
        "shop.myshopify.com", {"gid://shopify/Product/99"}
    )
    assert removed == 0

    result = jobs_mod.load_latest_result("shop.myshopify.com")
    assert result is not None
    assert len(result["products"]) == 3


def test_remove_products_no_op_when_empty_set(analysis_with_products):
    jobs_mod, _ = analysis_with_products

    removed = jobs_mod.remove_products_from_analysis("shop.myshopify.com", set())
    assert removed == 0
