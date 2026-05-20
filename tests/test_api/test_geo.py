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
    # /geo/readiness is now permanently redirected (301) to /audit/readiness
    resp = client.get(f"/api/shops/{SHOP}/geo/readiness", follow_redirects=False)
    assert resp.status_code == 301
    assert f"/api/shops/{SHOP}/audit/readiness" in resp.headers["location"]


def test_get_geo_readiness_respects_top_parameter(client, snapshot_file) -> None:
    resp = client.get(f"/api/shops/{SHOP}/geo/readiness?top=1", follow_redirects=False)
    assert resp.status_code == 301
    assert "top=1" in resp.headers["location"]


def test_get_geo_readiness_filters_by_scope_when_requested(client, snapshot_file) -> None:
    resp = client.get(f"/api/shops/{SHOP}/geo/readiness?scope=draft", follow_redirects=False)
    assert resp.status_code == 301
    assert "scope=draft" in resp.headers["location"]


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


def test_get_geo_control_groups_returns_control_candidates(client, snapshot_file, tmp_path) -> None:
    db = tmp_path / "control-groups.db"
    init_db(db)
    snapshot = {
        "shop": {"domain": "example.com"},
        "products": [
            {
                **_SNAPSHOT["products"][0],
                "productType": "Harnais",
                "tags": ["chien", "nylon"],
                "variants": {"edges": [{"node": {"price": "49.90", "inventoryQuantity": 12}}]},
            },
            {
                "id": "gid://shopify/Product/3",
                "title": "Harnais chien rouge",
                "handle": "harnais-chien-rouge",
                "productType": "Harnais",
                "tags": ["chien", "nylon"],
                "description": "Harnais nylon réglable confortable pour chien avec boucle solide.",
                "variants": {"edges": [{"node": {"price": "52.00", "inventoryQuantity": 10}}]},
                "status": "ACTIVE",
            },
        ],
        "collections": [],
    }
    gsc_dir = tmp_path / SHOP
    gsc_dir.mkdir()
    gsc_path = gsc_dir / "gsc_performance.csv"
    gsc_path.write_text(
        "url,clicks,impressions,ctr,position\n"
        "https://example.com/products/harnais-chien,12,300,0.04,8\n"
        "https://example.com/products/harnais-chien-rouge,11,285,0.038,8.5\n",
        encoding="utf-8",
    )

    with (
        patch("app.api.deps.get_token", return_value=None),
        patch("app.api.deps._SNAPSHOT_DEFAULT", snapshot_file),
        patch("app.api.geo.DB_PATH", db),
        patch("app.api.geo.load_snapshot_from_file_or_db", return_value=snapshot),
        patch("app.api.geo._find_gsc_file", return_value=gsc_path),
    ):
        client.post(
            f"/api/shops/{SHOP}/geo/ledger/events",
            json={
                "resource_type": "product",
                "resource_id": "gid://shopify/Product/1",
                "resource_title": "Harnais chien nylon",
                "action_type": "enrich_product_facts",
                "status": "applied",
                "score_before": 60,
                "before_snapshot": {
                    "path": "/products/harnais-chien",
                    "content": {"handle": "harnais-chien"},
                    "commerce": {"price": "49.90", "inventory_quantity": 12},
                    "scores": {"readiness_score": 60},
                },
                "metrics_before": {"gsc": {"impressions": 300, "position": 8}},
            },
        )
        resp = client.get(f"/api/shops/{SHOP}/geo/control-groups")

    assert resp.status_code == 200
    data = resp.json()
    assert data["available"] is True
    assert data["summary"]["groups_with_controls"] == 1
    assert data["groups"][0]["controls"][0]["resource_id"] == "gid://shopify/Product/3"
    assert data["groups"][0]["controls"][0]["quality"] == "strong"


def test_get_geo_validation_timeline_returns_event_windows(client, tmp_path) -> None:
    db = tmp_path / "timeline.db"
    init_db(db)
    with (
        patch("app.api.deps.get_token", return_value=None),
        patch("app.api.geo.DB_PATH", db),
    ):
        client.post(
            f"/api/shops/{SHOP}/geo/ledger/events",
            json={
                "resource_type": "product",
                "resource_id": "gid://shopify/Product/1",
                "resource_title": "Harnais chien nylon",
                "action_type": "enrich_product_facts",
                "status": "applied",
                "score_before": 60,
                "measurement_status": "baseline_captured",
                "before_snapshot": {"path": "/products/harnais-chien", "scores": {"readiness_score": 60}},
                "metrics_before": {"gsc": {"impressions": 300, "position": 8}},
            },
        )
        resp = client.get(f"/api/shops/{SHOP}/geo/validation-timeline")

    assert resp.status_code == 200
    data = resp.json()
    assert data["available"] is True
    assert data["summary"]["timelines_built"] == 1
    assert data["timelines"][0]["windows"][0]["label"] == "J+0"
    assert data["timelines"][0]["windows"][-1]["label"] == "J+90"


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


def test_get_geo_crawlability_returns_llms_preview(client, snapshot_file) -> None:
    snapshot = {
        **_SNAPSHOT,
        "shop": {"domain": "example.com"},
        "collections": [{"id": "gid://shopify/Collection/1", "title": "Harnais", "handle": "harnais"}],
    }
    with (
        patch("app.api.deps.get_token", return_value=None),
        patch("app.api.deps._SNAPSHOT_DEFAULT", snapshot_file),
        patch("app.api.geo.load_snapshot_from_file_or_db", return_value=snapshot),
    ):
        resp = client.get(f"/api/shops/{SHOP}/geo/crawlability?top_products=5&top_collections=5")

    assert resp.status_code == 200
    data = resp.json()
    assert data["available"] is True
    assert data["domain"] == "example.com"
    assert data["summary"]["dry_run"] is True
    assert "llms.txt preview" in data["llms_txt"]
    assert data["included_pages"]


def test_get_geo_crawlability_returns_404_without_snapshot(client, tmp_path) -> None:
    with (
        patch("app.api.deps.get_token", return_value=None),
        patch("app.api.deps._SNAPSHOT_DEFAULT", tmp_path / "missing.json"),
        patch("app.api.geo.load_snapshot_from_file_or_db", return_value=None),
    ):
        resp = client.get(f"/api/shops/{SHOP}/geo/crawlability")

    assert resp.status_code == 404


def test_get_geo_competitors_returns_query_monitor(client, snapshot_file, tmp_path) -> None:
    query_dir = tmp_path / SHOP
    query_dir.mkdir()
    query_path = query_dir / "gsc_query_page.csv"
    query_path.write_text(
        "query,page,clicks,impressions,ctr,position\n"
        "meilleur harnais chien,/products/harnais-chien,10,700,0.01,9\n",
        encoding="utf-8",
    )

    with (
        patch("app.api.deps.get_token", return_value=None),
        patch("app.api.deps._SNAPSHOT_DEFAULT", snapshot_file),
        patch("app.api.geo.load_snapshot_from_file_or_db", return_value=_SNAPSHOT),
        patch("app.api.geo._find_gsc_query_page_file", return_value=query_path),
    ):
        resp = client.get(f"/api/shops/{SHOP}/geo/competitors?competitors=miacara.com,zara.com&top=5")

    assert resp.status_code == 200
    data = resp.json()
    assert data["available"] is True
    assert data["gsc_query_page_connected"] is True
    assert data["summary"]["dry_run"] is True
    assert data["summary"]["competitor_domains"] == 2
    assert data["queries"][0]["competitors"]


def test_get_geo_competitors_returns_404_without_snapshot(client, tmp_path) -> None:
    with (
        patch("app.api.deps.get_token", return_value=None),
        patch("app.api.deps._SNAPSHOT_DEFAULT", tmp_path / "missing.json"),
        patch("app.api.geo.load_snapshot_from_file_or_db", return_value=None),
    ):
        resp = client.get(f"/api/shops/{SHOP}/geo/competitors")

    assert resp.status_code == 404


def test_create_and_list_geo_optimization_snapshot(client, snapshot_file, tmp_path) -> None:
    db = tmp_path / "geo-snapshots.db"
    init_db(db)
    gsc_dir = tmp_path / SHOP
    gsc_dir.mkdir()
    gsc_path = gsc_dir / "gsc_performance.csv"
    gsc_path.write_text(
        "url,clicks,impressions,ctr,position\n"
        "https://example.com/products/harnais-chien,12,300,0.04,9\n",
        encoding="utf-8",
    )
    payload = {
        "resource_type": "product",
        "resource_id": "gid://shopify/Product/1",
        "action_type": "add_answer_blocks",
        "hypothesis": "Answer blocks should improve clarity.",
        "notes": "Before snapshot.",
    }

    with (
        patch("app.api.deps.get_token", return_value=None),
        patch("app.api.deps._SNAPSHOT_DEFAULT", snapshot_file),
        patch("app.api.geo.DB_PATH", db),
        patch("app.api.geo.load_snapshot_from_file_or_db", return_value={**_SNAPSHOT, "shop": {"domain": "example.com"}}),
        patch("app.api.geo._find_gsc_file", return_value=gsc_path),
    ):
        created = client.post(f"/api/shops/{SHOP}/geo/optimization-snapshots", json=payload)
        listed = client.get(f"/api/shops/{SHOP}/geo/optimization-snapshots")

    assert created.status_code == 200
    assert created.json()["created"] is True
    assert created.json()["snapshot"]["metrics"]["gsc"]["impressions"] == 300
    assert listed.status_code == 200
    assert listed.json()["total"] == 1
    assert listed.json()["snapshots"][0]["action_type"] == "add_answer_blocks"


def test_create_geo_ledger_event_from_snapshot_and_update_status(client, snapshot_file, tmp_path) -> None:
    db = tmp_path / "geo-events.db"
    init_db(db)
    with (
        patch("app.api.deps.get_token", return_value=None),
        patch("app.api.deps._SNAPSHOT_DEFAULT", snapshot_file),
        patch("app.api.geo.DB_PATH", db),
        patch("app.api.geo.load_snapshot_from_file_or_db", return_value=_SNAPSHOT),
        patch("app.api.geo._find_gsc_file", return_value=None),
    ):
        snapshot_resp = client.post(
            f"/api/shops/{SHOP}/geo/optimization-snapshots",
            json={
                "resource_type": "product",
                "resource_id": "gid://shopify/Product/1",
                "action_type": "enrich_product_facts",
                "hypothesis": "Richer facts should improve answer eligibility.",
            },
        )
        snapshot_id = snapshot_resp.json()["snapshot_id"]
        created = client.post(
            f"/api/shops/{SHOP}/geo/ledger/events/from-snapshot",
            json={
                "snapshot_id": snapshot_id,
                "status": "applied",
                "job_id": "job-123",
                "estimated_impact": {"revenue_estimate": 22},
            },
        )
        event_id = created.json()["event_id"]
        updated = client.patch(
            f"/api/shops/{SHOP}/geo/ledger/events/{event_id}/status",
            json={
                "status": "measured",
                "score_after": 88,
                "measurement_status": "j30_measured",
                "observed_impact": {"revenue": 11},
            },
        )
        listed = client.get(f"/api/shops/{SHOP}/geo/ledger")

    assert snapshot_resp.status_code == 200
    assert created.status_code == 200
    assert updated.status_code == 200
    event = listed.json()["events"][0]
    assert event["snapshot_id"] == snapshot_id
    assert event["status"] == "measured"
    assert event["score_after"] == 88
    assert event["measurement_status"] == "j30_measured"
    assert event["observed_impact"]["revenue"] == 11
    assert [entry["status"] for entry in event["status_history"]] == ["applied", "measured"]


def test_create_geo_optimization_snapshot_returns_404_for_missing_resource(client, snapshot_file, tmp_path) -> None:
    db = tmp_path / "geo-snapshots.db"
    init_db(db)
    with (
        patch("app.api.deps.get_token", return_value=None),
        patch("app.api.deps._SNAPSHOT_DEFAULT", snapshot_file),
        patch("app.api.geo.DB_PATH", db),
        patch("app.api.geo.load_snapshot_from_file_or_db", return_value=_SNAPSHOT),
        patch("app.api.geo._find_gsc_file", return_value=None),
    ):
        resp = client.post(
            f"/api/shops/{SHOP}/geo/optimization-snapshots",
            json={
                "resource_type": "product",
                "resource_id": "missing",
                "action_type": "add_answer_blocks",
            },
        )

    assert resp.status_code == 404


def test_get_geo_progress_curve_returns_payload_with_degraded_tracking(client, tmp_path) -> None:
    db = tmp_path / "geo-progress.db"
    init_db(db)
    with (
        patch("app.api.deps.get_token", return_value=None),
        patch("app.api.geo.DB_PATH", db),
        patch("app.api.geo._find_gsc_file", return_value=None),
        patch("app.api.geo._load_ga4_daily", return_value=({}, False)),
    ):
        resp = client.get(f"/api/shops/{SHOP}/geo/progress-curve?days=90")

    assert resp.status_code == 200
    data = resp.json()
    assert data["shop"] == SHOP
    assert data["window_days"] == 90
    assert data["flags"]["incomplete_tracking"] is True
    assert data["series"]["geo_score"] == []
    assert data["totals"]["snapshots_in_window"] == 0


def test_get_geo_progress_curve_includes_snapshot_and_event_data(client, tmp_path) -> None:
    db = tmp_path / "geo-progress-2.db"
    init_db(db)
    # Seed one snapshot + one event directly in the DB to exercise full flow.
    from app.geo.ledger import create_geo_event
    from app.geo.optimization_snapshots import create_optimization_snapshot

    snapshot_payload = {
        "resource_type": "product",
        "resource_id": "p1",
        "resource_title": "Harnais",
        "action_type": "enrich_facts",
        "source": "geo",
        "hypothesis": None,
        "snapshot": {"commerce": {"inventory_quantity": 5, "price": "49.90"}},
        "metrics": {"gsc": {"impressions": 1500, "clicks": 120, "ctr": 0.08, "position": 8.5}},
        "readiness_score": 72,
        "seo_score": 60,
        "content_hash": "abc",
    }
    create_optimization_snapshot(shop=SHOP, snapshot_data=snapshot_payload, db_path=db)
    create_geo_event(
        shop=SHOP,
        event_type="planned_optimization",
        resource_type="product",
        resource_id="p1",
        resource_title="Harnais",
        action_type="enrich_facts",
        before_snapshot={"scores": {"readiness_score": 60}},
        metrics_before={"gsc": {"impressions": 1500}},
        estimated_impact={"revenue_estimate": 120.0},
        db_path=db,
    )

    with (
        patch("app.api.deps.get_token", return_value=None),
        patch("app.api.geo.DB_PATH", db),
        patch("app.api.geo._find_gsc_file", return_value=None),
        patch("app.api.geo._load_ga4_daily", return_value=({}, True)),
    ):
        resp = client.get(f"/api/shops/{SHOP}/geo/progress-curve?days=90")

    assert resp.status_code == 200
    data = resp.json()
    assert data["totals"]["snapshots_in_window"] == 1
    assert data["totals"]["events_in_window"] == 1
    assert data["series"]["geo_score"][0]["value"] == 72
    assert data["series"]["impressions"][0]["value"] == 1500
    assert len(data["optimizations_in_validation"]) == 1
    assert data["flags"]["incomplete_tracking"] is True  # gsc missing → still flagged


def test_get_geo_confidence_scores_returns_summary_and_scores(client, tmp_path) -> None:
    db = tmp_path / "geo-confidence.db"
    init_db(db)
    from app.geo.ledger import create_geo_event

    create_geo_event(
        shop=SHOP,
        event_type="planned_optimization",
        resource_type="product",
        resource_id="p1",
        resource_title="Harnais",
        action_type="enrich_facts",
        before_snapshot={},
        metrics_before={"gsc": {"impressions": 800, "clicks": 40}},
        estimated_impact={"revenue_estimate": 50.0},
        status="applied",
        db_path=db,
    )

    with (
        patch("app.api.deps.get_token", return_value=None),
        patch("app.api.geo.DB_PATH", db),
    ):
        resp = client.get(f"/api/shops/{SHOP}/geo/confidence-scores")

    assert resp.status_code == 200
    data = resp.json()
    assert data["shop"] == SHOP
    assert data["summary"]["total_events"] == 1
    assert "by_label" in data["summary"]
    assert len(data["scores"]) == 1
    assert "score" in data["scores"][0]
    assert "label" in data["scores"][0]
    assert "factors" in data["scores"][0]


def test_get_geo_impact_report_returns_reports_and_markdown(client, tmp_path) -> None:
    db = tmp_path / "geo-impact-report.db"
    init_db(db)
    from app.geo.ledger import create_geo_event

    create_geo_event(
        shop=SHOP,
        event_type="planned_optimization",
        resource_type="product",
        resource_id="p1",
        resource_title="Harnais nylon",
        action_type="enrich_facts",
        before_snapshot={},
        metrics_before={"gsc": {"impressions": 600, "clicks": 30, "ctr": 0.05, "position": 12.0}},
        metrics_after={"gsc": {"impressions": 900, "clicks": 50, "ctr": 0.055, "position": 10.0}},
        score_before=60,
        score_after=75,
        estimated_impact={"revenue_estimate": 80.0},
        status="applied",
        db_path=db,
    )

    with (
        patch("app.api.deps.get_token", return_value=None),
        patch("app.api.geo.DB_PATH", db),
    ):
        resp = client.get(f"/api/shops/{SHOP}/geo/impact-report")

    assert resp.status_code == 200
    data = resp.json()
    assert data["shop"] == SHOP
    assert "generated_at" in data
    assert data["summary"]["total"] == 1
    assert "by_verdict" in data["summary"]
    assert len(data["reports"]) == 1
    report = data["reports"][0]
    assert report["scores"]["geo_delta"] == 15
    assert report["verdict"] in ("positif_probable", "neutre", "inconclusif", "négatif_possible")
    assert "next_recommendation" in report
    assert "Harnais nylon" in data["markdown"]
    assert "# Rapport d'impact GEO" in data["markdown"]


def test_get_geo_retention_milestones_returns_milestones(client, tmp_path) -> None:
    db = tmp_path / "geo-retention.db"
    init_db(db)
    from app.geo.ledger import create_geo_event

    create_geo_event(
        shop=SHOP,
        event_type="planned_optimization",
        resource_type="product",
        resource_id="p1",
        resource_title="Harnais",
        action_type="enrich_facts",
        before_snapshot={},
        metrics_before={"gsc": {"impressions": 400}},
        estimated_impact={},
        status="applied",
        db_path=db,
    )

    with (
        patch("app.api.deps.get_token", return_value=None),
        patch("app.api.geo.DB_PATH", db),
    ):
        resp = client.get(f"/api/shops/{SHOP}/geo/retention-milestones")

    assert resp.status_code == 200
    data = resp.json()
    assert data["shop"] == SHOP
    assert data["has_active_events"] is True
    assert len(data["milestones"]) == 4
    assert data["milestones"][0]["label"] == "J+7"
    assert "retention_message_fr" in data


def test_get_geo_next_best_actions_returns_actions_and_summary(client, tmp_path) -> None:
    db = tmp_path / "geo-nba.db"
    init_db(db)
    from app.geo.ledger import create_geo_event

    create_geo_event(
        shop=SHOP,
        event_type="planned_optimization",
        resource_type="product",
        resource_id="p1",
        resource_title="Harnais nylon",
        action_type="enrich_facts",
        before_snapshot={},
        metrics_before={"gsc": {"impressions": 600, "clicks": 30, "ctr": 0.05, "position": 12.0}},
        metrics_after={"gsc": {"impressions": 900, "clicks": 50, "ctr": 0.055, "position": 10.0}},
        score_before=60,
        score_after=75,
        estimated_impact={"revenue_estimate": 80.0},
        status="applied",
        db_path=db,
    )

    with (
        patch("app.api.deps.get_token", return_value=None),
        patch("app.api.geo.DB_PATH", db),
        patch("app.api.geo.load_snapshot_from_file_or_db", return_value=None),
    ):
        resp = client.get(f"/api/shops/{SHOP}/geo/next-best-actions")

    assert resp.status_code == 200
    data = resp.json()
    assert data["shop"] == SHOP
    assert data["dry_run"] is True
    assert data["summary"]["total_actions"] == 1
    assert "by_action" in data["summary"]
    assert len(data["actions"]) == 1
    action = data["actions"][0]
    assert action["action_type"] in ("répliquer", "ajuster", "rollback", "attendre")
    assert action["priority"] in ("high", "medium", "low")
    assert action["dry_run"] is True


def test_get_geo_faq_content_returns_content_items(client, tmp_path) -> None:
    snapshot = {
        "products": [
            {
                "id": "gid://shopify/Product/1",
                "title": "Harnais nylon chien",
                "handle": "harnais-nylon",
                "product_type": "Harnais",
                "descriptionHtml": "Harnais en nylon. Compatible chiens 10-40 kg. Garantie 2 ans.",
                "status": "ACTIVE",
                "variants": {"edges": [{"node": {"price": "39.90"}}]},
                "tags": [],
            }
        ],
        "collections": [],
    }

    with (
        patch("app.api.deps.get_token", return_value=None),
        patch("app.api.geo.load_snapshot_from_file_or_db", return_value=snapshot),
        patch("app.api.geo._find_gsc_file", return_value=None),
    ):
        resp = client.get(f"/api/shops/{SHOP}/geo/faq-content?top=1")

    assert resp.status_code == 200
    data = resp.json()
    assert data["shop"] == SHOP
    assert data["summary"]["total"] == 1
    assert len(data["content_items"]) == 1
    item = data["content_items"][0]
    assert item["content_type"] == "product_faq"
    assert "faq_items" in item
    assert "faq_jsonld" in item
    assert "quality_score" in item
    assert item["status"] in ("draft", "needs_review")
