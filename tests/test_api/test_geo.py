"""Tests for GEO product facts endpoint."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.db import init_db
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
            "title": "Harnais chien nylon",
            "handle": "harnais-chien",
            "description": "Harnais en nylon réglable, lavable, fabriqué en France. Garantie 30 jours.",
            "variants": {"edges": [{"node": {"price": "49.90"}}]},
        },
        {
            "id": "gid://shopify/Product/2",
            "title": "Bol chat",
            "handle": "bol-chat",
            "description": "Bol chat design.",
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
    path = tmp_path / "shopify_snapshot.json"
    path.write_text(json.dumps(_SNAPSHOT), encoding="utf-8")
    return path


def test_get_geo_facts_returns_product_facts_when_snapshot_exists(client, snapshot_file) -> None:
    with (
        patch("app.api.deps.get_token", return_value=None),
        patch("app.api.deps._SNAPSHOT_DEFAULT", snapshot_file),
        patch("app.api.geo.load_snapshot_from_file_or_db", return_value=_SNAPSHOT),
    ):
        resp = client.get(f"/api/shops/{SHOP}/geo/facts")

    assert resp.status_code == 200
    data = resp.json()
    assert data["available"] is True
    assert data["total"] == 2
    assert "avg_completeness_score" in data["summary"]
    assert data["products"][0]["confirmed_facts"]


def test_get_geo_facts_respects_top_parameter_when_requested(client, snapshot_file) -> None:
    with (
        patch("app.api.deps.get_token", return_value=None),
        patch("app.api.deps._SNAPSHOT_DEFAULT", snapshot_file),
        patch("app.api.geo.load_snapshot_from_file_or_db", return_value=_SNAPSHOT),
    ):
        resp = client.get(f"/api/shops/{SHOP}/geo/facts?top=1")

    assert resp.status_code == 200
    assert len(resp.json()["products"]) == 1


def test_get_geo_facts_returns_404_when_snapshot_is_missing(client, tmp_path) -> None:
    with (
        patch("app.api.deps.get_token", return_value=None),
        patch("app.api.deps._SNAPSHOT_DEFAULT", tmp_path / "missing.json"),
        patch("app.api.geo.load_snapshot_from_file_or_db", return_value=None),
    ):
        resp = client.get(f"/api/shops/{SHOP}/geo/facts")

    assert resp.status_code == 404


def test_get_geo_readiness_returns_scores_when_snapshot_exists(client, snapshot_file) -> None:
    with (
        patch("app.api.deps.get_token", return_value=None),
        patch("app.api.deps._SNAPSHOT_DEFAULT", snapshot_file),
        patch("app.api.geo.load_snapshot_from_file_or_db", return_value=_SNAPSHOT),
    ):
        resp = client.get(f"/api/shops/{SHOP}/geo/readiness")

    assert resp.status_code == 200
    data = resp.json()
    assert data["available"] is True
    assert data["total"] == 2
    assert "avg_readiness_score" in data["summary"]
    assert "components" in data["products"][0]


def test_get_geo_readiness_respects_top_parameter(client, snapshot_file) -> None:
    with (
        patch("app.api.deps.get_token", return_value=None),
        patch("app.api.deps._SNAPSHOT_DEFAULT", snapshot_file),
        patch("app.api.geo.load_snapshot_from_file_or_db", return_value=_SNAPSHOT),
    ):
        resp = client.get(f"/api/shops/{SHOP}/geo/readiness?top=1")

    assert resp.status_code == 200
    assert len(resp.json()["products"]) == 1


def test_get_geo_priorities_returns_revenue_aware_rows(client, snapshot_file, tmp_path) -> None:
    gsc_dir = tmp_path / SHOP
    gsc_dir.mkdir()
    gsc_path = gsc_dir / "gsc_performance.csv"
    gsc_path.write_text(
        "url,clicks,impressions,ctr,position\n"
        "https://example.com/products/harnais-chien,20,1000,0.02,12\n",
        encoding="utf-8",
    )

    with (
        patch("app.api.deps.get_token", return_value=None),
        patch("app.api.deps._SNAPSHOT_DEFAULT", snapshot_file),
        patch("app.api.geo.load_snapshot_from_file_or_db", return_value={**_SNAPSHOT, "shop": {"domain": "example.com"}}),
        patch("app.api.geo._find_gsc_file", return_value=gsc_path),
    ):
        resp = client.get(f"/api/shops/{SHOP}/geo/priorities?top=1&conversion_rate=0.05")

    assert resp.status_code == 200
    data = resp.json()
    assert data["available"] is True
    assert data["summary"]["gsc_connected"] is True
    assert len(data["rows"]) == 1
    assert "revenue_estimate" in data["rows"][0]


def test_get_geo_priorities_works_without_gsc(client, snapshot_file) -> None:
    with (
        patch("app.api.deps.get_token", return_value=None),
        patch("app.api.deps._SNAPSHOT_DEFAULT", snapshot_file),
        patch("app.api.geo.load_snapshot_from_file_or_db", return_value=_SNAPSHOT),
        patch("app.api.geo._find_gsc_file", return_value=None),
    ):
        resp = client.get(f"/api/shops/{SHOP}/geo/priorities")

    assert resp.status_code == 200
    assert resp.json()["summary"]["gsc_connected"] is False


def test_get_geo_weekly_actions_returns_action_cards(client, snapshot_file, tmp_path) -> None:
    gsc_dir = tmp_path / SHOP
    gsc_dir.mkdir()
    gsc_path = gsc_dir / "gsc_performance.csv"
    gsc_path.write_text(
        "url,clicks,impressions,ctr,position\n"
        "https://example.com/products/harnais-chien,20,1000,0.02,12\n"
        "https://example.com/products/bol-chat,5,500,0.01,15\n",
        encoding="utf-8",
    )

    with (
        patch("app.api.deps.get_token", return_value=None),
        patch("app.api.deps._SNAPSHOT_DEFAULT", snapshot_file),
        patch("app.api.geo.load_snapshot_from_file_or_db", return_value={**_SNAPSHOT, "shop": {"domain": "example.com"}}),
        patch("app.api.geo._find_gsc_file", return_value=gsc_path),
    ):
        resp = client.get(f"/api/shops/{SHOP}/geo/weekly-actions")

    assert resp.status_code == 200
    data = resp.json()
    assert data["available"] is True
    assert data["summary"]["weekly_actions"] == 2
    assert data["actions"][0]["weekly_message"]
    assert data["actions"][0]["next_steps"]


def test_get_geo_weekly_actions_respects_limit(client, snapshot_file) -> None:
    with (
        patch("app.api.deps.get_token", return_value=None),
        patch("app.api.deps._SNAPSHOT_DEFAULT", snapshot_file),
        patch("app.api.geo.load_snapshot_from_file_or_db", return_value=_SNAPSHOT),
        patch("app.api.geo._find_gsc_file", return_value=None),
    ):
        resp = client.get(f"/api/shops/{SHOP}/geo/weekly-actions?limit=1")

    assert resp.status_code == 200
    assert len(resp.json()["actions"]) == 1


def test_create_geo_ledger_event_and_list_it(client, tmp_path) -> None:
    db = tmp_path / "ledger.db"
    init_db(db)
    payload = {
        "resource_type": "product",
        "resource_id": "gid://shopify/Product/1",
        "resource_title": "Harnais",
        "action_type": "enrich_product_facts",
        "before_snapshot": {"readiness_score": 40},
        "metrics_before": {"impressions": 100},
        "estimated_impact": {"revenue_estimate": 12.5},
        "hypothesis": "Facts should improve answerability.",
    }

    with (
        patch("app.api.deps.get_token", return_value=None),
        patch("app.api.geo.DB_PATH", db),
    ):
        created = client.post(f"/api/shops/{SHOP}/geo/ledger/events", json=payload)
        listed = client.get(f"/api/shops/{SHOP}/geo/ledger")

    assert created.status_code == 200
    assert created.json()["created"] is True
    assert listed.status_code == 200
    data = listed.json()
    assert data["total"] == 1
    assert data["summary"]["estimated_revenue"] == 12.5
    assert data["events"][0]["hypothesis"] == "Facts should improve answerability."


def test_geo_ledger_status_filter(client, tmp_path) -> None:
    db = tmp_path / "ledger.db"
    init_db(db)
    with (
        patch("app.api.deps.get_token", return_value=None),
        patch("app.api.geo.DB_PATH", db),
    ):
        client.post(
            f"/api/shops/{SHOP}/geo/ledger/events",
            json={
                "resource_type": "product",
                "resource_id": "1",
                "resource_title": "A",
                "action_type": "add_answer_blocks",
                "status": "planned",
            },
        )
        client.post(
            f"/api/shops/{SHOP}/geo/ledger/events",
            json={
                "resource_type": "product",
                "resource_id": "2",
                "resource_title": "B",
                "action_type": "improve_schema",
                "status": "measured",
            },
        )
        resp = client.get(f"/api/shops/{SHOP}/geo/ledger?status=measured")

    assert resp.status_code == 200
    assert resp.json()["total"] == 1
    assert resp.json()["events"][0]["status"] == "measured"


def test_get_geo_risk_guard_returns_protection_rows(client, snapshot_file, tmp_path) -> None:
    gsc_dir = tmp_path / SHOP
    gsc_dir.mkdir()
    gsc_path = gsc_dir / "gsc_performance.csv"
    gsc_path.write_text(
        "url,clicks,impressions,ctr,position\n"
        "https://example.com/products/harnais-chien,180,1200,0.15,3\n",
        encoding="utf-8",
    )

    with (
        patch("app.api.deps.get_token", return_value=None),
        patch("app.api.deps._SNAPSHOT_DEFAULT", snapshot_file),
        patch("app.api.geo.load_snapshot_from_file_or_db", return_value={**_SNAPSHOT, "shop": {"domain": "example.com"}}),
        patch("app.api.geo._find_gsc_file", return_value=gsc_path),
    ):
        resp = client.get(f"/api/shops/{SHOP}/geo/risk-guard")

    assert resp.status_code == 200
    data = resp.json()
    assert data["available"] is True
    assert "protected" in data["summary"]
    assert data["rows"][0]["guard_status"] in {"protected", "review_required", "safe"}


def test_get_geo_risk_guard_returns_404_without_snapshot(client, tmp_path) -> None:
    with (
        patch("app.api.deps.get_token", return_value=None),
        patch("app.api.deps._SNAPSHOT_DEFAULT", tmp_path / "missing.json"),
        patch("app.api.geo.load_snapshot_from_file_or_db", return_value=None),
    ):
        resp = client.get(f"/api/shops/{SHOP}/geo/risk-guard")

    assert resp.status_code == 404


def test_get_geo_collections_returns_dry_run_suggestions(client, snapshot_file, tmp_path) -> None:
    query_dir = tmp_path / SHOP
    query_dir.mkdir()
    query_path = query_dir / "gsc_query_page.csv"
    query_path.write_text(
        "query,page,clicks,impressions,ctr,position\n"
        "meilleur harnais chien,/collections/harnais-chien,10,600,0.02,8\n",
        encoding="utf-8",
    )
    snapshot = {
        **_SNAPSHOT,
        "products": [
            {
                **_SNAPSHOT["products"][0],
                "product_type": "Harnais chien",
                "tags": ["chien", "nylon"],
            },
            {
                "id": "gid://shopify/Product/3",
                "title": "Harnais chien cuir",
                "handle": "harnais-chien-cuir",
                "product_type": "Harnais chien",
                "tags": ["chien", "cuir"],
            },
        ],
    }

    with (
        patch("app.api.deps.get_token", return_value=None),
        patch("app.api.deps._SNAPSHOT_DEFAULT", snapshot_file),
        patch("app.api.geo.load_snapshot_from_file_or_db", return_value=snapshot),
        patch("app.api.geo._find_gsc_query_page_file", return_value=query_path),
    ):
        resp = client.get(f"/api/shops/{SHOP}/geo/collections?top=1&min_products=2")

    assert resp.status_code == 200
    data = resp.json()
    assert data["available"] is True
    assert data["gsc_query_page_connected"] is True
    assert data["summary"]["dry_run"] is True
    assert len(data["suggestions"]) == 1
    assert data["suggestions"][0]["dry_run"] is True
    assert data["suggestions"][0]["product_count"] == 2


def test_get_geo_collections_returns_404_without_snapshot(client, tmp_path) -> None:
    with (
        patch("app.api.deps.get_token", return_value=None),
        patch("app.api.deps._SNAPSHOT_DEFAULT", tmp_path / "missing.json"),
        patch("app.api.geo.load_snapshot_from_file_or_db", return_value=None),
    ):
        resp = client.get(f"/api/shops/{SHOP}/geo/collections")

    assert resp.status_code == 404


def test_get_geo_answer_blocks_returns_fact_grounded_blocks(client, snapshot_file) -> None:
    with (
        patch("app.api.deps.get_token", return_value=None),
        patch("app.api.deps._SNAPSHOT_DEFAULT", snapshot_file),
        patch("app.api.geo.load_snapshot_from_file_or_db", return_value=_SNAPSHOT),
    ):
        resp = client.get(f"/api/shops/{SHOP}/geo/answer-blocks?top=1&max_blocks=3")

    assert resp.status_code == 200
    data = resp.json()
    assert data["available"] is True
    assert data["summary"]["dry_run"] is True
    assert len(data["products"]) == 1
    assert data["products"][0]["answer_blocks"]
    assert data["products"][0]["jsonld"]["@type"] == "FAQPage"


def test_get_geo_answer_blocks_returns_404_without_snapshot(client, tmp_path) -> None:
    with (
        patch("app.api.deps.get_token", return_value=None),
        patch("app.api.deps._SNAPSHOT_DEFAULT", tmp_path / "missing.json"),
        patch("app.api.geo.load_snapshot_from_file_or_db", return_value=None),
    ):
        resp = client.get(f"/api/shops/{SHOP}/geo/answer-blocks")

    assert resp.status_code == 404
