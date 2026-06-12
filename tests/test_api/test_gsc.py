"""Tests for Google Search Console API endpoints."""

from __future__ import annotations

from unittest.mock import patch

import pandas as pd
from fastapi.testclient import TestClient

from app.main import app

ENV = {
    "SHOPIFY_STORE_DOMAIN": "store.myshopify.com",
    "SHOPIFY_ACCESS_TOKEN": "shpat_test",
    "SHOPIFY_CLIENT_ID": "client_id",
    "SHOPIFY_CLIENT_SECRET": "client_secret",
    "SHOPIFY_SCOPES": "read_products",
    "APP_URL": "https://app.example.com",
    "INTERNAL_API_SECRET": "internal",
    "GOOGLE_OAUTH_CLIENT_PATH": "/tmp/google-client.json",
}

HEADERS = {
    "X-Leonie-Shop": "store.myshopify.com",
    "X-Internal-Secret": "internal",
    "X-Shopify-Access-Token": "shpat_test",
}


def test_gsc_disconnect_deletes_shared_google_token(monkeypatch) -> None:
    """The disconnect endpoint clears the shop's Google token (shared by GSC + GA4)."""
    monkeypatch.setenv("INTERNAL_API_SECRET", "internal")
    with (
        patch.dict("os.environ", ENV),
        patch("app.api.gsc.delete_google_token") as delete_token,
    ):
        resp = TestClient(app).delete(
            "/api/shops/store.myshopify.com/gsc/disconnect", headers=HEADERS
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body == {"shop": "store.myshopify.com", "disconnected": True}
    delete_token.assert_called_once_with("store.myshopify.com")


def test_gsc_status_reports_disconnected_when_no_google_token_exists(monkeypatch) -> None:
    monkeypatch.setenv("INTERNAL_API_SECRET", "internal")
    with (
        patch.dict("os.environ", ENV),
        patch("app.api.gsc.get_google_token", return_value=None),
        patch("app.api.gsc.latest_import_status", return_value={"available": False, "row_count": 0}),
    ):
        resp = TestClient(app).get("/api/shops/store.myshopify.com/gsc/status", headers=HEADERS)

    assert resp.status_code == 200
    body = resp.json()
    assert body["configured"] is True
    assert body["connected"] is False
    assert body["reauth_required"] is False
    assert body["action_required"]


def test_gsc_status_reports_reauth_required_when_google_revoked_the_token(monkeypatch) -> None:
    monkeypatch.setenv("INTERNAL_API_SECRET", "internal")
    with (
        patch.dict("os.environ", ENV),
        patch("app.api.gsc.get_google_token", return_value=None),
        patch("app.api.gsc.get_shop_config", return_value="1"),
        patch("app.api.gsc.latest_import_status", return_value={"available": False, "row_count": 0}),
    ):
        resp = TestClient(app).get("/api/shops/store.myshopify.com/gsc/status", headers=HEADERS)

    assert resp.status_code == 200
    body = resp.json()
    assert body["connected"] is False
    assert body["reauth_required"] is True
    assert "Reconnect" in body["action_required"]


def test_gsc_status_ignores_stale_reauth_flag_when_token_exists(monkeypatch) -> None:
    monkeypatch.setenv("INTERNAL_API_SECRET", "internal")
    with (
        patch.dict("os.environ", ENV),
        patch("app.api.gsc.get_google_token", return_value={"email": "a@example.com"}),
        patch("app.api.gsc.get_shop_config", return_value="1"),
        patch("app.api.gsc.latest_import_status", return_value={"available": True, "row_count": 10}),
    ):
        resp = TestClient(app).get("/api/shops/store.myshopify.com/gsc/status", headers=HEADERS)

    assert resp.status_code == 200
    body = resp.json()
    assert body["connected"] is True
    assert body["reauth_required"] is False
    assert body["action_required"] is None


def test_gsc_authorize_returns_authorization_url(monkeypatch) -> None:
    monkeypatch.setenv("INTERNAL_API_SECRET", "internal")
    with (
        patch.dict("os.environ", ENV),
        patch("app.api.gsc.create_state", return_value="state"),
        patch("app.api.gsc.build_authorization_url", return_value=("https://accounts.google.com/o/oauth2/auth", None)),
    ):
        resp = TestClient(app).post("/api/shops/store.myshopify.com/gsc/authorize", headers=HEADERS)

    assert resp.status_code == 200
    assert resp.json()["authorization_url"].startswith("https://accounts.google.com")


def test_gsc_import_requires_connected_google_token(monkeypatch) -> None:
    monkeypatch.setenv("INTERNAL_API_SECRET", "internal")
    with (
        patch.dict("os.environ", ENV),
        patch("app.api.gsc.get_google_token", return_value=None),
    ):
        resp = TestClient(app).post("/api/shops/store.myshopify.com/gsc/import", headers=HEADERS, json={})

    assert resp.status_code == 409
    assert "not connected" in resp.json()["detail"]


def test_gsc_opportunities_returns_empty_state_when_no_import_exists(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("INTERNAL_API_SECRET", "internal")
    with patch.dict("os.environ", ENV), patch("app.api.gsc._DATA_DIR", tmp_path):
        resp = TestClient(app).get("/api/shops/store.myshopify.com/gsc/opportunities", headers=HEADERS)

    assert resp.status_code == 200
    body = resp.json()
    assert body["available"] is False
    assert body["opportunities"] == []
    assert body["summary"]["total"] == 0


def test_gsc_opportunities_returns_prioritized_opportunities(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("INTERNAL_API_SECRET", "internal")
    shop_dir = tmp_path / "store.myshopify.com"
    shop_dir.mkdir(parents=True)
    pd.DataFrame(
        [
            {
                "url": "https://example.com/products/a",
                "clicks": 2,
                "impressions": 150,
                "ctr": 0.013,
                "position": 13.5,
            },
            {
                "url": "https://example.com/products/b",
                "clicks": 5,
                "impressions": 300,
                "ctr": 0.017,
                "position": 11.0,
            },
        ]
    ).to_csv(shop_dir / "gsc_performance.csv", index=False)

    with patch.dict("os.environ", ENV), patch("app.api.gsc._DATA_DIR", tmp_path):
        resp = TestClient(app).get("/api/shops/store.myshopify.com/gsc/opportunities", headers=HEADERS)

    assert resp.status_code == 200
    body = resp.json()
    assert body["available"] is True
    assert body["summary"]["total"] == 2
    assert body["summary"]["by_zone"]["quick_win"] == 2
    assert body["opportunities"][0]["opportunity_score"] >= body["opportunities"][1]["opportunity_score"]
