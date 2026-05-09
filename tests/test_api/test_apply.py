"""Tests for apply endpoints."""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import app

ENV = {
    "SHOPIFY_STORE_DOMAIN": "287c4a-bb.myshopify.com",
    "SHOPIFY_ACCESS_TOKEN": "shpat_test",
    "SHOPIFY_CLIENT_ID": "client_id",
    "SHOPIFY_CLIENT_SECRET": "client_secret",
    "SHOPIFY_SCOPES": "read_products",
    "APP_URL": "https://example.com",
}

SHOP = "287c4a-bb.myshopify.com"
PRODUCT_GID = "gid://shopify/Product/123456"


@pytest.fixture()
def client():
    with patch.dict("os.environ", ENV):
        yield TestClient(app)


def _auth_patches():
    return patch("app.api.deps.get_token", return_value=None)


def test_apply_meta_dry_run_returns_preview(client: TestClient):
    payload = [{"product_id": PRODUCT_GID, "title": "New Title", "description": "New desc"}]
    with _auth_patches():
        resp = client.post(f"/api/shops/{SHOP}/apply/meta?dry_run=true", json=payload)
    assert resp.status_code == 200
    result = resp.json()
    assert len(result) == 1
    assert result[0]["status"] == "preview"
    assert "New Title" in result[0]["detail"]


def test_apply_meta_dry_run_is_default(client: TestClient):
    payload = [{"product_id": PRODUCT_GID, "title": "Title"}]
    with _auth_patches():
        resp = client.post(f"/api/shops/{SHOP}/apply/meta", json=payload)
    assert resp.status_code == 200
    assert resp.json()[0]["status"] == "preview"


def test_apply_meta_dry_run_does_not_call_shopify(client: TestClient, mocker):
    mock_update = mocker.patch("app.api.apply.update_product_seo")
    payload = [{"product_id": PRODUCT_GID, "title": "Title"}]
    with _auth_patches():
        client.post(f"/api/shops/{SHOP}/apply/meta?dry_run=true", json=payload)
    mock_update.assert_not_called()


def test_apply_meta_apply_calls_shopify(client: TestClient, mocker):
    mock_update = mocker.patch("app.api.apply.update_product_seo", return_value={})
    payload = [{"product_id": PRODUCT_GID, "title": "New Title", "description": "New desc"}]
    with _auth_patches():
        resp = client.post(f"/api/shops/{SHOP}/apply/meta?dry_run=false", json=payload)
    assert resp.status_code == 200
    assert resp.json()[0]["status"] == "applied"
    mock_update.assert_called_once_with(
        product_id=PRODUCT_GID,
        seo_title="New Title",
        seo_description="New desc",
        endpoint=f"https://{SHOP}/admin/api/2025-01/graphql.json",
        headers={"X-Shopify-Access-Token": "shpat_test", "Content-Type": "application/json"},
    )


def test_apply_meta_shopify_error_returns_error_status(client: TestClient, mocker):
    mocker.patch("app.api.apply.update_product_seo", side_effect=RuntimeError("Shopify down"))
    payload = [{"product_id": PRODUCT_GID, "title": "Title"}]
    with _auth_patches():
        resp = client.post(f"/api/shops/{SHOP}/apply/meta?dry_run=false", json=payload)
    assert resp.status_code == 200
    assert resp.json()[0]["status"] == "error"
    assert "Shopify down" in resp.json()[0]["detail"]


def test_apply_meta_empty_list_returns_422(client: TestClient):
    with _auth_patches():
        resp = client.post(f"/api/shops/{SHOP}/apply/meta", json=[])
    assert resp.status_code == 422


def test_apply_meta_unknown_shop_returns_403(client: TestClient):
    with patch("app.api.deps.get_token", return_value=None):
        resp = client.post(
            "/api/shops/unknown.myshopify.com/apply/meta", json=[{"product_id": "x"}]
        )
    assert resp.status_code == 403
