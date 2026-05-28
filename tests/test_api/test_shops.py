"""Tests for shop management endpoints."""

import json
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.api.shops import _diagnose_visibility_issues
from app.db import init_db
from app.main import app

ENV = {
    "SHOPIFY_STORE_DOMAIN": "287c4a-bb.myshopify.com",
    "SHOPIFY_ACCESS_TOKEN": "shpat_test",
    "SHOPIFY_CLIENT_ID": "client_id",
    "SHOPIFY_CLIENT_SECRET": "client_secret",
    "SHOPIFY_SCOPES": "read_products",
    "APP_URL": "https://example.com",
    "INTERNAL_API_SECRET": "test-internal-secret",
}

_INTERNAL_HEADERS = {"X-Internal-Secret": "test-internal-secret"}


@pytest.fixture()
def client():
    with patch.dict("os.environ", ENV):
        yield TestClient(app)


def test_list_shops_without_internal_secret_returns_403(client: TestClient):
    """GET /api/shops is an admin endpoint — must reject without X-Internal-Secret."""
    resp = client.get("/api/shops")
    assert resp.status_code == 403


def test_list_shops_wrong_internal_secret_returns_403(client: TestClient):
    resp = client.get("/api/shops", headers={"X-Internal-Secret": "wrong"})
    assert resp.status_code == 403


def test_list_shops_empty(client: TestClient, mocker):
    mocker.patch("app.api.shops.list_tokens", return_value=[])
    resp = client.get("/api/shops", headers=_INTERNAL_HEADERS)
    assert resp.status_code == 200
    assert resp.json() == []


def test_list_shops_with_installs(client: TestClient, mocker):
    mocker.patch(
        "app.api.shops.list_tokens",
        return_value=[{"shop": "test.myshopify.com", "scope": "read_products"}],
    )
    resp = client.get("/api/shops", headers=_INTERNAL_HEADERS)
    assert resp.status_code == 200
    assert len(resp.json()) == 1
    assert resp.json()[0]["shop"] == "test.myshopify.com"


def test_shop_status_primary_tenant_with_snapshot(client: TestClient, tmp_path: Path):
    snapshot = {
        "products": [{"id": "1", "title": "T"}],
        "collections": [],
        "snapshot_date": "2026-05-09",
    }
    snap_file = tmp_path / "shopify_snapshot.json"
    snap_file.write_text(json.dumps(snapshot))

    with (
        patch("app.api.deps.get_token", return_value=None),
        patch("app.api.deps._SNAPSHOT_DEFAULT", snap_file),
    ):
        resp = client.get("/api/shops/287c4a-bb.myshopify.com/status")

    assert resp.status_code == 200
    body = resp.json()
    assert body["installed"] is True
    assert body["snapshot_available"] is True
    assert body["product_count"] == 1
    assert body["snapshot_date"] == "2026-05-09"


def test_shop_status_unknown_shop_returns_403(client: TestClient):
    with patch("app.api.deps.get_token", return_value=None):
        resp = client.get("/api/shops/unknown.myshopify.com/status")
    assert resp.status_code == 403


def test_shop_status_no_snapshot(client: TestClient, tmp_path: Path):
    with (
        patch("app.api.deps.get_token", return_value=None),
        patch("app.api.deps._SNAPSHOT_DEFAULT", tmp_path / "missing.json"),
    ):
        resp = client.get("/api/shops/287c4a-bb.myshopify.com/status")
    assert resp.status_code == 200
    assert resp.json()["snapshot_available"] is False
    assert resp.json()["product_count"] == 0


def test_shop_status_falls_back_to_db_snapshot(client: TestClient, tmp_path: Path):
    db = tmp_path / "history.db"
    init_db(db)
    with sqlite3.connect(db) as conn:
        conn.execute(
            """
            INSERT INTO snapshots
                (shop, snapshot_date, resource_type, resource_id, data_json)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                "287c4a-bb.myshopify.com",
                "2026-05-14T12:00:00Z",
                "product",
                "gid://shopify/Product/1",
                json.dumps({"id": "gid://shopify/Product/1", "title": "Harnais"}),
            ),
        )

    with (
        patch("app.api.deps.get_token", return_value=None),
        patch("app.api.deps._SNAPSHOT_DEFAULT", tmp_path / "missing.json"),
        patch("app.api.snapshot_store.DB_PATH", db),
    ):
        resp = client.get("/api/shops/287c4a-bb.myshopify.com/status")

    assert resp.status_code == 200
    body = resp.json()
    assert body["snapshot_available"] is True
    assert body["product_count"] == 1
    assert body["snapshot_date"] == "2026-05-14T12:00:00Z"


# ── Level-1 visibility diagnosis ────────────────────────────────────────────────


def _well_optimized_product() -> dict:
    """A product with no indexing red flags (old, rich content, images, SEO, collection)."""
    return {
        "id": "gid://shopify/Product/1",
        "title": "Harnais tout-en-un",
        "publishedAt": (datetime.now(UTC) - timedelta(days=90)).isoformat(),
        "description": "x" * 300,
        "images": {"edges": [{"node": {"url": "https://img/1.jpg"}}]},
        "seo": {"title": "Harnais", "description": "Le meilleur harnais"},
        "collections": {"edges": [{"node": {"title": "Chiens"}}]},
    }


def test_diagnose_returns_no_issues_for_well_optimized_product():
    assert _diagnose_visibility_issues(_well_optimized_product()) == []


def test_diagnose_flags_recently_published_product():
    product = _well_optimized_product()
    product["publishedAt"] = (datetime.now(UTC) - timedelta(days=3)).isoformat()
    assert "recently_published" in _diagnose_visibility_issues(product)


def test_diagnose_flags_thin_content():
    product = _well_optimized_product()
    product["description"] = "Court."
    assert "thin_content" in _diagnose_visibility_issues(product)


def test_diagnose_flags_missing_images_seo_and_collection():
    product = _well_optimized_product()
    product["images"] = {"edges": []}
    product["seo"] = {"title": "", "description": ""}
    product["collections"] = {"edges": []}
    issues = _diagnose_visibility_issues(product)
    assert {"no_images", "no_seo_meta", "no_collection"} <= set(issues)


def test_diagnose_tolerates_malformed_published_date():
    product = _well_optimized_product()
    product["publishedAt"] = "not-a-date"
    # Should not raise; recently_published simply not flagged.
    assert "recently_published" not in _diagnose_visibility_issues(product)
