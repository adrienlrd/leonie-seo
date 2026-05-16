"""Tests for internal linking opportunities endpoint."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml
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
        },
        {
            "id": "gid://shopify/Product/2",
            "title": "Collier Chat",
            "handle": "collier-chat",
            "seo": {"title": None, "description": None},
            "images": {"edges": []},
        },
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
    "vetements_chien": ["manteau chien hiver", "vêtements chien luxe"],
    "accessoires_chat": ["collier chat cuir"],
    "brand": ["léonie"],
}

_GSC_CSV = """\
url,clicks,impressions,ctr,position
https://287c4a-bb.myshopify.com/products/manteau-chien,5,100,0.05,3.0
"""


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
    p = tmp_path / "keywords.yaml"
    p.write_text(yaml.dump(_KEYWORDS, allow_unicode=True))
    return p


@pytest.fixture()
def gsc_dir(tmp_path: Path) -> Path:
    shop_dir = tmp_path / SHOP
    shop_dir.mkdir(parents=True)
    (shop_dir / "gsc_performance.csv").write_text(_GSC_CSV, encoding="utf-8")
    return tmp_path


def test_internal_links_returns_opportunities(client, snapshot_file, keywords_file) -> None:
    with (
        patch("app.api.deps.get_token", return_value=None),
        patch("app.api.deps._SNAPSHOT_DEFAULT", snapshot_file),
        patch("app.api.internal_links._KEYWORDS_PATH", keywords_file),
        patch("app.api.internal_links._DATA_DIR", snapshot_file.parent),
    ):
        resp = client.get(f"/api/shops/{SHOP}/audit/internal-links")

    assert resp.status_code == 200
    data = resp.json()
    assert data["available"] is True
    assert data["total_opportunities"] > 0
    assert "opportunities" in data
    assert "orphans" in data
    row = data["opportunities"][0]
    assert "source_keyword" in row
    assert "target_url" in row
    assert "anchor_text" in row
    assert "relevance_score" in row


def test_internal_links_sorted_by_score(client, snapshot_file, keywords_file) -> None:
    with (
        patch("app.api.deps.get_token", return_value=None),
        patch("app.api.deps._SNAPSHOT_DEFAULT", snapshot_file),
        patch("app.api.internal_links._KEYWORDS_PATH", keywords_file),
        patch("app.api.internal_links._DATA_DIR", snapshot_file.parent),
    ):
        resp = client.get(f"/api/shops/{SHOP}/audit/internal-links")

    scores = [r["relevance_score"] for r in resp.json()["opportunities"]]
    assert scores == sorted(scores, reverse=True)


def test_internal_links_brand_excluded(client, snapshot_file, keywords_file) -> None:
    with (
        patch("app.api.deps.get_token", return_value=None),
        patch("app.api.deps._SNAPSHOT_DEFAULT", snapshot_file),
        patch("app.api.internal_links._KEYWORDS_PATH", keywords_file),
        patch("app.api.internal_links._DATA_DIR", snapshot_file.parent),
    ):
        resp = client.get(f"/api/shops/{SHOP}/audit/internal-links")

    keywords_used = [r["source_keyword"] for r in resp.json()["opportunities"]]
    assert "léonie" not in keywords_used


def test_internal_links_orphans_with_gsc(client, snapshot_file, keywords_file, gsc_dir) -> None:
    with (
        patch("app.api.deps.get_token", return_value=None),
        patch("app.api.deps._SNAPSHOT_DEFAULT", snapshot_file),
        patch("app.api.internal_links._KEYWORDS_PATH", keywords_file),
        patch("app.api.internal_links._DATA_DIR", gsc_dir),
    ):
        resp = client.get(f"/api/shops/{SHOP}/audit/internal-links")

    data = resp.json()
    assert data["gsc_connected"] is True
    # collier-chat has no impressions → orphan
    orphan_handles = [o["handle"] for o in data["orphans"]]
    assert "collier-chat" in orphan_handles
    assert "manteau-chien" not in orphan_handles


def test_internal_links_top_param(client, snapshot_file, keywords_file) -> None:
    with (
        patch("app.api.deps.get_token", return_value=None),
        patch("app.api.deps._SNAPSHOT_DEFAULT", snapshot_file),
        patch("app.api.internal_links._KEYWORDS_PATH", keywords_file),
        patch("app.api.internal_links._DATA_DIR", snapshot_file.parent),
    ):
        resp = client.get(f"/api/shops/{SHOP}/audit/internal-links?top=1")

    assert resp.status_code == 200
    assert len(resp.json()["opportunities"]) <= 1


def test_internal_links_no_snapshot_returns_404(client, tmp_path, keywords_file) -> None:
    with (
        patch("app.api.deps.get_token", return_value=None),
        patch("app.api.deps._SNAPSHOT_DEFAULT", tmp_path / "missing.json"),
        patch("app.api.internal_links._KEYWORDS_PATH", keywords_file),
        patch("app.api.internal_links._DATA_DIR", tmp_path),
    ):
        resp = client.get(f"/api/shops/{SHOP}/audit/internal-links")

    assert resp.status_code == 404


def test_internal_links_no_keywords_returns_404(client, snapshot_file, tmp_path) -> None:
    with (
        patch("app.api.deps.get_token", return_value=None),
        patch("app.api.deps._SNAPSHOT_DEFAULT", snapshot_file),
        patch("app.api.internal_links._KEYWORDS_PATH", tmp_path / "missing.yaml"),
        patch("app.api.internal_links._DATA_DIR", snapshot_file.parent),
    ):
        resp = client.get(f"/api/shops/{SHOP}/audit/internal-links")

    assert resp.status_code == 404
