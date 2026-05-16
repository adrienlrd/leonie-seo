"""Tests for audit endpoints."""

import json
import sqlite3
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.db import init_db
from app.main import app

ENV = {
    "SHOPIFY_STORE_DOMAIN": "287c4a-bb.myshopify.com",
    "SHOPIFY_ACCESS_TOKEN": "shpat_test",
    "SHOPIFY_CLIENT_ID": "client_id",
    "SHOPIFY_CLIENT_SECRET": "client_secret",
    "SHOPIFY_SCOPES": "read_products",
    "APP_URL": "https://example.com",
}

SHOP = "287c4a-bb.myshopify.com"

_SNAPSHOT = {
    "products": [
        {
            "id": "gid://shopify/Product/1",
            "title": "Test Product",
            "handle": "test-product",
            "description": "desc",
            "seo": {"title": "", "description": ""},  # missing meta title → issue
            "images": {"edges": [{"node": {"id": "img1", "altText": None, "url": "x.jpg"}}]},
            "collections": [],
        }
    ],
    "collections": [],
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


def test_get_issues_returns_list(client: TestClient, snapshot_file: Path):
    with (
        patch("app.api.deps.get_token", return_value=None),
        patch("app.api.deps._SNAPSHOT_DEFAULT", snapshot_file),
    ):
        resp = client.get(f"/api/shops/{SHOP}/audit/issues")
    assert resp.status_code == 200
    issues = resp.json()
    assert isinstance(issues, list)
    assert len(issues) > 0
    assert "issue_type" in issues[0]


def test_get_issues_detects_missing_meta_title(client: TestClient, snapshot_file: Path):
    with (
        patch("app.api.deps.get_token", return_value=None),
        patch("app.api.deps._SNAPSHOT_DEFAULT", snapshot_file),
    ):
        resp = client.get(f"/api/shops/{SHOP}/audit/issues")
    types = [i["issue_type"] for i in resp.json()]
    assert "missing_meta_title" in types


def test_get_issues_detects_missing_alt_text(client: TestClient, snapshot_file: Path):
    with (
        patch("app.api.deps.get_token", return_value=None),
        patch("app.api.deps._SNAPSHOT_DEFAULT", snapshot_file),
    ):
        resp = client.get(f"/api/shops/{SHOP}/audit/issues")
    types = [i["issue_type"] for i in resp.json()]
    assert "missing_alt_text" in types


def test_get_issues_severity_filter(client: TestClient, snapshot_file: Path):
    with (
        patch("app.api.deps.get_token", return_value=None),
        patch("app.api.deps._SNAPSHOT_DEFAULT", snapshot_file),
    ):
        resp = client.get(f"/api/shops/{SHOP}/audit/issues?severity=critical")
    for issue in resp.json():
        assert issue["severity"] == "critical"


def test_get_issues_resource_type_filter(client: TestClient, snapshot_file: Path):
    with (
        patch("app.api.deps.get_token", return_value=None),
        patch("app.api.deps._SNAPSHOT_DEFAULT", snapshot_file),
    ):
        resp = client.get(f"/api/shops/{SHOP}/audit/issues?resource_type=product")
    assert resp.status_code == 200
    for issue in resp.json():
        assert issue["resource_type"] == "product"


def test_get_issues_no_snapshot_returns_404(client: TestClient, tmp_path: Path):
    with (
        patch("app.api.deps.get_token", return_value=None),
        patch("app.api.deps._SNAPSHOT_DEFAULT", tmp_path / "missing.json"),
    ):
        resp = client.get(f"/api/shops/{SHOP}/audit/issues")
    assert resp.status_code == 404


def test_get_score_returns_float(client: TestClient, snapshot_file: Path):
    with (
        patch("app.api.deps.get_token", return_value=None),
        patch("app.api.deps._SNAPSHOT_DEFAULT", snapshot_file),
    ):
        resp = client.get(f"/api/shops/{SHOP}/audit/score")
    assert resp.status_code == 200
    body = resp.json()
    assert "total" in body
    assert 0 <= body["total"] <= 100
    assert "components" in body


def test_get_score_no_snapshot_returns_404(client: TestClient, tmp_path: Path):
    with (
        patch("app.api.deps.get_token", return_value=None),
        patch("app.api.deps._SNAPSHOT_DEFAULT", tmp_path / "missing.json"),
    ):
        resp = client.get(f"/api/shops/{SHOP}/audit/score")
    assert resp.status_code == 404


def test_get_issues_falls_back_to_db_snapshot(client: TestClient, tmp_path: Path):
    db = tmp_path / "history.db"
    init_db(db)
    product = _SNAPSHOT["products"][0]
    with sqlite3.connect(db) as conn:
        conn.execute(
            """
            INSERT INTO snapshots
                (shop, snapshot_date, resource_type, resource_id, data_json)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                SHOP,
                "2026-05-14T12:00:00Z",
                "product",
                product["id"],
                json.dumps(product),
            ),
        )

    with (
        patch("app.api.deps.get_token", return_value=None),
        patch("app.api.deps._SNAPSHOT_DEFAULT", tmp_path / "missing.json"),
        patch("app.api.snapshot_store.DB_PATH", db),
    ):
        resp = client.get(f"/api/shops/{SHOP}/audit/issues")

    assert resp.status_code == 200
    assert any(issue["issue_type"] == "missing_meta_title" for issue in resp.json())


def test_get_issues_unknown_shop_returns_403(client: TestClient):
    with patch("app.api.deps.get_token", return_value=None):
        resp = client.get("/api/shops/unknown.myshopify.com/audit/issues")
    assert resp.status_code == 403


def test_get_issues_rejects_internal_shop_mismatch(client: TestClient):
    headers = {
        "X-Leonie-Shop": "other.myshopify.com",
        "X-Internal-Secret": "test-internal-secret",
    }
    with patch.dict("os.environ", {"INTERNAL_API_SECRET": "test-internal-secret"}):
        resp = client.get(f"/api/shops/{SHOP}/audit/issues", headers=headers)
    assert resp.status_code == 403
