"""Tests for product description rewrite endpoint."""

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
            "title": "Le Harnais Haute Couture pour Chien",
            "handle": "harnais-chien",
            "description": "<p>Un manteau.</p>",
            "seo": {"title": None, "description": None},
            "images": {"edges": []},
        },
        {
            "id": "gid://shopify/Product/2",
            "title": "Fontaine Chat Silencieuse",
            "handle": "fontaine-chat",
            "description": "",
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


def test_descriptions_returns_suggestions(client, snapshot_file) -> None:
    with (
        patch("app.api.deps.get_token", return_value=None),
        patch("app.api.deps._SNAPSHOT_DEFAULT", snapshot_file),
    ):
        resp = client.get(f"/api/shops/{SHOP}/audit/descriptions")

    assert resp.status_code == 200
    data = resp.json()
    assert data["available"] is True
    assert data["total"] == 2
    row = data["rows"][0]
    assert "product_id" in row
    assert "title" in row
    assert "category" in row
    assert "old_description" in row
    assert "suggested_description" in row
    assert "word_count" in row
    assert "quality_ok" in row


def test_descriptions_classifies_correctly(client, snapshot_file) -> None:
    with (
        patch("app.api.deps.get_token", return_value=None),
        patch("app.api.deps._SNAPSHOT_DEFAULT", snapshot_file),
    ):
        resp = client.get(f"/api/shops/{SHOP}/audit/descriptions")

    rows = {r["title"]: r for r in resp.json()["rows"]}
    assert rows["Le Harnais Haute Couture pour Chien"]["category"] == "vetements_chien"
    assert rows["Fontaine Chat Silencieuse"]["category"] == "fontaines"


def test_descriptions_word_count_in_range(client, snapshot_file) -> None:
    with (
        patch("app.api.deps.get_token", return_value=None),
        patch("app.api.deps._SNAPSHOT_DEFAULT", snapshot_file),
    ):
        resp = client.get(f"/api/shops/{SHOP}/audit/descriptions")

    for row in resp.json()["rows"]:
        assert row["word_count"] >= 50
        assert row["quality_ok"] is True


def test_descriptions_no_snapshot_returns_404(client, tmp_path) -> None:
    with (
        patch("app.api.deps.get_token", return_value=None),
        patch("app.api.deps._SNAPSHOT_DEFAULT", tmp_path / "missing.json"),
    ):
        resp = client.get(f"/api/shops/{SHOP}/audit/descriptions")

    assert resp.status_code == 404


def test_descriptions_apply_dry_run(client, snapshot_file) -> None:
    long_enough = " ".join(["mot"] * 60)
    payload = {
        "items": [
            {
                "product_id": "gid://shopify/Product/1",
                "description": long_enough,
            }
        ],
        "dry_run": True,
    }
    with (
        patch("app.api.deps.get_token", return_value=None),
        patch("app.api.deps._SNAPSHOT_DEFAULT", snapshot_file),
    ):
        resp = client.post(f"/api/shops/{SHOP}/audit/descriptions/apply", json=payload)

    assert resp.status_code == 200
    data = resp.json()
    assert data["dry_run"] is True
    assert data["results"][0]["status"] == "preview"


def test_descriptions_apply_rejects_too_short(client, snapshot_file) -> None:
    payload = {
        "items": [
            {
                "product_id": "gid://shopify/Product/1",
                "description": "Trop court.",
            }
        ],
        "dry_run": True,
    }
    with (
        patch("app.api.deps.get_token", return_value=None),
        patch("app.api.deps._SNAPSHOT_DEFAULT", snapshot_file),
    ):
        resp = client.post(f"/api/shops/{SHOP}/audit/descriptions/apply", json=payload)

    assert resp.status_code == 422


def test_descriptions_apply_live_calls_writer(client, snapshot_file) -> None:
    mock_result = MagicMock(applied=True, error=None)
    long_desc = " ".join(["mot"] * 80)
    payload = {
        "items": [{"product_id": "gid://shopify/Product/1", "description": long_desc}],
        "dry_run": False,
        "confirm_live_write": True,
    }
    with (
        patch("app.api.deps.get_token", return_value=None),
        patch("app.api.deps._SNAPSHOT_DEFAULT", snapshot_file),
        patch("app.api.descriptions.ShopifyWriter") as mock_cls,
    ):
        mock_cls.return_value.apply_product_description.return_value = mock_result
        resp = client.post(f"/api/shops/{SHOP}/audit/descriptions/apply", json=payload)

    assert resp.status_code == 200
    data = resp.json()
    assert data["dry_run"] is False
    assert data["applied"] == 1
    assert data["errors"] == 0
