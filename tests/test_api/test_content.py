"""Tests for FAQ and blog brief content generation endpoints."""

from __future__ import annotations

import csv
import io
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
            "title": "Harnais Chien Cuir",
            "handle": "harnais-chien-cuir",
            "seo": {"title": None, "description": None},
            "images": {"edges": []},
        },
        {
            "id": "gid://shopify/Product/2",
            "title": "Collier Chat Luxe",
            "handle": "collier-chat-luxe",
            "seo": {"title": None, "description": None},
            "images": {"edges": []},
        },
    ],
    "collections": [],
}

_GSC_ROWS = [
    {"query": "comment choisir harnais chien", "impressions": "120", "clicks": "5", "position": "12"},
    {"query": "meilleur harnais pour chien", "impressions": "80", "clicks": "3", "position": "14"},
    {"query": "pourquoi mettre un harnais chien", "impressions": "45", "clicks": "2", "position": "18"},
    {"query": "harnais chien cuir", "impressions": "200", "clicks": "12", "position": "5"},  # not informational
    {"query": "guide collier chat", "impressions": "30", "clicks": "1", "position": "22"},
]


def _make_gsc_csv(rows: list[dict]) -> str:
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=["query", "impressions", "clicks", "position"])
    writer.writeheader()
    writer.writerows(rows)
    return out.getvalue()


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
def gsc_csv(tmp_path: Path) -> Path:
    shop_dir = tmp_path / SHOP
    shop_dir.mkdir(parents=True)
    p = shop_dir / "gsc_performance.csv"
    p.write_text(_make_gsc_csv(_GSC_ROWS))
    return tmp_path


# ---------------------------------------------------------------------------
# FAQ
# ---------------------------------------------------------------------------


def test_faq_returns_per_product(client, snapshot_file) -> None:
    with (
        patch("app.api.deps.get_token", return_value=None),
        patch("app.api.deps._SNAPSHOT_DEFAULT", snapshot_file),
        patch("app.api.content.load_snapshot_from_file_or_db", return_value=_SNAPSHOT),
    ):
        resp = client.get(f"/api/shops/{SHOP}/content/faq")

    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    assert len(data["items"]) == 2


def test_faq_contains_questions_and_answers(client, snapshot_file) -> None:
    with (
        patch("app.api.deps.get_token", return_value=None),
        patch("app.api.deps._SNAPSHOT_DEFAULT", snapshot_file),
        patch("app.api.content.load_snapshot_from_file_or_db", return_value=_SNAPSHOT),
    ):
        resp = client.get(f"/api/shops/{SHOP}/content/faq")

    item = resp.json()["items"][0]
    assert item["faq_count"] == 5  # 5 templates
    for entry in item["faq"]:
        assert "q" in entry
        assert "a" in entry
        assert len(entry["q"]) > 0
        assert len(entry["a"]) > 0


def test_faq_title_interpolated(client, snapshot_file) -> None:
    with (
        patch("app.api.deps.get_token", return_value=None),
        patch("app.api.deps._SNAPSHOT_DEFAULT", snapshot_file),
        patch("app.api.content.load_snapshot_from_file_or_db", return_value=_SNAPSHOT),
    ):
        resp = client.get(f"/api/shops/{SHOP}/content/faq")

    item = next(i for i in resp.json()["items"] if i["handle"] == "harnais-chien-cuir")
    assert "Harnais Chien Cuir" in item["faq"][0]["q"]


def test_faq_jsonld_structure(client, snapshot_file) -> None:
    with (
        patch("app.api.deps.get_token", return_value=None),
        patch("app.api.deps._SNAPSHOT_DEFAULT", snapshot_file),
        patch("app.api.content.load_snapshot_from_file_or_db", return_value=_SNAPSHOT),
    ):
        resp = client.get(f"/api/shops/{SHOP}/content/faq")

    item = resp.json()["items"][0]
    jsonld = item["jsonld"]
    assert jsonld["@type"] == "FAQPage"
    assert len(jsonld["mainEntity"]) == 5
    assert jsonld["mainEntity"][0]["@type"] == "Question"
    assert "acceptedAnswer" in jsonld["mainEntity"][0]


def test_faq_no_snapshot_returns_404(client, tmp_path) -> None:
    with (
        patch("app.api.deps.get_token", return_value=None),
        patch("app.api.deps._SNAPSHOT_DEFAULT", tmp_path / "missing.json"),
        patch("app.api.content.load_snapshot_from_file_or_db", return_value=None),
    ):
        resp = client.get(f"/api/shops/{SHOP}/content/faq")

    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Blog briefs
# ---------------------------------------------------------------------------


def test_briefs_filters_informational(client, snapshot_file, gsc_csv) -> None:
    with (
        patch("app.api.deps.get_token", return_value=None),
        patch("app.api.deps._SNAPSHOT_DEFAULT", snapshot_file),
        patch("app.api.content.load_snapshot_from_file_or_db", return_value=_SNAPSHOT),
        patch("app.api.content._DATA_DIR", gsc_csv),
    ):
        resp = client.get(f"/api/shops/{SHOP}/content/briefs?min_impressions=10")

    assert resp.status_code == 200
    data = resp.json()
    keywords = [b["target_keyword"] for b in data["briefs"]]
    # "harnais chien cuir" is NOT informational → should not appear
    assert "harnais chien cuir" not in keywords
    # Question words → should appear
    assert any("comment" in k or "meilleur" in k or "pourquoi" in k or "guide" in k for k in keywords)


def test_briefs_structure(client, snapshot_file, gsc_csv) -> None:
    with (
        patch("app.api.deps.get_token", return_value=None),
        patch("app.api.deps._SNAPSHOT_DEFAULT", snapshot_file),
        patch("app.api.content.load_snapshot_from_file_or_db", return_value=_SNAPSHOT),
        patch("app.api.content._DATA_DIR", gsc_csv),
    ):
        resp = client.get(f"/api/shops/{SHOP}/content/briefs")

    for brief in resp.json()["briefs"]:
        assert "target_keyword" in brief
        assert "suggested_title" in brief
        assert "h2_sections" in brief
        assert len(brief["h2_sections"]) == 5
        assert "word_count_target" in brief
        assert brief["word_count_target"] > 0
        assert "internal_links" in brief


def test_briefs_sorted_by_impressions(client, snapshot_file, gsc_csv) -> None:
    with (
        patch("app.api.deps.get_token", return_value=None),
        patch("app.api.deps._SNAPSHOT_DEFAULT", snapshot_file),
        patch("app.api.content.load_snapshot_from_file_or_db", return_value=_SNAPSHOT),
        patch("app.api.content._DATA_DIR", gsc_csv),
    ):
        resp = client.get(f"/api/shops/{SHOP}/content/briefs")

    impressions = [b["impressions"] for b in resp.json()["briefs"]]
    assert impressions == sorted(impressions, reverse=True)


def test_briefs_no_gsc_returns_empty(client, snapshot_file, tmp_path) -> None:
    with (
        patch("app.api.deps.get_token", return_value=None),
        patch("app.api.deps._SNAPSHOT_DEFAULT", snapshot_file),
        patch("app.api.content.load_snapshot_from_file_or_db", return_value=_SNAPSHOT),
        patch("app.api.content._DATA_DIR", tmp_path / "empty"),
    ):
        resp = client.get(f"/api/shops/{SHOP}/content/briefs")

    data = resp.json()
    assert resp.status_code == 200
    assert data["gsc_connected"] is False
    assert data["total"] == 0


def test_briefs_internal_links_from_snapshot(client, snapshot_file, gsc_csv) -> None:
    with (
        patch("app.api.deps.get_token", return_value=None),
        patch("app.api.deps._SNAPSHOT_DEFAULT", snapshot_file),
        patch("app.api.content.load_snapshot_from_file_or_db", return_value=_SNAPSHOT),
        patch("app.api.content._DATA_DIR", gsc_csv),
    ):
        resp = client.get(f"/api/shops/{SHOP}/content/briefs")

    # "comment choisir harnais chien" → harnais-chien-cuir product should match
    briefs = resp.json()["briefs"]
    harnais_brief = next((b for b in briefs if "harnais" in b["target_keyword"]), None)
    if harnais_brief:
        paths = [lk["path"] for lk in harnais_brief["internal_links"]]
        assert any("harnais" in p for p in paths)
