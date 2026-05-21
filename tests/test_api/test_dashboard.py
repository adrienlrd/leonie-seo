"""Tests for the dashboard aggregator endpoint."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import app

_SHOP = "testshop.myshopify.com"


def _make_client() -> TestClient:
    return TestClient(app, raise_server_exceptions=True)


@pytest.fixture()
def mock_env(monkeypatch):
    monkeypatch.setenv("LEONIE_REQUIRE_SESSION_TOKEN", "false")
    monkeypatch.setenv("SHOPIFY_STORE_DOMAIN", _SHOP)
    monkeypatch.setenv("SHOPIFY_ACCESS_TOKEN", "test-token")


def _empty_snapshot():
    return {"products": [], "shop": {"domain": _SHOP}}


def test_dashboard_returns_all_zones(mock_env) -> None:
    with (
        patch("app.api.dashboard._load_snapshot", return_value=_empty_snapshot()),
        patch("app.api.dashboard._load_crawl_findings", return_value=[]),
        patch("app.api.dashboard.get_validated_niche_hypothesis", return_value=None),
        patch("app.api.dashboard._find_gsc_file", return_value=None),
        patch("app.api.dashboard._load_gsc_query_rows", return_value=[]),
        patch("app.api.dashboard.list_geo_events", return_value=[]),
        patch("app.api.dashboard.build_priority_actions", return_value={"actions": [], "sparse_signal": True}),
        patch("app.api.dashboard.get_shop_metrics", return_value={"total_cost_usd": 0.0}),
        patch("app.api.dashboard.check_budget", side_effect=Exception("no db")),
    ):
        client = _make_client()
        resp = client.get(f"/api/shops/{_SHOP}/dashboard?plan=free")
    assert resp.status_code == 200
    body = resp.json()
    assert "zone1" in body
    assert "zone2" in body
    assert "zone3" in body
    assert "zone4" in body
    assert "zone5" in body
    assert "zone6" in body
    assert "banners" in body
    assert "llm_budget" in body


def test_dashboard_zone6_always_disabled(mock_env) -> None:
    with (
        patch("app.api.dashboard._load_snapshot", return_value=_empty_snapshot()),
        patch("app.api.dashboard._load_crawl_findings", return_value=[]),
        patch("app.api.dashboard.get_validated_niche_hypothesis", return_value=None),
        patch("app.api.dashboard._find_gsc_file", return_value=None),
        patch("app.api.dashboard._load_gsc_query_rows", return_value=[]),
        patch("app.api.dashboard.list_geo_events", return_value=[]),
        patch("app.api.dashboard.build_priority_actions", return_value={"actions": [], "sparse_signal": True}),
        patch("app.api.dashboard.get_shop_metrics", return_value={"total_cost_usd": 0.0}),
        patch("app.api.dashboard.check_budget", side_effect=Exception("no db")),
    ):
        client = _make_client()
        resp = client.get(f"/api/shops/{_SHOP}/dashboard")
    assert resp.json()["zone6"]["ai_visibility_enabled"] is False
    assert resp.json()["zone6"]["available_in"] == "v2"


def test_dashboard_zone1_null_when_no_products(mock_env) -> None:
    with (
        patch("app.api.dashboard._load_snapshot", return_value=_empty_snapshot()),
        patch("app.api.dashboard._load_crawl_findings", return_value=[]),
        patch("app.api.dashboard.get_validated_niche_hypothesis", return_value=None),
        patch("app.api.dashboard._find_gsc_file", return_value=None),
        patch("app.api.dashboard._load_gsc_query_rows", return_value=[]),
        patch("app.api.dashboard.list_geo_events", return_value=[]),
        patch("app.api.dashboard.build_priority_actions", return_value={"actions": [], "sparse_signal": True}),
        patch("app.api.dashboard.get_shop_metrics", return_value={"total_cost_usd": 0.0}),
        patch("app.api.dashboard.check_budget", side_effect=Exception("no db")),
    ):
        client = _make_client()
        resp = client.get(f"/api/shops/{_SHOP}/dashboard")
    z1 = resp.json()["zone1"]
    assert z1["global_score"] is None
    assert z1["products_in_scope"] == 0


def test_dashboard_pilot_safe_banner(mock_env, monkeypatch) -> None:
    monkeypatch.setenv("LEONIE_PILOT_SAFE_MODE", "true")
    with (
        patch("app.api.dashboard._load_snapshot", return_value=_empty_snapshot()),
        patch("app.api.dashboard._load_crawl_findings", return_value=[]),
        patch("app.api.dashboard.get_validated_niche_hypothesis", return_value=None),
        patch("app.api.dashboard._find_gsc_file", return_value=None),
        patch("app.api.dashboard._load_gsc_query_rows", return_value=[]),
        patch("app.api.dashboard.list_geo_events", return_value=[]),
        patch("app.api.dashboard.build_priority_actions", return_value={"actions": [], "sparse_signal": True}),
        patch("app.api.dashboard.get_shop_metrics", return_value={"total_cost_usd": 0.0}),
        patch("app.api.dashboard.check_budget", side_effect=Exception("no db")),
    ):
        client = _make_client()
        resp = client.get(f"/api/shops/{_SHOP}/dashboard")
    assert resp.json()["banners"]["pilot_safe"] is True


def test_dashboard_llm_budget_pro_plan(mock_env) -> None:
    with (
        patch("app.api.dashboard._load_snapshot", return_value=_empty_snapshot()),
        patch("app.api.dashboard._load_crawl_findings", return_value=[]),
        patch("app.api.dashboard.get_validated_niche_hypothesis", return_value=None),
        patch("app.api.dashboard._find_gsc_file", return_value=None),
        patch("app.api.dashboard._load_gsc_query_rows", return_value=[]),
        patch("app.api.dashboard.list_geo_events", return_value=[]),
        patch("app.api.dashboard.build_priority_actions", return_value={"actions": [], "sparse_signal": True}),
        patch("app.api.dashboard.get_shop_metrics", return_value={"total_cost_usd": 3.5}),
        patch("app.api.dashboard.check_budget", return_value={
            "spent_usd": 3.5, "usage_pct": 23.3, "budget_usd": 15.0
        }),
    ):
        client = _make_client()
        resp = client.get(f"/api/shops/{_SHOP}/dashboard?plan=pro")
    budget = resp.json()["llm_budget"]
    assert budget["limit_usd"] == 15.0
    assert budget["used_usd"] == 3.5


def test_dashboard_zone4_pending_gsc_when_no_token(mock_env) -> None:
    with (
        patch("app.api.dashboard._load_snapshot", return_value=_empty_snapshot()),
        patch("app.api.dashboard._load_crawl_findings", return_value=[]),
        patch("app.api.dashboard.get_validated_niche_hypothesis", return_value=None),
        patch("app.api.dashboard._find_gsc_file", return_value=None),
        patch("app.api.dashboard._load_gsc_query_rows", return_value=[]),
        patch("app.api.dashboard.list_geo_events", return_value=[]),
        patch("app.api.dashboard.build_priority_actions", return_value={"actions": [], "sparse_signal": True}),
        patch("app.api.dashboard.get_shop_metrics", return_value={"total_cost_usd": 0.0}),
        patch("app.api.dashboard.check_budget", side_effect=Exception("no db")),
        patch("app.api.dashboard.get_conn", side_effect=Exception("no db")),
    ):
        client = _make_client()
        resp = client.get(f"/api/shops/{_SHOP}/dashboard")
    z4 = resp.json()["zone4"]
    pending_keys = [s["key"] for s in z4["pending_steps"]]
    assert "gsc" in pending_keys


def test_dashboard_zone3_reads_events_from_ledger_payload(mock_env) -> None:
    with (
        patch("app.api.dashboard._load_snapshot", return_value=_empty_snapshot()),
        patch("app.api.dashboard._load_crawl_findings", return_value=[]),
        patch("app.api.dashboard.get_validated_niche_hypothesis", return_value=None),
        patch("app.api.dashboard._find_gsc_file", return_value=None),
        patch("app.api.dashboard._load_gsc_query_rows", return_value=[]),
        patch(
            "app.api.dashboard.list_geo_events",
            return_value={
                "total": 2,
                "limit": 200,
                "offset": 0,
                "events": [
                    {"status": "applied", "created_at": "2026-05-01T00:00:00+00:00"},
                    {"status": "planned", "created_at": "2026-05-02T00:00:00+00:00"},
                ],
            },
        ),
        patch("app.api.dashboard.build_priority_actions", return_value={"actions": [], "sparse_signal": True}),
        patch("app.api.dashboard.get_shop_metrics", return_value={"total_cost_usd": 0.0}),
        patch("app.api.dashboard.check_budget", side_effect=Exception("no db")),
    ):
        client = _make_client()
        resp = client.get(f"/api/shops/{_SHOP}/dashboard")

    assert resp.status_code == 200
    assert resp.json()["zone3"]["active_optimizations_count"] == 1
