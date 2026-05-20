"""Tests for GET /api/shops/{shop}/priorities endpoint."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import app

_SHOP = "testshop.myshopify.com"

_SNAPSHOT = {
    "snapshot_date": "2026-05-20T10:00:00",
    "shop": {"domain": _SHOP},
    "products": [
        {
            "id": "gid://shopify/Product/101",
            "handle": "prod-a",
            "title": "Product A",
            "status": "ACTIVE",
            "descriptionHtml": "A nice product.",
            "seo": {"title": "Product A", "description": "A nice product."},
            "variants": {"edges": [{"node": {"price": "49.99", "inventoryQuantity": 5}}]},
        },
    ],
    "collections": [],
}

_PRIORITY_RESULT = {
    "shop": _SHOP,
    "generated_at": "2026-05-20T12:00:00+00:00",
    "scope": "active",
    "actions": [
        {
            "rank": 1,
            "action_id": "prod-a-improve_seo_copy-1",
            "product_id": "gid://shopify/Product/101",
            "product_handle": "prod-a",
            "product_title": "Product A",
            "action_type": "improve_seo_copy",
            "action_label": "Améliorer le contenu SEO",
            "priority_score": 72,
            "why_now": "Cette page reçoit 300 impressions à la position 14.",
            "evidence": [{"source": "gsc", "metric": "impressions", "value": 300}],
            "estimates": {
                "impact": "high",
                "confidence": "high",
                "effort": "low",
                "risk": "low",
                "click_gain_estimate": 12.0,
                "revenue_estimate_eur": 80.0,
                "estimate_basis": "gsc_only",
            },
            "success_metric": {
                "name": "gsc_impressions",
                "current_value": 300,
                "target_value": 390,
                "measurement_window_days": 60,
                "source": "gsc",
            },
            "preview": {
                "depends_on": ["product_facts_layer"],
                "expected_output_type": "meta",
                "human_review_required": True,
            },
            "risk_guard": {"status": "safe", "reasons": [], "override_required": False},
            "niche_alerts": [],
        }
    ],
    "candidates_evaluated": 1,
    "sparse_signal": True,
    "llm_used": False,
    "fallback_reason": "plan_free",
    "next_refresh_at": "2026-05-27T12:00:00+00:00",
}


def _make_client() -> TestClient:
    return TestClient(app, raise_server_exceptions=True)


@pytest.fixture()
def mock_env(monkeypatch):
    monkeypatch.setenv("LEONIE_REQUIRE_SESSION_TOKEN", "false")
    monkeypatch.setenv("SHOPIFY_STORE_DOMAIN", _SHOP)
    monkeypatch.setenv("SHOPIFY_ACCESS_TOKEN", "test-token")


def test_get_priorities_returns_schema(mock_env) -> None:
    with (
        patch("app.api.priorities._load_snapshot", return_value=_SNAPSHOT),
        patch("app.api.priorities._load_crawl_findings", return_value=[]),
        patch("app.api.priorities._find_gsc_file", return_value=None),
        patch("app.api.priorities._load_gsc_query_rows", return_value=[]),
        patch("app.api.priorities.get_validated_niche_hypothesis", return_value=None),
        patch("app.api.priorities.build_priority_actions", return_value=_PRIORITY_RESULT),
    ):
        client = _make_client()
        resp = client.get(f"/api/shops/{_SHOP}/priorities")
    assert resp.status_code == 200
    data = resp.json()
    assert "actions" in data
    assert "sparse_signal" in data
    assert "llm_used" in data
    assert data["shop"] == _SHOP


def test_get_priorities_plan_free_by_default(mock_env) -> None:
    captured_plan: dict[str, str] = {}

    def _capture_plan(*args, plan: str = "free", **kwargs) -> dict:
        captured_plan["plan"] = plan
        return _PRIORITY_RESULT

    with (
        patch("app.api.priorities._load_snapshot", return_value=_SNAPSHOT),
        patch("app.api.priorities._load_crawl_findings", return_value=[]),
        patch("app.api.priorities._find_gsc_file", return_value=None),
        patch("app.api.priorities._load_gsc_query_rows", return_value=[]),
        patch("app.api.priorities.get_validated_niche_hypothesis", return_value=None),
        patch("app.api.priorities.build_priority_actions", side_effect=_capture_plan),
    ):
        client = _make_client()
        client.get(f"/api/shops/{_SHOP}/priorities")
    assert captured_plan.get("plan") == "free"


def test_get_priorities_accepts_pro_plan(mock_env) -> None:
    with (
        patch("app.api.priorities._load_snapshot", return_value=_SNAPSHOT),
        patch("app.api.priorities._load_crawl_findings", return_value=[]),
        patch("app.api.priorities._find_gsc_file", return_value=None),
        patch("app.api.priorities._load_gsc_query_rows", return_value=[]),
        patch("app.api.priorities.get_validated_niche_hypothesis", return_value=None),
        patch("app.api.priorities.build_priority_actions", return_value=_PRIORITY_RESULT),
    ):
        client = _make_client()
        resp = client.get(f"/api/shops/{_SHOP}/priorities?plan=pro")
    assert resp.status_code == 200


def test_get_priorities_snapshot_age_in_response(mock_env) -> None:
    with (
        patch("app.api.priorities._load_snapshot", return_value=_SNAPSHOT),
        patch("app.api.priorities._load_crawl_findings", return_value=[]),
        patch("app.api.priorities._find_gsc_file", return_value=None),
        patch("app.api.priorities._load_gsc_query_rows", return_value=[]),
        patch("app.api.priorities.get_validated_niche_hypothesis", return_value=None),
        patch("app.api.priorities.build_priority_actions", return_value=_PRIORITY_RESULT),
    ):
        client = _make_client()
        resp = client.get(f"/api/shops/{_SHOP}/priorities")
    assert resp.status_code == 200
    assert "snapshot_age_days" in resp.json()
