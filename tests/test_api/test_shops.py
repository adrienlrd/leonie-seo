"""Tests for shop management endpoints."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import app

ENV = {
    "SHOPIFY_STORE_DOMAIN": "287c4a-bb.myshopify.com",
    "SHOPIFY_ACCESS_TOKEN": "shpat_test",
    "SHOPIFY_CLIENT_ID": "client_id",
    "SHOPIFY_CLIENT_SECRET": "client_secret",
    "SHOPIFY_SCOPES": "read_products",
    "APP_URL": "https://example.com",
}


@pytest.fixture()
def client():
    with patch.dict("os.environ", ENV):
        yield TestClient(app)


def test_list_shops_empty(client: TestClient, mocker):
    mocker.patch("app.api.shops.list_tokens", return_value=[])
    resp = client.get("/api/shops")
    assert resp.status_code == 200
    assert resp.json() == []


def test_list_shops_with_installs(client: TestClient, mocker):
    mocker.patch(
        "app.api.shops.list_tokens",
        return_value=[{"shop": "test.myshopify.com", "scope": "read_products"}],
    )
    resp = client.get("/api/shops")
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
