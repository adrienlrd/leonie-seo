"""Tests for privacy policy page and GDPR data export endpoint."""

from __future__ import annotations

import sqlite3
from contextlib import ExitStack
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.db import init_db
from app.main import app

ENV = {
    "SHOPIFY_STORE_DOMAIN": "store.myshopify.com",
    "SHOPIFY_ACCESS_TOKEN": "shpat_test",
    "SHOPIFY_CLIENT_ID": "client_id",
    "SHOPIFY_CLIENT_SECRET": "client_secret",
    "SHOPIFY_SCOPES": "read_products",
    "APP_URL": "https://example.com",
}

SHOP = "store.myshopify.com"


@pytest.fixture()
def client():
    with patch.dict("os.environ", ENV):
        yield TestClient(app)


class _shop_patches:
    def __init__(self, plan: str = "pro"):
        self._plan = plan

    def __enter__(self):
        self._stack = ExitStack()
        self._stack.enter_context(patch("app.api.deps.get_token", return_value=None))
        self._stack.enter_context(patch("app.api.deps.get_plan_for_shop", return_value=self._plan))
        return self

    def __exit__(self, *args):
        self._stack.close()


# ── GET /privacy ──────────────────────────────────────────────────────────────


def test_privacy_policy_returns_200(client):
    resp = client.get("/privacy")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]


def test_privacy_policy_contains_gdpr_export_url(client):
    resp = client.get("/privacy")
    assert "/api/gdpr/export" in resp.text


def test_privacy_policy_bilingual(client):
    resp = client.get("/privacy")
    assert "Politique de confidentialité" in resp.text
    assert "Privacy Policy" in resp.text


def test_privacy_policy_app_store_mode_mentions_neon_and_publisher(client):
    """In default app_store mode: must declare Neon Postgres host and that
    the publisher is the data controller — NOT 'self-hosted'."""
    with patch.dict("os.environ", {"LEONIE_MODE": "app_store"}):
        resp = client.get("/privacy")
    assert "Neon Postgres" in resp.text
    assert "publisher" in resp.text or "éditeur" in resp.text
    # Must NOT claim the app is self-hosted
    assert "auto-hébergé" not in resp.text


def test_privacy_policy_self_hosted_mode_declares_self_hosted(client):
    """In self_hosted mode: must declare the merchant is the data controller
    and that no data leaves their environment."""
    with patch.dict("os.environ", {"LEONIE_MODE": "self_hosted"}):
        resp = client.get("/privacy")
    assert "auto-hébergé" in resp.text or "self-hosted" in resp.text


def test_privacy_policy_default_is_app_store_mode(client):
    """When LEONIE_MODE is unset, the privacy policy must default to the
    App Store variant (conservative — assumes SaaS hosting)."""
    env_no_mode = {k: v for k, v in ENV.items() if k != "LEONIE_MODE"}
    with patch.dict("os.environ", env_no_mode, clear=True):
        resp = client.get("/privacy")
    assert "Neon Postgres" in resp.text


# ── GET /api/gdpr/export ──────────────────────────────────────────────────────


def test_gdpr_export_returns_shop_field(client):
    with _shop_patches():
        resp = client.get(f"/api/gdpr/export?shop={SHOP}")
    assert resp.status_code == 200
    assert resp.json()["shop"] == SHOP


def test_gdpr_export_has_exported_at(client):
    with _shop_patches():
        resp = client.get(f"/api/gdpr/export?shop={SHOP}")
    assert "exported_at" in resp.json()


def test_gdpr_export_data_structure(client):
    with _shop_patches():
        resp = client.get(f"/api/gdpr/export?shop={SHOP}")
    data = resp.json()["data"]
    assert "installation" in data
    assert "subscription" in data
    assert "gdpr_requests" in data


def test_gdpr_export_does_not_expose_access_token(client):
    token_record = {
        "shop": SHOP,
        "access_token": "shpat_super_secret",
        "scope": "read_products",
        "installed_at": "2026-05-01T00:00:00+00:00",
        "updated_at": "2026-05-01T00:00:00+00:00",
    }
    with _shop_patches(), patch("app.api.privacy.get_token", return_value=token_record):
        resp = client.get(f"/api/gdpr/export?shop={SHOP}")
    body = resp.text
    assert "shpat_super_secret" not in body
    assert resp.json()["data"]["installation"]["scope"] == "read_products"


def test_gdpr_export_includes_gdpr_requests(client, tmp_path, monkeypatch):
    db = tmp_path / "test.db"
    init_db(db)
    with sqlite3.connect(db) as conn:
        conn.execute(
            "INSERT INTO gdpr_requests (received_at, topic, shop, payload) VALUES (?, ?, ?, ?)",
            ("2026-05-10T10:00:00+00:00", "customers/data_request", SHOP, "{}"),
        )
    monkeypatch.setattr("app.api.privacy.DB_PATH", db)
    with _shop_patches():
        resp = client.get(f"/api/gdpr/export?shop={SHOP}")
    requests = resp.json()["data"]["gdpr_requests"]
    assert len(requests) == 1
    assert requests[0]["topic"] == "customers/data_request"


def test_gdpr_export_unknown_shop_returns_403(client):
    with patch("app.api.deps.get_token", return_value=None):
        resp = client.get("/api/gdpr/export?shop=unknown.myshopify.com")
    assert resp.status_code == 403
