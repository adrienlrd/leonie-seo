"""Tests for billing API endpoints and subscription webhook."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.db import init_db
from app.main import app

ENV = {
    "SHOPIFY_CLIENT_ID": "client_id",
    "SHOPIFY_CLIENT_SECRET": "test_secret",
    "SHOPIFY_SCOPES": "read_products",
    "APP_URL": "https://app.example.com",
    "SHOPIFY_STORE_DOMAIN": "store.myshopify.com",
    "SHOPIFY_ACCESS_TOKEN": "shpat_test",
}

SHOP = "store.myshopify.com"
SUB_GID = "gid://shopify/AppSubscription/42"


@pytest.fixture()
def db(tmp_path):
    path = tmp_path / "test.db"
    init_db(path)
    return path


@pytest.fixture()
def client():
    with patch.dict("os.environ", ENV):
        yield TestClient(app, raise_server_exceptions=True)


def _sign_webhook(body: bytes, secret: str = "test_secret") -> str:
    digest = hmac.new(secret.encode(), body, hashlib.sha256).digest()
    return base64.b64encode(digest).decode()


# ── GET /api/shops/{shop}/billing/plans ──────────────────────────────────────


def test_list_plans_returns_three_plans(client, db, monkeypatch):
    monkeypatch.setattr("app.billing.router.get_plan_for_shop", lambda shop, **kw: "free")
    resp = client.get(f"/api/shops/{SHOP}/billing/plans")
    assert resp.status_code == 200
    data = resp.json()
    plan_ids = [p["id"] for p in data["plans"]]
    assert "free" in plan_ids
    assert "pro" in plan_ids
    assert "agency" in plan_ids


def test_list_plans_marks_current_plan(client, monkeypatch):
    monkeypatch.setattr("app.billing.router.get_plan_for_shop", lambda shop, **kw: "pro")
    resp = client.get(f"/api/shops/{SHOP}/billing/plans")
    plans = {p["id"]: p for p in resp.json()["plans"]}
    assert plans["pro"]["current"] is True
    assert plans["free"]["current"] is False


# ── POST /api/shops/{shop}/billing/subscribe ─────────────────────────────────


def test_subscribe_returns_confirmation_url(client, db, monkeypatch):
    monkeypatch.setattr(
        "app.billing.router.create_subscription",
        lambda *a, **kw: {
            "confirmation_url": "https://partners.shopify.com/confirm",
            "subscription_id": SUB_GID,
        },
    )
    monkeypatch.setattr("app.billing.router.upsert_subscription", lambda **kw: None)
    resp = client.post(f"/api/shops/{SHOP}/billing/subscribe", json={"plan": "pro"})
    assert resp.status_code == 200
    assert "confirmation_url" in resp.json()


def test_subscribe_unknown_plan_returns_400(client):
    resp = client.post(f"/api/shops/{SHOP}/billing/subscribe", json={"plan": "enterprise"})
    assert resp.status_code == 400


def test_subscribe_billing_error_returns_502(client, monkeypatch):
    from app.billing.client import BillingError

    monkeypatch.setattr(
        "app.billing.router.create_subscription",
        lambda *a, **kw: (_ for _ in ()).throw(BillingError("fail")),
    )
    resp = client.post(f"/api/shops/{SHOP}/billing/subscribe", json={"plan": "pro"})
    assert resp.status_code == 502


# ── GET /api/shops/{shop}/billing/status ─────────────────────────────────────


def test_billing_status_no_subscription(client, monkeypatch):
    monkeypatch.setattr("app.billing.router.get_plan_for_shop", lambda shop, **kw: "free")
    monkeypatch.setattr("app.billing.router.get_subscription", lambda shop: None)
    resp = client.get(f"/api/shops/{SHOP}/billing/status")
    assert resp.status_code == 200
    assert resp.json()["plan"] == "free"
    assert resp.json()["subscription_id"] is None


# ── POST /api/shops/{shop}/billing/cancel ────────────────────────────────────


def test_cancel_no_active_subscription_returns_404(client, monkeypatch):
    monkeypatch.setattr("app.billing.router.get_subscription", lambda shop: None)
    resp = client.post(f"/api/shops/{SHOP}/billing/cancel")
    assert resp.status_code == 404


def test_cancel_active_subscription_succeeds(client, monkeypatch):
    monkeypatch.setattr(
        "app.billing.router.get_subscription",
        lambda shop: {"status": "active", "subscription_id": SUB_GID},
    )
    monkeypatch.setattr("app.billing.router.cancel_subscription", lambda *a, **kw: "cancelled")
    monkeypatch.setattr("app.billing.router.update_subscription_status", lambda *a, **kw: True)
    resp = client.post(f"/api/shops/{SHOP}/billing/cancel")
    assert resp.status_code == 200
    assert resp.json()["plan"] == "free"


# ── GET /billing/confirm ──────────────────────────────────────────────────────


def test_billing_confirm_activates_pending_subscription(client, db, monkeypatch):
    monkeypatch.setattr(
        "app.billing.router.get_subscription",
        lambda shop: {"status": "pending", "subscription_id": SUB_GID},
    )
    monkeypatch.setattr(
        "app.billing.router.update_subscription_status", lambda *a, **kw: True
    )
    resp = client.get(f"/billing/confirm?shop={SHOP}", follow_redirects=False)
    assert resp.status_code in (302, 307)


# ── POST /shopify/webhooks/app_subscriptions/update ──────────────────────────


def test_subscription_webhook_updates_status(client, db, monkeypatch):
    monkeypatch.setattr(
        "app.oauth.webhooks.update_subscription_status",
        lambda sub_id, status, **kw: True,
    )
    body = json.dumps(
        {
            "admin_graphql_api_id": SUB_GID,
            "status": "ACTIVE",
            "name": "Léonie SEO Pro",
        }
    ).encode()
    resp = client.post(
        "/shopify/webhooks/app_subscriptions/update",
        content=body,
        headers={"X-Shopify-Hmac-Sha256": _sign_webhook(body), "Content-Type": "application/json"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "active"


def test_subscription_webhook_invalid_hmac_returns_401(client):
    body = b'{"status": "ACTIVE"}'
    resp = client.post(
        "/shopify/webhooks/app_subscriptions/update",
        content=body,
        headers={"X-Shopify-Hmac-Sha256": "bad"},
    )
    assert resp.status_code == 401
