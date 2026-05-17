"""Tests for GA4 OAuth2 endpoints — authorize, callback, settings, disconnect."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app

SHOP = "287c4a-bb.myshopify.com"

ENV = {
    "SHOPIFY_STORE_DOMAIN": SHOP,
    "SHOPIFY_ACCESS_TOKEN": "shpat_test",
    "SHOPIFY_CLIENT_ID": "client_id",
    "SHOPIFY_CLIENT_SECRET": "client_secret",
    "SHOPIFY_SCOPES": "read_products",
    "APP_URL": "https://example.com",
    "GOOGLE_OAUTH_CLIENT_CONFIG": '{"web":{"client_id":"id","client_secret":"sec","redirect_uris":["https://example.com"],"auth_uri":"https://accounts.google.com/o/oauth2/auth","token_uri":"https://oauth2.googleapis.com/token"}}',
    "GOOGLE_OAUTH_STATE_SECRET": "test-secret-32chars-padded-here-!!",
}

_FAKE_URL = "https://accounts.google.com/o/oauth2/auth?scope=analytics"
_FAKE_PROPS = [
    {"property_id": "123456789", "property_name": "My Store", "account_name": "Acme"}
]


@pytest.fixture()
def client(tmp_path: Path):
    with patch.dict("os.environ", ENV):
        with patch("app.db_adapter.DB_PATH", tmp_path / "test.db"):
            from app.db import init_db

            init_db(tmp_path / "test.db")
            yield TestClient(app)


@pytest.fixture()
def authed_client(client):
    """Client with shop token pre-seeded and get_token patched."""
    return client


# ---------------------------------------------------------------------------
# Status
# ---------------------------------------------------------------------------


def test_ga4_status_not_connected(authed_client):
    with patch("app.api.deps.get_token", return_value=None):
        resp = authed_client.get(f"/api/shops/{SHOP}/ga4/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["oauth_connected"] is False
    assert data["ready"] is False


def test_ga4_status_connected_with_property(authed_client, tmp_path):
    from app.gsc.token_store import save_google_token
    from app.shop_config_store import set_shop_config

    with patch("app.api.deps.get_token", return_value=None), patch(
        "app.db_adapter.DB_PATH", tmp_path / "test.db"
    ):
        save_google_token(SHOP, '{"token":"abc"}', "analytics.readonly", email="test@test.com")
        set_shop_config(SHOP, "ga4_property_id", "123456789")
        set_shop_config(SHOP, "ga4_property_name", "My Store")
        resp = authed_client.get(f"/api/shops/{SHOP}/ga4/status")

    assert resp.status_code == 200
    data = resp.json()
    assert data["oauth_connected"] is True
    assert data["property_id"] == "123456789"
    assert data["property_name"] == "My Store"
    assert data["ready"] is True


# ---------------------------------------------------------------------------
# Authorize
# ---------------------------------------------------------------------------


def test_ga4_authorize_returns_url(authed_client):
    with (
        patch("app.api.deps.get_token", return_value=None),
        patch("app.api.ga4.build_authorization_url", return_value=(_FAKE_URL, None)),
    ):
        resp = authed_client.post(f"/api/shops/{SHOP}/ga4/authorize")
    assert resp.status_code == 200
    assert resp.json()["authorization_url"] == _FAKE_URL


def test_ga4_authorize_not_configured(authed_client):
    with (
        patch("app.api.deps.get_token", return_value=None),
        patch("app.api.ga4.ga4_oauth_configured", return_value=False),
    ):
        resp = authed_client.post(f"/api/shops/{SHOP}/ga4/authorize")
    assert resp.status_code == 503


# ---------------------------------------------------------------------------
# Callback
# ---------------------------------------------------------------------------


def test_ga4_callback_saves_token(authed_client, tmp_path):
    fake_creds = MagicMock()
    fake_creds.to_json.return_value = '{"token":"abc","refresh_token":"ref"}'

    with (
        patch("app.api.ga4.verify_state", return_value=SHOP),
        patch("app.api.ga4.exchange_code", return_value=fake_creds),
        patch("app.api.ga4.save_credentials") as mock_save,
        patch("app.api.ga4.get_shop_config", return_value=None),
        patch("app.api.ga4.delete_shop_config"),
    ):
        resp = authed_client.get(
            "/api/google/ga4/callback", params={"code": "abc123", "state": "valid.state"}
        )
    assert resp.status_code == 200
    assert "connecté" in resp.text.lower()
    mock_save.assert_called_once_with(SHOP, fake_creds)


def test_ga4_callback_invalid_state(authed_client):
    from app.gsc.oauth_state import GoogleOAuthStateError

    with patch("app.api.ga4.verify_state", side_effect=GoogleOAuthStateError("bad state")):
        resp = authed_client.get(
            "/api/google/ga4/callback", params={"code": "abc", "state": "bad.state"}
        )
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Properties
# ---------------------------------------------------------------------------


def test_ga4_list_properties(authed_client):
    with (
        patch("app.api.deps.get_token", return_value=None),
        patch("app.api.ga4.list_properties", return_value=_FAKE_PROPS),
    ):
        resp = authed_client.get(f"/api/shops/{SHOP}/ga4/properties")
    assert resp.status_code == 200
    assert resp.json()["properties"] == _FAKE_PROPS


def test_ga4_list_properties_not_connected(authed_client):
    from app.ga4.oauth import GA4OAuthError

    with (
        patch("app.api.deps.get_token", return_value=None),
        patch("app.api.ga4.list_properties", side_effect=GA4OAuthError("not connected")),
    ):
        resp = authed_client.get(f"/api/shops/{SHOP}/ga4/properties")
    assert resp.status_code == 409


# ---------------------------------------------------------------------------
# Save settings
# ---------------------------------------------------------------------------


def test_ga4_save_settings(authed_client):
    with (
        patch("app.api.deps.get_token", return_value=None),
        patch("app.api.ga4.set_shop_config") as mock_set,
    ):
        resp = authed_client.post(
            f"/api/shops/{SHOP}/ga4/settings",
            json={"property_id": "123456789", "property_name": "My Store"},
        )
    assert resp.status_code == 200
    assert resp.json()["saved"] is True
    assert mock_set.call_count == 2


def test_ga4_save_settings_empty_property_id(authed_client):
    with patch("app.api.deps.get_token", return_value=None):
        resp = authed_client.post(
            f"/api/shops/{SHOP}/ga4/settings",
            json={"property_id": "  ", "property_name": ""},
        )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Disconnect
# ---------------------------------------------------------------------------


def test_ga4_disconnect(authed_client):
    with (
        patch("app.api.deps.get_token", return_value=None),
        patch("app.api.ga4.disconnect") as mock_disc,
        patch("app.api.ga4.delete_shop_config") as mock_del,
    ):
        resp = authed_client.delete(f"/api/shops/{SHOP}/ga4/disconnect")
    assert resp.status_code == 200
    assert resp.json()["disconnected"] is True
    mock_disc.assert_called_once_with(SHOP)
    assert mock_del.call_count == 2
