"""Tests for long-tail keyword coverage endpoint."""

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
            "seo": {"title": None, "description": None},
            "images": {"edges": []},
        }
    ],
    "collections": [
        {
            "id": "gid://shopify/Collection/1",
            "title": "Vêtements Chien",
            "handle": "vetements-chien",
            "seo": {"title": None, "description": None},
        }
    ],
}

_KEYWORDS = {
    "vetements_chien": ["manteau pour chien luxe", "vêtements chien premium"],
    "gap_category": ["fontaine chat silencieuse"],
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
def keywords_file(tmp_path: Path) -> Path:
    import yaml
    p = tmp_path / "keywords.yaml"
    p.write_text(yaml.dump(_KEYWORDS, allow_unicode=True))
    return p


def test_longtail_returns_summary(client, snapshot_file, keywords_file) -> None:
    with (
        patch("app.api.deps.get_token", return_value=None),
        patch("app.api.deps._SNAPSHOT_DEFAULT", snapshot_file),
        patch("app.api.longtail._KEYWORDS_PATH", keywords_file),
        patch("app.api.longtail._DATA_DIR", snapshot_file.parent),
    ):
        resp = client.get(f"/api/shops/{SHOP}/audit/longtail")

    assert resp.status_code == 200
    data = resp.json()
    assert data["available"] is True
    assert data["total"] == 3
    assert "ranking" in data["summary"]
    assert "on_site" in data["summary"]
    assert "gap" in data["summary"]
    assert data["summary"]["ranking"] + data["summary"]["on_site"] + data["summary"]["gap"] == 3


def test_longtail_rows_sorted_by_status(client, snapshot_file, keywords_file) -> None:
    with (
        patch("app.api.deps.get_token", return_value=None),
        patch("app.api.deps._SNAPSHOT_DEFAULT", snapshot_file),
        patch("app.api.longtail._KEYWORDS_PATH", keywords_file),
        patch("app.api.longtail._DATA_DIR", snapshot_file.parent),
    ):
        resp = client.get(f"/api/shops/{SHOP}/audit/longtail")

    rows = resp.json()["rows"]
    assert len(rows) > 0
    for row in rows:
        assert row["status"] in ("ranking", "on_site", "gap")
        assert "keyword" in row
        assert "recommendation" in row
        assert "opportunity_score" in row


def test_longtail_no_snapshot_returns_404(client, tmp_path, keywords_file) -> None:
    with (
        patch("app.api.deps.get_token", return_value=None),
        patch("app.api.deps._SNAPSHOT_DEFAULT", tmp_path / "missing.json"),
        patch("app.api.longtail._KEYWORDS_PATH", keywords_file),
        patch("app.api.longtail._DATA_DIR", tmp_path),
    ):
        resp = client.get(f"/api/shops/{SHOP}/audit/longtail")

    assert resp.status_code == 404


def test_longtail_no_keywords_returns_404(client, snapshot_file, tmp_path) -> None:
    with (
        patch("app.api.deps.get_token", return_value=None),
        patch("app.api.deps._SNAPSHOT_DEFAULT", snapshot_file),
        patch("app.api.longtail._KEYWORDS_PATH", tmp_path / "missing.yaml"),
        patch("app.api.longtail._DATA_DIR", snapshot_file.parent),
    ):
        resp = client.get(f"/api/shops/{SHOP}/audit/longtail")

    assert resp.status_code == 404


def test_longtail_top_param(client, snapshot_file, keywords_file) -> None:
    with (
        patch("app.api.deps.get_token", return_value=None),
        patch("app.api.deps._SNAPSHOT_DEFAULT", snapshot_file),
        patch("app.api.longtail._KEYWORDS_PATH", keywords_file),
        patch("app.api.longtail._DATA_DIR", snapshot_file.parent),
    ):
        resp = client.get(f"/api/shops/{SHOP}/audit/longtail?top=1")

    assert resp.status_code == 200
    assert len(resp.json()["rows"]) <= 1
