"""Tests for the OAuth install/callback flow."""

import hashlib
import hmac as hmac_lib
from unittest.mock import AsyncMock, MagicMock, patch
from urllib.parse import urlencode

import pytest
from fastapi.testclient import TestClient

from app.main import app

ENV = {
    "SHOPIFY_CLIENT_ID": "test_client_id",
    "SHOPIFY_CLIENT_SECRET": "test_secret",
    "SHOPIFY_SCOPES": "read_products,write_products",
    "APP_URL": "https://my-app.example.com",
}


@pytest.fixture()
def client():
    with patch.dict("os.environ", ENV):
        yield TestClient(app)


def _sign(params: dict, secret: str = "test_secret") -> str:
    filtered = {k: v for k, v in params.items() if k != "hmac"}
    msg = urlencode(sorted(filtered.items()))
    return hmac_lib.new(secret.encode(), msg.encode(), hashlib.sha256).hexdigest()


# --- /install ---


def test_install_redirects_to_shopify_oauth(client: TestClient):
    resp = client.get("/shopify/install?shop=mystore.myshopify.com", follow_redirects=False)
    assert resp.status_code in (302, 307)
    loc = resp.headers["location"]
    assert "mystore.myshopify.com/admin/oauth/authorize" in loc
    assert "client_id=test_client_id" in loc
    assert "state=" in loc


def test_install_includes_redirect_uri(client: TestClient):
    resp = client.get("/shopify/install?shop=mystore.myshopify.com", follow_redirects=False)
    loc = resp.headers["location"]
    assert "redirect_uri=" in loc
    assert "shopify/callback" in loc


def test_install_rejects_non_myshopify_domain(client: TestClient):
    resp = client.get("/shopify/install?shop=evil.example.com", follow_redirects=False)
    assert resp.status_code == 400


def test_install_rejects_empty_shop(client: TestClient):
    resp = client.get("/shopify/install?shop=", follow_redirects=False)
    assert resp.status_code in (400, 422)


# --- /callback ---


def test_callback_rejects_invalid_shop_format(client: TestClient):
    params = {"shop": "evil.example.com", "code": "abc", "state": "xyz", "hmac": "bad"}
    resp = client.get("/shopify/callback", params=params)
    assert resp.status_code == 400


def test_callback_rejects_invalid_hmac(client: TestClient):
    params = {"shop": "mystore.myshopify.com", "code": "abc", "state": "xyz", "hmac": "bad"}
    resp = client.get("/shopify/callback", params=params)
    assert resp.status_code == 403


def test_callback_rejects_unknown_state(client: TestClient, mocker):
    mocker.patch("app.oauth.router.consume_state", return_value=False)
    params = {"shop": "mystore.myshopify.com", "code": "abc", "state": "unknown-uuid"}
    params["hmac"] = _sign(params)
    resp = client.get("/shopify/callback", params=params)
    assert resp.status_code == 403


def test_callback_full_flow(client: TestClient, mocker):
    mocker.patch("app.oauth.router.save_token")
    mocker.patch("app.oauth.router.consume_state", return_value=True)

    shop = "mystore.myshopify.com"
    code = "auth_code_123"
    params = {"shop": shop, "code": code, "state": "stub-state"}
    params["hmac"] = _sign(params)

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"access_token": "shpat_real", "scope": "read_products"}

    mock_http = AsyncMock()
    mock_http.__aenter__.return_value = mock_http
    mock_http.post.return_value = mock_resp

    with patch("app.oauth.router.httpx.AsyncClient", return_value=mock_http):
        resp = client.get("/shopify/callback", params=params)

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "installed"
    assert body["shop"] == shop
    assert "access_token" not in body  # never exposed


def test_callback_returns_502_when_shopify_token_exchange_fails(client: TestClient, mocker):
    mocker.patch("app.oauth.router.save_token")
    mocker.patch("app.oauth.router.consume_state", return_value=True)

    params = {"shop": "mystore.myshopify.com", "code": "bad_code", "state": "stub"}
    params["hmac"] = _sign(params)

    mock_resp = MagicMock()
    mock_resp.status_code = 400

    mock_http = AsyncMock()
    mock_http.__aenter__.return_value = mock_http
    mock_http.post.return_value = mock_resp

    with patch("app.oauth.router.httpx.AsyncClient", return_value=mock_http):
        resp = client.get("/shopify/callback", params=params)

    assert resp.status_code == 502


# --- /health ---


def test_health_endpoint(client: TestClient):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
