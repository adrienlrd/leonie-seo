"""Tests for /api/shops/{shop}/jsonld/status endpoint."""

from __future__ import annotations

import json
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
            "title": "Manteau Chien",
            "handle": "manteau-chien",
            "description": "Un beau manteau pour chien",
            "images": {
                "edges": [{"node": {"url": "https://cdn.shopify.com/img1.jpg"}}]
            },
        },
        {
            "id": "gid://shopify/Product/2",
            "title": "Collier Chat",
            "handle": "collier-chat",
            "description": "",
            "images": {"edges": []},
        },
    ],
    "collections": [
        {
            "id": "gid://shopify/Collection/10",
            "title": "Chiens",
            "handle": "chiens",
            "description": "Tous nos produits pour chiens",
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


def test_jsonld_status_returns_organization(client, snapshot_file) -> None:
    with (
        patch("app.api.deps.get_token", return_value=None),
        patch("app.api.deps._SNAPSHOT_DEFAULT", snapshot_file),
        patch("app.api.jsonld.load_snapshot_from_file_or_db", return_value=_SNAPSHOT),
    ):
        resp = client.get(f"/api/shops/{SHOP}/jsonld/status")

    assert resp.status_code == 200
    data = resp.json()
    assert data["shop"] == SHOP
    orgs = [r for r in data["resources"] if r["resource_type"] == "organization"]
    assert len(orgs) == 1
    assert orgs[0]["valid"] is True
    assert orgs[0]["jsonld"]["@type"] == "Organization"


def test_jsonld_status_products_included(client, snapshot_file) -> None:
    with (
        patch("app.api.deps.get_token", return_value=None),
        patch("app.api.deps._SNAPSHOT_DEFAULT", snapshot_file),
        patch("app.api.jsonld.load_snapshot_from_file_or_db", return_value=_SNAPSHOT),
    ):
        resp = client.get(f"/api/shops/{SHOP}/jsonld/status")

    data = resp.json()
    products = [r for r in data["resources"] if r["resource_type"] == "product"]
    assert len(products) == 2
    handles = {p["handle"] for p in products}
    assert handles == {"manteau-chien", "collier-chat"}


def test_jsonld_status_collections_included(client, snapshot_file) -> None:
    with (
        patch("app.api.deps.get_token", return_value=None),
        patch("app.api.deps._SNAPSHOT_DEFAULT", snapshot_file),
        patch("app.api.jsonld.load_snapshot_from_file_or_db", return_value=_SNAPSHOT),
    ):
        resp = client.get(f"/api/shops/{SHOP}/jsonld/status")

    data = resp.json()
    collections = [r for r in data["resources"] if r["resource_type"] == "collection"]
    assert len(collections) == 1
    assert collections[0]["handle"] == "chiens"
    assert collections[0]["valid"] is True


def test_jsonld_status_valid_counts(client, snapshot_file) -> None:
    with (
        patch("app.api.deps.get_token", return_value=None),
        patch("app.api.deps._SNAPSHOT_DEFAULT", snapshot_file),
        patch("app.api.jsonld.load_snapshot_from_file_or_db", return_value=_SNAPSHOT),
    ):
        resp = client.get(f"/api/shops/{SHOP}/jsonld/status")

    data = resp.json()
    # 1 org + 2 products + 1 collection = 4 total, all valid (offers always generated)
    assert data["total"] == 4
    assert data["valid"] == 4
    assert data["invalid"] == 0


def test_jsonld_status_product_has_offers(client, snapshot_file) -> None:
    with (
        patch("app.api.deps.get_token", return_value=None),
        patch("app.api.deps._SNAPSHOT_DEFAULT", snapshot_file),
        patch("app.api.jsonld.load_snapshot_from_file_or_db", return_value=_SNAPSHOT),
    ):
        resp = client.get(f"/api/shops/{SHOP}/jsonld/status")

    data = resp.json()
    products = [r for r in data["resources"] if r["resource_type"] == "product"]
    for p in products:
        assert "offers" in p["jsonld"]
        assert p["jsonld"]["@type"] == "Product"
        assert p["valid"] is True


def test_jsonld_status_no_snapshot_still_returns_org(client, tmp_path) -> None:
    missing = tmp_path / "missing.json"
    with (
        patch("app.api.deps.get_token", return_value=None),
        patch("app.api.deps._SNAPSHOT_DEFAULT", missing),
        patch("app.api.jsonld.load_snapshot_from_file_or_db", return_value=None),
    ):
        resp = client.get(f"/api/shops/{SHOP}/jsonld/status")

    assert resp.status_code == 200
    data = resp.json()
    assert data["available"] is False
    orgs = [r for r in data["resources"] if r["resource_type"] == "organization"]
    assert len(orgs) == 1


def test_jsonld_status_extension_note_present(client, snapshot_file) -> None:
    with (
        patch("app.api.deps.get_token", return_value=None),
        patch("app.api.deps._SNAPSHOT_DEFAULT", snapshot_file),
        patch("app.api.jsonld.load_snapshot_from_file_or_db", return_value=_SNAPSHOT),
    ):
        resp = client.get(f"/api/shops/{SHOP}/jsonld/status")

    data = resp.json()
    assert "extension_note" in data
    assert "leonie-seo-jsonld" in data["extension_note"]
