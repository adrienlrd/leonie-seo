"""Tests for GDPR mandatory webhooks (task 51)."""

from __future__ import annotations

import base64
import hashlib
import hmac
import sqlite3
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import app

ENV = {
    "SHOPIFY_CLIENT_ID": "client_id",
    "SHOPIFY_CLIENT_SECRET": "test_secret",
    "SHOPIFY_SCOPES": "read_products",
    "APP_URL": "https://example.com",
}

SHOP = "gdpr-test.myshopify.com"
BODY = b'{"shop_id": 1, "shop_domain": "gdpr-test.myshopify.com"}'


@pytest.fixture()
def client():
    with patch.dict("os.environ", ENV):
        yield TestClient(app)


def _sign(body: bytes, secret: str = "test_secret") -> str:
    digest = hmac.new(secret.encode(), body, hashlib.sha256).digest()
    return base64.b64encode(digest).decode()


def _headers(body: bytes, *, include_shop: bool = True) -> dict:
    h = {"X-Shopify-Hmac-Sha256": _sign(body), "Content-Type": "application/json"}
    if include_shop:
        h["X-Shopify-Shop-Domain"] = SHOP
    return h


# ── customers/data_request ────────────────────────────────────────────────────


def test_customers_data_request_valid_returns_200(client, tmp_path, monkeypatch):
    monkeypatch.setattr("app.oauth.gdpr.DB_PATH", tmp_path / "test.db")
    from app.db import init_db

    init_db(tmp_path / "test.db")
    resp = client.post(
        "/shopify/webhooks/customers/data_request", content=BODY, headers=_headers(BODY)
    )
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_customers_data_request_invalid_hmac_returns_401(client):
    headers = {"X-Shopify-Hmac-Sha256": "bad", "X-Shopify-Shop-Domain": SHOP}
    resp = client.post("/shopify/webhooks/customers/data_request", content=BODY, headers=headers)
    assert resp.status_code == 401


def test_customers_data_request_missing_hmac_returns_401(client):
    resp = client.post(
        "/shopify/webhooks/customers/data_request",
        content=BODY,
        headers={"X-Shopify-Shop-Domain": SHOP},
    )
    assert resp.status_code == 401


# ── customers/redact ──────────────────────────────────────────────────────────


def test_customers_redact_valid_returns_200(client, tmp_path, monkeypatch):
    monkeypatch.setattr("app.oauth.gdpr.DB_PATH", tmp_path / "test.db")
    from app.db import init_db

    init_db(tmp_path / "test.db")
    resp = client.post("/shopify/webhooks/customers/redact", content=BODY, headers=_headers(BODY))
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_customers_redact_invalid_hmac_returns_401(client):
    headers = {"X-Shopify-Hmac-Sha256": "bad", "X-Shopify-Shop-Domain": SHOP}
    resp = client.post("/shopify/webhooks/customers/redact", content=BODY, headers=headers)
    assert resp.status_code == 401


def test_customers_redact_missing_hmac_returns_401(client):
    resp = client.post(
        "/shopify/webhooks/customers/redact", content=BODY, headers={"X-Shopify-Shop-Domain": SHOP}
    )
    assert resp.status_code == 401


# ── shop/redact ───────────────────────────────────────────────────────────────


def test_shop_redact_valid_deletes_token_and_returns_200(client, tmp_path, monkeypatch):
    monkeypatch.setattr("app.oauth.gdpr.DB_PATH", tmp_path / "test.db")
    from app.db import init_db

    init_db(tmp_path / "test.db")
    mock_delete = patch("app.oauth.gdpr.delete_token").start()
    resp = client.post("/shopify/webhooks/shop/redact", content=BODY, headers=_headers(BODY))
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
    mock_delete.assert_called_once_with(SHOP)
    patch.stopall()


def test_shop_redact_invalid_hmac_returns_401(client):
    headers = {"X-Shopify-Hmac-Sha256": "bad", "X-Shopify-Shop-Domain": SHOP}
    resp = client.post("/shopify/webhooks/shop/redact", content=BODY, headers=headers)
    assert resp.status_code == 401


def test_shop_redact_missing_hmac_returns_401(client):
    resp = client.post(
        "/shopify/webhooks/shop/redact", content=BODY, headers={"X-Shopify-Shop-Domain": SHOP}
    )
    assert resp.status_code == 401


# ── audit trail ──────────────────────────────────────────────────────────────


def test_gdpr_request_logged_to_db(client, tmp_path, monkeypatch):
    db = tmp_path / "test.db"
    monkeypatch.setattr("app.oauth.gdpr.DB_PATH", db)
    from app.db import init_db

    init_db(db)
    client.post("/shopify/webhooks/customers/data_request", content=BODY, headers=_headers(BODY))
    with sqlite3.connect(db) as conn:
        rows = conn.execute("SELECT topic, shop FROM gdpr_requests").fetchall()
    assert len(rows) == 1
    assert rows[0] == ("customers/data_request", SHOP)


def test_verify_webhook_hmac_exported_from_hmac_validator():
    from app.oauth.hmac_validator import verify_webhook_hmac

    secret = "mysecret"
    body = b"hello"
    sig = _sign(body, secret)
    assert verify_webhook_hmac(body, sig, secret) is True
    assert verify_webhook_hmac(body, "bad", secret) is False
    assert verify_webhook_hmac(body, None, secret) is False
