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


def _seed_shop_data(db, raw_dir, shop):
    with sqlite3.connect(db) as conn:
        conn.execute(
            "INSERT INTO shop_tokens (shop, access_token, installed_at, updated_at) "
            "VALUES (?, 'tok', 'now', 'now')",
            (shop,),
        )
        conn.execute(
            "INSERT INTO shop_config (shop, key, value) VALUES (?, 'lang', 'fr')", (shop,)
        )
        conn.execute(
            "INSERT INTO analysis_artifacts (shop, artifact_type, data_json, updated_at) "
            "VALUES (?, 'market_analysis', '{}', 'now')",
            (shop,),
        )
    shop_dir = raw_dir / shop
    shop_dir.mkdir(parents=True)
    (shop_dir / "shopify_snapshot.json").write_text("{}")


def test_shop_redact_purges_db_rows_and_raw_files_and_returns_200(client, tmp_path, monkeypatch):
    db = tmp_path / "test.db"
    raw_dir = tmp_path / "raw"
    monkeypatch.setattr("app.oauth.gdpr.DB_PATH", db)
    monkeypatch.setattr("app.oauth.gdpr._RAW_DIR", raw_dir)
    from app.db import init_db

    init_db(db)
    _seed_shop_data(db, raw_dir, SHOP)
    _seed_shop_data(db, raw_dir, "other-shop.myshopify.com")

    resp = client.post("/shopify/webhooks/shop/redact", content=BODY, headers=_headers(BODY))
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}

    with sqlite3.connect(db) as conn:
        for table in ("shop_tokens", "shop_config", "analysis_artifacts"):
            assert (
                conn.execute(f"SELECT COUNT(*) FROM {table} WHERE shop = ?", (SHOP,)).fetchone()[0]  # noqa: S608
                == 0
            )
            assert (
                conn.execute(
                    f"SELECT COUNT(*) FROM {table} WHERE shop = ?",  # noqa: S608
                    ("other-shop.myshopify.com",),
                ).fetchone()[0]
                == 1
            )
        # Audit trail must survive the purge.
        rows = conn.execute("SELECT topic, shop FROM gdpr_requests").fetchall()
    assert rows == [("shop/redact", SHOP)]
    assert not (raw_dir / SHOP).exists()
    assert (raw_dir / "other-shop.myshopify.com" / "shopify_snapshot.json").exists()


def test_shop_redact_invalid_shop_domain_skips_purge_and_returns_200(
    client, tmp_path, monkeypatch
):
    db = tmp_path / "test.db"
    monkeypatch.setattr("app.oauth.gdpr.DB_PATH", db)
    from app.db import init_db

    init_db(db)
    mock_purge = patch("app.oauth.gdpr.purge_shop_data").start()
    headers = {
        "X-Shopify-Hmac-Sha256": _sign(BODY),
        "X-Shopify-Shop-Domain": "../evil",
        "Content-Type": "application/json",
    }
    resp = client.post("/shopify/webhooks/shop/redact", content=BODY, headers=headers)
    assert resp.status_code == 200
    mock_purge.assert_not_called()
    patch.stopall()


def test_purge_shop_data_rejects_malformed_domain(tmp_path, monkeypatch):
    from app.oauth.gdpr import purge_shop_data

    monkeypatch.setattr("app.oauth.gdpr.DB_PATH", tmp_path / "test.db")
    with pytest.raises(ValueError, match="Invalid shop domain"):
        purge_shop_data("../../etc")


def test_purge_shop_data_covers_every_shop_scoped_table(tmp_path, monkeypatch):
    """Every table created by init_db with a `shop` column must be purged
    (except the gdpr_requests audit trail) — guards against schema drift."""
    db = tmp_path / "test.db"
    monkeypatch.setattr("app.oauth.gdpr.DB_PATH", db)
    from app.db import init_db
    from app.oauth.gdpr import _SHOP_SCOPED_TABLES

    init_db(db)
    with sqlite3.connect(db) as conn:
        tables = [
            r[0]
            for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        ]
        shop_tables = {
            t
            for t in tables
            if any(r[1] == "shop" for r in conn.execute(f"PRAGMA table_info({t})").fetchall())
        }
    expected = shop_tables - {"gdpr_requests"}
    assert expected == set(_SHOP_SCOPED_TABLES)


# ── in-app reset (Danger Zone) ───────────────────────────────────────────────


def test_reset_shop_data_wipes_everything_except_token_and_subscription(tmp_path, monkeypatch):
    db = tmp_path / "test.db"
    raw_dir = tmp_path / "raw"
    monkeypatch.setattr("app.oauth.gdpr.DB_PATH", db)
    monkeypatch.setattr("app.oauth.gdpr._RAW_DIR", raw_dir)
    from app.db import init_db
    from app.oauth.gdpr import _RESET_PRESERVED_TABLES, reset_shop_data

    init_db(db)
    _seed_shop_data(db, raw_dir, SHOP)
    with sqlite3.connect(db) as conn:
        conn.execute(
            "INSERT INTO subscriptions (shop, plan, status, created_at, updated_at) "
            "VALUES (?, 'pro', 'active', 'now', 'now')",
            (SHOP,),
        )
        conn.execute(
            "INSERT INTO redeemed_quota_codes (code, shop, redeemed_at) "
            "VALUES ('GEO-TEST-ABCDEF12', ?, 'now')",
            (SHOP,),
        )

    result = reset_shop_data(SHOP)
    # shop_config + analysis_artifacts seeded above = 2 rows wiped, no failures.
    assert result["deleted"] == 2
    assert result["failed"] == []

    with sqlite3.connect(db) as conn:
        # Preserved: OAuth token + subscription keep the app installed and billed.
        for table in _RESET_PRESERVED_TABLES:
            assert (
                conn.execute(f"SELECT COUNT(*) FROM {table} WHERE shop = ?", (SHOP,)).fetchone()[0]  # noqa: S608
                == 1
            )
        # Wiped: everything else, including analysis artifacts.
        for table in ("shop_config", "analysis_artifacts"):
            assert (
                conn.execute(f"SELECT COUNT(*) FROM {table} WHERE shop = ?", (SHOP,)).fetchone()[0]  # noqa: S608
                == 0
            )
    assert not (raw_dir / SHOP).exists()


def test_reset_shop_data_deletes_business_profile(tmp_path, monkeypatch):
    """The whole point of a reset: the merchant must land back on onboarding.

    The home loader keeps showing a populated dashboard as long as
    load_business_profile returns a validated profile — which reads
    business_profile.json first (data dir), then the analysis_artifacts row.
    Reset must clear BOTH, so its raw dir must be the same one the profile is
    written to. Guards against the prod bug where reset wiped DB rows but a
    hardcoded, DATA_DIR-ignoring path left the file on disk.
    """
    db = tmp_path / "test.db"
    data = tmp_path / "raw"
    monkeypatch.setattr("app.oauth.gdpr.DB_PATH", db)
    monkeypatch.setattr("app.oauth.gdpr._RAW_DIR", data)
    monkeypatch.setattr("app.business_profile.jobs._DATA_DIR", data)
    from app.business_profile.jobs import load_business_profile, save_business_profile
    from app.db import init_db
    from app.oauth.gdpr import reset_shop_data

    init_db(db)
    save_business_profile(SHOP, {"brand": "X", "status": "validated"}, db_path=db)
    assert load_business_profile(SHOP, db_path=db) is not None

    reset_shop_data(SHOP)

    assert load_business_profile(SHOP, db_path=db) is None
    assert not (data / SHOP).exists()


def test_reset_shop_data_rejects_malformed_domain(tmp_path, monkeypatch):
    from app.oauth.gdpr import reset_shop_data

    monkeypatch.setattr("app.oauth.gdpr.DB_PATH", tmp_path / "test.db")
    with pytest.raises(ValueError, match="Invalid shop domain"):
        reset_shop_data("../../etc")


def test_reset_preserved_tables_are_shop_scoped():
    """Preserved tables must be a subset of the purge allowlist — guards against
    a typo silently preserving nothing (or a non-existent table)."""
    from app.oauth.gdpr import _RESET_PRESERVED_TABLES, _SHOP_SCOPED_TABLES

    assert set(_RESET_PRESERVED_TABLES) <= set(_SHOP_SCOPED_TABLES)


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


def test_reset_shop_data_preserves_plan_override(tmp_path, monkeypatch):
    """The Danger Zone reset must not silently downgrade an overridden plan."""
    db = tmp_path / "test.db"
    raw_dir = tmp_path / "raw"
    monkeypatch.setattr("app.oauth.gdpr.DB_PATH", db)
    monkeypatch.setattr("app.oauth.gdpr._RAW_DIR", raw_dir)
    from app.db import init_db
    from app.oauth.gdpr import reset_shop_data

    init_db(db)
    with sqlite3.connect(db) as conn:
        conn.execute(
            "INSERT INTO shop_config (shop, key, value) VALUES (?, 'plan_override', 'agency')",
            (SHOP,),
        )
        conn.execute(
            "INSERT INTO shop_config (shop, key, value) VALUES (?, 'app_language', 'fr')",
            (SHOP,),
        )
        conn.execute(
            "INSERT INTO shop_config (shop, key, value) VALUES (?, 'managed_product_ids', '[]')",
            (SHOP,),
        )

    reset_shop_data(SHOP)

    with sqlite3.connect(db) as conn:
        rows = dict(
            conn.execute(
                "SELECT key, value FROM shop_config WHERE shop = ?", (SHOP,)
            ).fetchall()
        )
    # plan_override and the app language survive; everything else is wiped.
    assert rows == {"plan_override": "agency", "app_language": "fr"}
