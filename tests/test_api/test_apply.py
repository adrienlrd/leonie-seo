"""Tests for apply endpoints."""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.apply.shopify_writer import ApplyResult
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


class _auth_patches:
    """Context manager: mock OAuth token lookup + plan resolution (Pro)."""

    def __enter__(self):
        self._p1 = patch("app.api.deps.get_token", return_value=None)
        self._p2 = patch("app.api.deps.get_plan_for_shop", return_value="pro")
        self._p1.start()
        self._p2.start()
        return self

    def __exit__(self, *args):
        self._p1.stop()
        self._p2.stop()


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
    mock_writer = mocker.patch("app.api.apply.ShopifyWriter")
    payload = [{"product_id": PRODUCT_GID, "title": "Title"}]
    with _auth_patches():
        client.post(f"/api/shops/{SHOP}/apply/meta?dry_run=true", json=payload)
    mock_writer.assert_not_called()


def test_apply_meta_apply_calls_shopify(client: TestClient, mocker):
    writer = mocker.Mock()
    writer.apply_product_seo.return_value = ApplyResult(resource_id=PRODUCT_GID, applied=True)
    mock_writer = mocker.patch("app.api.apply.ShopifyWriter", return_value=writer)
    payload = [{"product_id": PRODUCT_GID, "title": "New Title", "description": "New desc"}]
    with _auth_patches():
        resp = client.post(
            f"/api/shops/{SHOP}/apply/meta?dry_run=false&confirm_live_write=true",
            json=payload,
        )
    assert resp.status_code == 200
    assert resp.json()[0]["status"] == "applied"
    mock_writer.assert_called_once_with(SHOP, "shpat_test")
    writer.apply_product_seo.assert_called_once_with(PRODUCT_GID, "New Title", "New desc")


def test_apply_meta_shopify_writer_error_returns_error_status(client: TestClient, mocker):
    writer = mocker.Mock()
    writer.apply_product_seo.return_value = ApplyResult(
        resource_id=PRODUCT_GID,
        applied=False,
        error="Title is too long",
    )
    mocker.patch("app.api.apply.ShopifyWriter", return_value=writer)
    payload = [{"product_id": PRODUCT_GID, "title": "Title"}]
    with _auth_patches():
        resp = client.post(
            f"/api/shops/{SHOP}/apply/meta?dry_run=false&confirm_live_write=true",
            json=payload,
        )
    assert resp.status_code == 200
    assert resp.json()[0]["status"] == "error"
    assert "Title is too long" in resp.json()[0]["detail"]


def test_apply_meta_live_requires_explicit_confirmation(client: TestClient, mocker):
    mock_writer = mocker.patch("app.api.apply.ShopifyWriter")
    payload = [{"product_id": PRODUCT_GID, "title": "Title"}]
    with _auth_patches():
        resp = client.post(f"/api/shops/{SHOP}/apply/meta?dry_run=false", json=payload)
    assert resp.status_code == 409
    assert "confirm_live_write=true" in resp.json()["detail"]
    mock_writer.assert_not_called()


def test_apply_meta_allows_dry_run(client: TestClient):
    payload = [{"product_id": PRODUCT_GID, "title": "Title"}]
    with _auth_patches():
        resp = client.post(f"/api/shops/{SHOP}/apply/meta?dry_run=true", json=payload)
    assert resp.status_code == 200
    assert resp.json()[0]["status"] == "preview"


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


def test_apply_meta_rejects_internal_shop_mismatch(client: TestClient):
    headers = {
        "X-Leonie-Shop": "other.myshopify.com",
        "X-Internal-Secret": "test-internal-secret",
    }
    payload = [{"product_id": PRODUCT_GID, "title": "Title"}]
    with patch.dict("os.environ", {"INTERNAL_API_SECRET": "test-internal-secret"}):
        resp = client.post(f"/api/shops/{SHOP}/apply/meta", json=payload, headers=headers)
    assert resp.status_code == 403
