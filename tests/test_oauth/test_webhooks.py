"""Tests for Shopify webhook handlers."""

import base64
import hashlib
import hmac
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import app

ENV = {
    "SHOPIFY_CLIENT_ID": "client_id",
    "SHOPIFY_CLIENT_SECRET": "client_secret",
    "SHOPIFY_SCOPES": "read_products",
    "APP_URL": "https://example.com",
}

SHOP = "test.myshopify.com"


@pytest.fixture()
def client():
    with patch.dict("os.environ", ENV):
        yield TestClient(app)


def _sign(body: bytes, secret: str = "client_secret") -> str:
    digest = hmac.new(secret.encode(), body, hashlib.sha256).digest()
    return base64.b64encode(digest).decode()


def test_app_uninstalled_valid_hmac_deletes_token(client: TestClient, mocker):
    mock_delete = mocker.patch("app.oauth.webhooks.delete_token")
    body = b'{"id":1,"name":"shop"}'
    headers = {
        "X-Shopify-Hmac-Sha256": _sign(body),
        "X-Shopify-Shop-Domain": SHOP,
        "Content-Type": "application/json",
    }
    resp = client.post("/shopify/webhooks/app/uninstalled", content=body, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "uninstalled"
    mock_delete.assert_called_once_with(SHOP)


def test_app_uninstalled_invalid_hmac_returns_401(client: TestClient, mocker):
    mock_delete = mocker.patch("app.oauth.webhooks.delete_token")
    body = b'{"id":1}'
    headers = {
        "X-Shopify-Hmac-Sha256": "invalid_signature",
        "X-Shopify-Shop-Domain": SHOP,
    }
    resp = client.post("/shopify/webhooks/app/uninstalled", content=body, headers=headers)
    assert resp.status_code == 401
    mock_delete.assert_not_called()


def test_app_uninstalled_missing_hmac_returns_401(client: TestClient):
    body = b'{"id":1}'
    headers = {"X-Shopify-Shop-Domain": SHOP}
    resp = client.post("/shopify/webhooks/app/uninstalled", content=body, headers=headers)
    assert resp.status_code == 401


def test_app_uninstalled_missing_shop_header_returns_400(client: TestClient):
    body = b'{"id":1}'
    headers = {"X-Shopify-Hmac-Sha256": _sign(body)}
    resp = client.post("/shopify/webhooks/app/uninstalled", content=body, headers=headers)
    assert resp.status_code == 400
