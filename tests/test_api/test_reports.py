"""Tests for exportable reports endpoints."""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

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
}

_SNAPSHOT = {
    "products": [
        {
            "id": "gid://shopify/Product/1",
            "title": "Harnais Chien",
            "handle": "harnais-chien",
            "seo": {"title": None, "description": None},
            "images": {
                "edges": [{"node": {"id": "gid://shopify/ProductImage/10",
                                    "url": "https://cdn.shopify.com/img1.jpg",
                                    "altText": None}}]
            },
        },
        {
            "id": "gid://shopify/Product/2",
            "title": "Collier Chat",
            "handle": "collier-chat",
            "seo": {
                "title": "Collier de luxe pour chat — boutique Léonie",
                "description": "Découvrez notre collier pour chat, élégant et résistant, parfait pour votre félin.",
            },
            "images": {"edges": []},
        },
    ],
    "collections": [
        {
            "id": "gid://shopify/Collection/10",
            "title": "Chiens",
            "handle": "chiens",
            "seo": {"title": None, "description": None},
        },
    ],
}


@pytest.fixture()
def client():
    with patch.dict("os.environ", ENV):
        yield TestClient(app)


@pytest.fixture()
def snapshot_file(tmp_path: Path) -> Path:
    p = tmp_path / "shopify_snapshot.json"
    p.write_text(json.dumps(_SNAPSHOT))
    return p


@pytest.fixture()
def db_with_changes(tmp_path: Path) -> Path:
    db = tmp_path / "history.db"
    now = datetime.now(UTC).isoformat()
    with sqlite3.connect(db) as conn:
        conn.execute("""CREATE TABLE seo_changes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            shop TEXT, applied_at TEXT NOT NULL,
            resource_type TEXT NOT NULL, resource_id TEXT NOT NULL,
            field TEXT NOT NULL, old_value TEXT, new_value TEXT,
            status TEXT NOT NULL)""")
        conn.execute(
            "INSERT INTO seo_changes (shop, applied_at, resource_type, resource_id, field, old_value, new_value, status) VALUES (?,?,?,?,?,?,?,?)",
            (SHOP, now, "product", "gid://shopify/Product/1", "seo.title", "Old", "New Title", "applied"),
        )
    return db


# ---------------------------------------------------------------------------
# /reports/list
# ---------------------------------------------------------------------------


def test_list_reports_snapshot_available(client, snapshot_file, db_with_changes) -> None:
    with (
        patch("app.api.deps.get_token", return_value=None),
        patch("app.api.deps._SNAPSHOT_DEFAULT", snapshot_file),
        patch("app.api.reports.load_snapshot_from_file_or_db", return_value=_SNAPSHOT),
        patch("app.api.reports.DB_PATH", db_with_changes),
    ):
        resp = client.get(f"/api/shops/{SHOP}/reports/list")

    assert resp.status_code == 200
    data = resp.json()
    audit = next(r for r in data["reports"] if r["type"] == "audit")
    delta = next(r for r in data["reports"] if r["type"] == "delta")
    assert audit["available"] is True
    assert delta["available"] is True


def test_list_reports_no_snapshot(client, tmp_path) -> None:
    missing = tmp_path / "missing.json"
    with (
        patch("app.api.deps.get_token", return_value=None),
        patch("app.api.deps._SNAPSHOT_DEFAULT", missing),
        patch("app.api.reports.load_snapshot_from_file_or_db", return_value=None),
        patch("app.api.reports.DB_PATH", tmp_path / "empty.db"),
    ):
        with sqlite3.connect(tmp_path / "empty.db") as conn:
            conn.execute("""CREATE TABLE seo_changes (id INTEGER PRIMARY KEY, shop TEXT,
                applied_at TEXT NOT NULL, resource_type TEXT NOT NULL,
                resource_id TEXT NOT NULL, field TEXT NOT NULL,
                old_value TEXT, new_value TEXT, status TEXT NOT NULL)""")
        resp = client.get(f"/api/shops/{SHOP}/reports/list")

    assert resp.status_code == 200
    audit = next(r for r in resp.json()["reports"] if r["type"] == "audit")
    assert audit["available"] is False


# ---------------------------------------------------------------------------
# /reports/audit
# ---------------------------------------------------------------------------


def test_audit_report_returns_markdown(client, snapshot_file) -> None:
    with (
        patch("app.api.deps.get_token", return_value=None),
        patch("app.api.deps._SNAPSHOT_DEFAULT", snapshot_file),
        patch("app.api.reports.load_snapshot_from_file_or_db", return_value=_SNAPSHOT),
    ):
        resp = client.get(f"/api/shops/{SHOP}/reports/audit")

    assert resp.status_code == 200
    assert "text/plain" in resp.headers["content-type"]
    body = resp.text
    assert "# Rapport d'audit SEO" in body
    assert SHOP in body


def test_audit_report_detects_missing_meta_title(client, snapshot_file) -> None:
    with (
        patch("app.api.deps.get_token", return_value=None),
        patch("app.api.deps._SNAPSHOT_DEFAULT", snapshot_file),
        patch("app.api.reports.load_snapshot_from_file_or_db", return_value=_SNAPSHOT),
    ):
        resp = client.get(f"/api/shops/{SHOP}/reports/audit")

    assert "missing_meta_title" in resp.text.lower() or "Missing Meta Title" in resp.text


def test_audit_report_detects_missing_alt_text(client, snapshot_file) -> None:
    with (
        patch("app.api.deps.get_token", return_value=None),
        patch("app.api.deps._SNAPSHOT_DEFAULT", snapshot_file),
        patch("app.api.reports.load_snapshot_from_file_or_db", return_value=_SNAPSHOT),
    ):
        resp = client.get(f"/api/shops/{SHOP}/reports/audit")

    assert "alt" in resp.text.lower()


def test_audit_report_no_snapshot_returns_404(client, tmp_path) -> None:
    with (
        patch("app.api.deps.get_token", return_value=None),
        patch("app.api.deps._SNAPSHOT_DEFAULT", tmp_path / "missing.json"),
        patch("app.api.reports.load_snapshot_from_file_or_db", return_value=None),
    ):
        resp = client.get(f"/api/shops/{SHOP}/reports/audit")

    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# /reports/delta
# ---------------------------------------------------------------------------


def test_delta_report_returns_markdown(client, snapshot_file, db_with_changes) -> None:
    with (
        patch("app.api.deps.get_token", return_value=None),
        patch("app.api.deps._SNAPSHOT_DEFAULT", snapshot_file),
        patch("app.api.reports.DB_PATH", db_with_changes),
    ):
        resp = client.get(f"/api/shops/{SHOP}/reports/delta")

    assert resp.status_code == 200
    body = resp.text
    assert "# Rapport de modifications SEO" in body
    assert SHOP in body


def test_delta_report_contains_change_data(client, snapshot_file, db_with_changes) -> None:
    with (
        patch("app.api.deps.get_token", return_value=None),
        patch("app.api.deps._SNAPSHOT_DEFAULT", snapshot_file),
        patch("app.api.reports.DB_PATH", db_with_changes),
    ):
        resp = client.get(f"/api/shops/{SHOP}/reports/delta")

    body = resp.text
    assert "seo.title" in body
    assert "New Title" in body
    assert "Old" in body


def test_delta_report_empty_db(client, tmp_path) -> None:
    db = tmp_path / "empty.db"
    with sqlite3.connect(db) as conn:
        conn.execute("""CREATE TABLE seo_changes (id INTEGER PRIMARY KEY, shop TEXT,
            applied_at TEXT NOT NULL, resource_type TEXT NOT NULL,
            resource_id TEXT NOT NULL, field TEXT NOT NULL,
            old_value TEXT, new_value TEXT, status TEXT NOT NULL)""")

    with (
        patch("app.api.deps.get_token", return_value=None),
        patch("app.api.deps._SNAPSHOT_DEFAULT", tmp_path / "s.json"),
        patch("app.api.reports.DB_PATH", db),
    ):
        resp = client.get(f"/api/shops/{SHOP}/reports/delta")

    assert resp.status_code == 200
    assert "0 modification" in resp.text
