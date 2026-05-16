"""Tests for ICE matrix API endpoint."""

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


def test_ice_returns_sorted_list(client: TestClient, snapshot_file: Path) -> None:
    with (
        patch("app.api.deps.get_token", return_value=None),
        patch("app.api.deps._SNAPSHOT_DEFAULT", snapshot_file),
        patch("app.api.ice._DATA_DIR", snapshot_file.parent),
    ):
        resp = client.get(f"/api/shops/{SHOP}/audit/ice")

    assert resp.status_code == 200
    rows = resp.json()
    assert isinstance(rows, list)
    assert len(rows) > 0
    scores = [r["ice_score"] for r in rows]
    assert scores == sorted(scores, reverse=True)
    assert "ice_score" in rows[0]
    assert "impact" in rows[0]
    assert "confidence" in rows[0]
    assert "effort" in rows[0]
    assert "issue_type" in rows[0]
    assert "resource_title" in rows[0]


def test_ice_respects_top_param(client: TestClient, snapshot_file: Path) -> None:
    with (
        patch("app.api.deps.get_token", return_value=None),
        patch("app.api.deps._SNAPSHOT_DEFAULT", snapshot_file),
        patch("app.api.ice._DATA_DIR", snapshot_file.parent),
    ):
        resp = client.get(f"/api/shops/{SHOP}/audit/ice?top=1")

    assert resp.status_code == 200
    assert len(resp.json()) <= 1


def test_ice_includes_crawl_issues(client: TestClient, snapshot_file: Path, tmp_path: Path) -> None:
    shop_dir = tmp_path / SHOP
    shop_dir.mkdir(parents=True, exist_ok=True)
    crawl_report = {
        "issues": [
            {
                "url": "https://example.com/missing",
                "issue_type": "page_404",
                "severity": "critical",
                "detail": "Page returns 404.",
            }
        ]
    }
    (shop_dir / "crawl_report.json").write_text(json.dumps(crawl_report), encoding="utf-8")
    with (
        patch("app.api.deps.get_token", return_value=None),
        patch("app.api.deps._SNAPSHOT_DEFAULT", snapshot_file),
        patch("app.api.ice._DATA_DIR", tmp_path),
    ):
        resp = client.get(f"/api/shops/{SHOP}/audit/ice")

    assert resp.status_code == 200
    issue_types = [r["issue_type"] for r in resp.json()]
    assert "page_404" in issue_types


def test_ice_no_snapshot_returns_404(client: TestClient, tmp_path: Path) -> None:
    with (
        patch("app.api.deps.get_token", return_value=None),
        patch("app.api.deps._SNAPSHOT_DEFAULT", tmp_path / "missing.json"),
        patch("app.api.ice._DATA_DIR", tmp_path),
    ):
        resp = client.get(f"/api/shops/{SHOP}/audit/ice")

    assert resp.status_code == 404
