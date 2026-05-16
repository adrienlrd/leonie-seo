"""Tests for keyword cannibalization detection endpoint."""

from __future__ import annotations

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

_GSC_QUERY_PAGE_CSV = """\
query,url,clicks,impressions,ctr,position
manteau chien,https://example.com/products/manteau-chien,5,120,0.04,3.2
manteau chien,https://example.com/collections/vetements-chien,2,120,0.02,8.5
collier chat,https://example.com/products/collier-chat,10,200,0.05,2.1
"""


@pytest.fixture()
def client():
    with patch.dict("os.environ", ENV):
        yield TestClient(app)


@pytest.fixture()
def gsc_file(tmp_path: Path) -> Path:
    shop_dir = tmp_path / SHOP
    shop_dir.mkdir(parents=True)
    p = shop_dir / "gsc_query_page.csv"
    p.write_text(_GSC_QUERY_PAGE_CSV, encoding="utf-8")
    return tmp_path


def test_cannibalization_returns_pairs(client, gsc_file) -> None:
    with (
        patch("app.api.deps.get_token", return_value=None),
        patch("app.api.cannibalization._DATA_DIR", gsc_file),
    ):
        resp = client.get(f"/api/shops/{SHOP}/audit/cannibalization")

    assert resp.status_code == 200
    data = resp.json()
    assert data["available"] is True
    assert data["total"] == 1  # only "manteau chien" has 2 pages
    assert len(data["rows"]) == 1
    row = data["rows"][0]
    assert row["query"] == "manteau chien"
    assert "recommendation" in row
    assert "severity" in row


def test_cannibalization_sorted_by_severity(client, gsc_file) -> None:
    with (
        patch("app.api.deps.get_token", return_value=None),
        patch("app.api.cannibalization._DATA_DIR", gsc_file),
    ):
        resp = client.get(f"/api/shops/{SHOP}/audit/cannibalization")

    rows = resp.json()["rows"]
    severities = [r["severity"] for r in rows]
    assert severities == sorted(severities, reverse=True)


def test_cannibalization_no_gsc_returns_available_false(client, tmp_path) -> None:
    with (
        patch("app.api.deps.get_token", return_value=None),
        patch("app.api.cannibalization._DATA_DIR", tmp_path),
    ):
        resp = client.get(f"/api/shops/{SHOP}/audit/cannibalization")

    assert resp.status_code == 200
    data = resp.json()
    assert data["available"] is False
    assert data["total"] == 0
    assert "message" in data


def test_cannibalization_summary_counts(client, gsc_file) -> None:
    with (
        patch("app.api.deps.get_token", return_value=None),
        patch("app.api.cannibalization._DATA_DIR", gsc_file),
    ):
        resp = client.get(f"/api/shops/{SHOP}/audit/cannibalization")

    summary = resp.json()["summary"]
    assert "high" in summary
    assert "medium" in summary
    assert "low" in summary
    assert summary["high"] + summary["medium"] + summary["low"] == resp.json()["total"]
