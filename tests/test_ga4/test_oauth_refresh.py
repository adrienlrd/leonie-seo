"""Tests for GA4 credential refresh failure handling (revoked Google token)."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import google.auth.exceptions

from app.ga4.oauth import get_credentials

_FAKE_TOKEN = json.dumps(
    {
        "token": None,
        "refresh_token": "fake_refresh",
        "token_uri": "https://oauth2.googleapis.com/token",
        "client_id": "fake_client",
        "client_secret": "fake_secret",
        "scopes": ["https://www.googleapis.com/auth/analytics.readonly"],
    }
)


def test_get_credentials_flags_reauth_and_clears_token_on_invalid_grant(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.ga4.oauth.get_google_token",
        lambda shop, **kw: {"token_json": _FAKE_TOKEN, "email": "a@example.com"},
    )
    deleted: list[str] = []
    monkeypatch.setattr(
        "app.ga4.oauth.delete_google_token", lambda shop, **kw: deleted.append(shop)
    )
    flags: list[tuple[str, str, str]] = []
    monkeypatch.setattr(
        "app.ga4.oauth.set_shop_config", lambda shop, key, value: flags.append((shop, key, value))
    )

    mock_creds = MagicMock()
    mock_creds.expired = True
    mock_creds.refresh_token = "fake_refresh"
    mock_creds.refresh.side_effect = google.auth.exceptions.RefreshError("invalid_grant")

    with patch("app.ga4.oauth.Credentials.from_authorized_user_info", return_value=mock_creds):
        result = get_credentials("store.myshopify.com")

    assert result is None
    assert deleted == ["store.myshopify.com"]
    assert flags == [("store.myshopify.com", "google_reauth_required", "1")]
