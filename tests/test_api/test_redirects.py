"""Tests for URL redirect validate and apply endpoints."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

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
        {"id": "gid://shopify/Product/1", "handle": "manteau-chien", "title": "Manteau"}
    ],
    "collections": [],
}

_VALID_ITEMS = [
    {"from_path": "/old-page", "to_path": "/products/manteau-chien"},
    {"from_path": "/ancien-produit", "to_path": "/collections/chien"},
]


@pytest.fixture()
def client():
    with patch.dict("os.environ", ENV):
        yield TestClient(app)


@pytest.fixture()
def snapshot_file(tmp_path: Path) -> Path:
    p = tmp_path / "shopify_snapshot.json"
    p.write_text(json.dumps(_SNAPSHOT))
    return p


def test_validate_returns_valid_and_warnings(client, snapshot_file) -> None:
    items = _VALID_ITEMS + [{"from_path": "bad-path", "to_path": "/dest"}]  # missing /
    with (
        patch("app.api.deps.get_token", return_value=None),
        patch("app.api.deps._SNAPSHOT_DEFAULT", snapshot_file),
    ):
        resp = client.post(
            f"/api/shops/{SHOP}/audit/redirects/validate",
            json={"items": items},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["total_submitted"] == 3
    assert data["total_valid"] == 2
    assert data["total_skipped"] == 1
    assert len(data["warnings"]) == 1
    assert "bad-path" in data["warnings"][0]


def test_validate_detects_self_redirect(client, snapshot_file) -> None:
    with (
        patch("app.api.deps.get_token", return_value=None),
        patch("app.api.deps._SNAPSHOT_DEFAULT", snapshot_file),
    ):
        resp = client.post(
            f"/api/shops/{SHOP}/audit/redirects/validate",
            json={"items": [{"from_path": "/same", "to_path": "/same"}]},
        )

    data = resp.json()
    assert data["total_valid"] == 0
    assert any("self-redirect" in w for w in data["warnings"])


def test_validate_detects_duplicate_from(client, snapshot_file) -> None:
    items = [
        {"from_path": "/dup", "to_path": "/dest1"},
        {"from_path": "/dup", "to_path": "/dest2"},
    ]
    with (
        patch("app.api.deps.get_token", return_value=None),
        patch("app.api.deps._SNAPSHOT_DEFAULT", snapshot_file),
    ):
        resp = client.post(
            f"/api/shops/{SHOP}/audit/redirects/validate",
            json={"items": items},
        )

    data = resp.json()
    assert data["total_valid"] == 1  # first accepted, second skipped
    assert any("duplicate" in w for w in data["warnings"])


def test_validate_warns_on_live_handle(client, snapshot_file) -> None:
    with (
        patch("app.api.deps.get_token", return_value=None),
        patch("app.api.deps._SNAPSHOT_DEFAULT", snapshot_file),
    ):
        resp = client.post(
            f"/api/shops/{SHOP}/audit/redirects/validate",
            json={"items": [{"from_path": "/products/manteau-chien", "to_path": "/dest"}]},
        )

    data = resp.json()
    # Row is still valid but generates a warning
    assert data["total_valid"] == 1
    assert any("manteau-chien" in w for w in data["warnings"])


def test_apply_dry_run(client, snapshot_file) -> None:
    with (
        patch("app.api.deps.get_token", return_value=None),
        patch("app.api.deps._SNAPSHOT_DEFAULT", snapshot_file),
    ):
        resp = client.post(
            f"/api/shops/{SHOP}/audit/redirects/apply",
            json={"items": _VALID_ITEMS, "dry_run": True},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["dry_run"] is True
    assert len(data["results"]) == 2
    assert all(r["status"] == "preview" for r in data["results"])


def test_apply_live_calls_writer(client, snapshot_file) -> None:
    mock_result = MagicMock(applied=True, error=None)
    with (
        patch("app.api.deps.get_token", return_value=None),
        patch("app.api.deps._SNAPSHOT_DEFAULT", snapshot_file),
        patch("app.api.redirects.ShopifyWriter") as mock_cls,
    ):
        mock_cls.return_value.apply_redirect.return_value = mock_result
        resp = client.post(
            f"/api/shops/{SHOP}/audit/redirects/apply",
            json={"items": _VALID_ITEMS, "dry_run": False, "confirm_live_write": True},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["dry_run"] is False
    assert data["applied"] == 2
    assert data["errors"] == 0


def test_apply_empty_items_returns_422(client, snapshot_file) -> None:
    with (
        patch("app.api.deps.get_token", return_value=None),
        patch("app.api.deps._SNAPSHOT_DEFAULT", snapshot_file),
    ):
        resp = client.post(
            f"/api/shops/{SHOP}/audit/redirects/apply",
            json={"items": [], "dry_run": True},
        )

    assert resp.status_code == 422
