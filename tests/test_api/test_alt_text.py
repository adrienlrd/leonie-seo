"""Tests for alt text generation and apply endpoint."""

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
        {
            "id": "gid://shopify/Product/1",
            "title": "Manteau Chien",
            "handle": "manteau-chien",
            "seo": {"title": None, "description": None},
            "images": {
                "edges": [
                    {
                        "node": {
                            "id": "gid://shopify/ProductImage/10",
                            "url": "https://cdn.shopify.com/img1.jpg",
                            "altText": None,
                        }
                    },
                    {
                        "node": {
                            "id": "gid://shopify/ProductImage/11",
                            "url": "https://cdn.shopify.com/img2.jpg",
                            "altText": "already set",
                        }
                    },
                ]
            },
        },
        {
            "id": "gid://shopify/Product/2",
            "title": "Collier Chat",
            "handle": "collier-chat",
            "seo": {"title": None, "description": None},
            "images": {"edges": []},
        },
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


def test_alt_text_returns_suggestions(client, snapshot_file) -> None:
    with (
        patch("app.api.deps.get_token", return_value=None),
        patch("app.api.deps._SNAPSHOT_DEFAULT", snapshot_file),
    ):
        resp = client.get(f"/api/shops/{SHOP}/audit/alt-text")

    assert resp.status_code == 200
    data = resp.json()
    assert data["available"] is True
    assert data["total"] == 1  # only img10 has no alt (img11 already set)
    row = data["rows"][0]
    assert row["image_id"] == "gid://shopify/ProductImage/10"
    assert row["product_name"] == "Manteau Chien"
    assert "suggested_alt" in row
    assert "char_count" in row
    assert "quality_ok" in row
    assert row["old_alt"] is None


def test_alt_text_excludes_images_with_existing_alt(client, snapshot_file) -> None:
    with (
        patch("app.api.deps.get_token", return_value=None),
        patch("app.api.deps._SNAPSHOT_DEFAULT", snapshot_file),
    ):
        resp = client.get(f"/api/shops/{SHOP}/audit/alt-text")

    image_ids = [r["image_id"] for r in resp.json()["rows"]]
    assert "gid://shopify/ProductImage/11" not in image_ids


def test_alt_text_suggestion_max_length(client, snapshot_file) -> None:
    with (
        patch("app.api.deps.get_token", return_value=None),
        patch("app.api.deps._SNAPSHOT_DEFAULT", snapshot_file),
    ):
        resp = client.get(f"/api/shops/{SHOP}/audit/alt-text")

    for row in resp.json()["rows"]:
        assert row["char_count"] <= 125


def test_alt_text_no_snapshot_returns_404(client, tmp_path) -> None:
    with (
        patch("app.api.deps.get_token", return_value=None),
        patch("app.api.deps._SNAPSHOT_DEFAULT", tmp_path / "missing.json"),
    ):
        resp = client.get(f"/api/shops/{SHOP}/audit/alt-text")

    assert resp.status_code == 404


def test_alt_text_apply_dry_run(client, snapshot_file) -> None:
    payload = {
        "items": [
            {
                "product_id": "gid://shopify/Product/1",
                "image_id": "gid://shopify/ProductImage/10",
                "alt_text": "Manteau chien hiver",
            }
        ],
        "dry_run": True,
    }
    with (
        patch("app.api.deps.get_token", return_value=None),
        patch("app.api.deps._SNAPSHOT_DEFAULT", snapshot_file),
    ):
        resp = client.post(f"/api/shops/{SHOP}/audit/alt-text/apply", json=payload)

    assert resp.status_code == 200
    data = resp.json()
    assert data["dry_run"] is True
    assert data["results"][0]["status"] == "preview"


def test_alt_text_apply_rejects_empty_alt(client, snapshot_file) -> None:
    payload = {
        "items": [
            {
                "product_id": "gid://shopify/Product/1",
                "image_id": "gid://shopify/ProductImage/10",
                "alt_text": "",
            }
        ],
        "dry_run": True,
    }
    with (
        patch("app.api.deps.get_token", return_value=None),
        patch("app.api.deps._SNAPSHOT_DEFAULT", snapshot_file),
    ):
        resp = client.post(f"/api/shops/{SHOP}/audit/alt-text/apply", json=payload)

    assert resp.status_code == 422


def test_alt_text_apply_live_calls_writer(client, snapshot_file) -> None:
    mock_result = MagicMock(applied=True, error=None)
    payload = {
        "items": [
            {
                "product_id": "gid://shopify/Product/1",
                "image_id": "gid://shopify/ProductImage/10",
                "alt_text": "Manteau chien hiver",
            }
        ],
        "dry_run": False,
        "confirm_live_write": True,
    }
    with (
        patch("app.api.deps.get_token", return_value=None),
        patch("app.api.deps._SNAPSHOT_DEFAULT", snapshot_file),
        patch("app.api.alt_text.ShopifyWriter") as mock_writer_cls,
    ):
        mock_writer_cls.return_value.apply_image_alt.return_value = mock_result
        resp = client.post(f"/api/shops/{SHOP}/audit/alt-text/apply", json=payload)

    assert resp.status_code == 200
    data = resp.json()
    assert data["dry_run"] is False
    assert data["applied"] == 1
    assert data["errors"] == 0
