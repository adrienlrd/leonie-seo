"""Tests for the shared FastAPI dependencies (auth + shop resolution)."""

import time
from unittest.mock import patch

import jwt
import pytest
from fastapi.testclient import TestClient

from app.main import app

CLIENT_ID = "test_client_id"
CLIENT_SECRET = "test_client_secret"
SHOP = "mystore.myshopify.com"

ENV_AUTH_ON = {
    "SHOPIFY_CLIENT_ID": CLIENT_ID,
    "SHOPIFY_CLIENT_SECRET": CLIENT_SECRET,
    "SHOPIFY_SCOPES": "read_products",
    "APP_URL": "https://example.com",
    "LEONIE_REQUIRE_SESSION_TOKEN": "true",
}


def _valid_jwt(shop: str = SHOP) -> str:
    now = int(time.time())
    payload = {
        "iss": f"https://{shop}/admin",
        "dest": f"https://{shop}/admin",
        "aud": CLIENT_ID,
        "sub": "1",
        "exp": now + 60,
        "nbf": now - 60,
        "iat": now,
        "jti": "x",
        "sid": "s",
    }
    return jwt.encode(payload, CLIENT_SECRET, algorithm="HS256")


@pytest.fixture()
def client_auth_on():
    with patch.dict("os.environ", ENV_AUTH_ON):
        yield TestClient(app)


def test_request_without_auth_header_rejected_when_auth_required(client_auth_on, mocker):
    mocker.patch("app.api.deps.get_token", return_value={"access_token": "t"})
    resp = client_auth_on.get(f"/api/shops/{SHOP}/status")
    assert resp.status_code == 401


def test_request_with_invalid_token_rejected(client_auth_on, mocker):
    mocker.patch("app.api.deps.get_token", return_value={"access_token": "t"})
    resp = client_auth_on.get(
        f"/api/shops/{SHOP}/status",
        headers={"Authorization": "Bearer not.a.jwt"},
    )
    assert resp.status_code == 401


def test_request_with_token_for_different_shop_rejected(client_auth_on, mocker):
    mocker.patch("app.api.deps.get_token", return_value={"access_token": "t"})
    token = _valid_jwt(shop="other.myshopify.com")
    resp = client_auth_on.get(
        f"/api/shops/{SHOP}/status",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403


def test_request_with_valid_token_passes(client_auth_on, mocker, tmp_path):
    mocker.patch(
        "app.api.deps.get_token",
        return_value={"access_token": "shpat_real_token"},
    )
    # Snapshot file does not need to exist for /status — it just reports the absence.
    token = _valid_jwt()
    resp = client_auth_on.get(
        f"/api/shops/{SHOP}/status",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["shop"] == SHOP


def test_auth_disabled_in_dev_mode_allows_request(mocker):
    """LEONIE_REQUIRE_SESSION_TOKEN=false must allow requests without a token."""
    env = {**ENV_AUTH_ON, "LEONIE_REQUIRE_SESSION_TOKEN": "false"}
    mocker.patch("app.api.deps.get_token", return_value={"access_token": "t"})
    with patch.dict("os.environ", env):
        client = TestClient(app)
        resp = client.get(f"/api/shops/{SHOP}/status")
    assert resp.status_code == 200
