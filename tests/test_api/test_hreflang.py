"""Tests for hreflang international SEO endpoints."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import app

SHOP = "hreflang-test.myshopify.com"

ENV = {
    "SHOPIFY_STORE_DOMAIN": SHOP,
    "SHOPIFY_ACCESS_TOKEN": "shpat_test",
    "SHOPIFY_CLIENT_ID": "client_id",
    "SHOPIFY_CLIENT_SECRET": "client_secret",
    "SHOPIFY_SCOPES": "read_products",
    "APP_URL": "https://example.com",
}

MARKETS_FR_BE = [
    {"locale": "fr-FR", "url_prefix": "", "primary": True},
    {"locale": "fr-BE", "url_prefix": "/fr-be", "primary": False},
    {"locale": "en-GB", "url_prefix": "/en-gb", "primary": False},
]


@pytest.fixture()
def client(tmp_path: Path):
    with patch.dict("os.environ", ENV):
        with patch("app.db_adapter.DB_PATH", tmp_path / "test.db"):
            from app.db import init_db

            init_db(tmp_path / "test.db")
            yield TestClient(app)


# ---------------------------------------------------------------------------
# Status
# ---------------------------------------------------------------------------


def test_status_empty_when_no_markets(client: TestClient):
    r = client.get(f"/api/shops/{SHOP}/hreflang/status")
    assert r.status_code == 200
    data = r.json()
    assert data["configured"] is False
    assert data["markets_count"] == 0
    assert data["ready"] is False
    assert data["issues_count"] > 0  # "no_markets" issue


def test_status_returns_markets_after_save(client: TestClient):
    client.post(f"/api/shops/{SHOP}/hreflang/settings", json={"markets": MARKETS_FR_BE})
    r = client.get(f"/api/shops/{SHOP}/hreflang/status")
    data = r.json()
    assert data["configured"] is True
    assert data["markets_count"] == 3
    assert data["ready"] is True
    assert data["error_count"] == 0


# ---------------------------------------------------------------------------
# Save settings
# ---------------------------------------------------------------------------


def test_save_settings_persists_markets(client: TestClient):
    r = client.post(f"/api/shops/{SHOP}/hreflang/settings", json={"markets": MARKETS_FR_BE})
    assert r.status_code == 200
    data = r.json()
    assert data["saved"] is True
    assert data["markets_count"] == 3


def test_save_settings_invalid_locale_rejected(client: TestClient):
    r = client.post(
        f"/api/shops/{SHOP}/hreflang/settings",
        json={"markets": [{"locale": "INVALID", "url_prefix": "", "primary": True}]},
    )
    assert r.status_code == 422


def test_save_settings_prefix_without_slash_rejected(client: TestClient):
    r = client.post(
        f"/api/shops/{SHOP}/hreflang/settings",
        json={"markets": [{"locale": "fr-FR", "url_prefix": "fr-be", "primary": False}]},
    )
    assert r.status_code == 422


# ---------------------------------------------------------------------------
# Issue detection
# ---------------------------------------------------------------------------


def test_issues_no_primary_detected(client: TestClient):
    markets = [
        {"locale": "fr-FR", "url_prefix": "/fr", "primary": False},
        {"locale": "en-GB", "url_prefix": "/en", "primary": False},
    ]
    r = client.post(f"/api/shops/{SHOP}/hreflang/settings", json={"markets": markets})
    issues = r.json()["issues"]
    codes = [i["code"] for i in issues]
    assert "no_primary" in codes


def test_issues_duplicate_locale_detected(client: TestClient):
    markets = [
        {"locale": "fr-FR", "url_prefix": "", "primary": True},
        {"locale": "fr-FR", "url_prefix": "/fr-be", "primary": False},
    ]
    r = client.post(f"/api/shops/{SHOP}/hreflang/settings", json={"markets": markets})
    codes = [i["code"] for i in r.json()["issues"]]
    assert "duplicate_locale" in codes


def test_issues_single_market_info(client: TestClient):
    markets = [{"locale": "fr-FR", "url_prefix": "", "primary": True}]
    r = client.post(f"/api/shops/{SHOP}/hreflang/settings", json={"markets": markets})
    codes = [i["code"] for i in r.json()["issues"]]
    assert "single_market" in codes


# ---------------------------------------------------------------------------
# Preview
# ---------------------------------------------------------------------------


def test_preview_unavailable_when_no_markets(client: TestClient):
    with patch("app.api.hreflang._load_markets", return_value=[]):
        r = client.get(f"/api/shops/{SHOP}/hreflang/preview")
    assert r.status_code == 200
    assert r.json()["available"] is False


def test_preview_generates_tags(client: TestClient, tmp_path: Path):
    client.post(f"/api/shops/{SHOP}/hreflang/settings", json={"markets": MARKETS_FR_BE})

    fake_snapshot = {
        "products": [{"handle": "croquettes-chien"}],
        "collections": [{"handle": "chiens"}],
    }

    with patch("app.api.hreflang.load_snapshot_from_file_or_db", return_value=fake_snapshot):
        with patch("app.api.hreflang._base_url", return_value="https://example.com"):
            r = client.get(f"/api/shops/{SHOP}/hreflang/preview?max_pages=5")

    assert r.status_code == 200
    data = r.json()
    assert data["available"] is True
    assert len(data["pages"]) > 0

    home = next(p for p in data["pages"] if p["type"] == "home")
    hreflangs = {t["hreflang"] for t in home["tags"]}
    assert "fr-FR" in hreflangs
    assert "fr-BE" in hreflangs
    assert "en-GB" in hreflangs
    assert "x-default" in hreflangs

    assert "fr-FR" in home["html"]
    assert 'hreflang="x-default"' in home["html"]


def test_preview_x_default_points_to_primary(client: TestClient):
    client.post(f"/api/shops/{SHOP}/hreflang/settings", json={"markets": MARKETS_FR_BE})

    with patch("app.api.hreflang.load_snapshot_from_file_or_db", return_value={}):
        with patch("app.api.hreflang._base_url", return_value="https://example.com"):
            r = client.get(f"/api/shops/{SHOP}/hreflang/preview")

    home = next(p for p in r.json()["pages"] if p["type"] == "home")
    x_default = next(t for t in home["tags"] if t["hreflang"] == "x-default")
    fr_fr = next(t for t in home["tags"] if t["hreflang"] == "fr-FR")
    assert x_default["href"] == fr_fr["href"]


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------


def test_delete_removes_markets(client: TestClient):
    client.post(f"/api/shops/{SHOP}/hreflang/settings", json={"markets": MARKETS_FR_BE})
    r = client.delete(f"/api/shops/{SHOP}/hreflang/settings")
    assert r.status_code == 200
    assert r.json()["deleted"] is True

    status = client.get(f"/api/shops/{SHOP}/hreflang/status").json()
    assert status["configured"] is False
