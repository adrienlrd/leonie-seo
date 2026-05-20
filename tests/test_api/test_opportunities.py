"""Tests for the opportunities endpoint."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import app

_SNAPSHOT = {
    "snapshot_date": "2026-05-20T10:00:00",
    "shop": {"domain": "test.myshopify.com"},
    "products": [
        {
            "id": "gid://shopify/Product/1",
            "title": "Harnais chien nylon",
            "handle": "harnais-chien",
            "status": "ACTIVE",
            "descriptionHtml": "Harnais en nylon réglable, lavable et confortable.",
            "seo": {"title": "Harnais chien nylon", "description": "Harnais réglable pour chien."},
            "variants": {"edges": [{"node": {"price": "49.90", "inventoryQuantity": 5}}]},
        },
        {
            "id": "gid://shopify/Product/2",
            "title": "Laisse cuir",
            "handle": "laisse-cuir",
            "status": "DRAFT",
            "descriptionHtml": "Laisse en cuir naturel.",
            "seo": {"title": "", "description": ""},
            "variants": {"edges": [{"node": {"price": "29.90", "inventoryQuantity": 3}}]},
        },
    ],
    "collections": [],
}

_SHOP = "test.myshopify.com"


def _make_client() -> TestClient:
    return TestClient(app, raise_server_exceptions=True)


@pytest.fixture()
def mock_env(monkeypatch):
    monkeypatch.setenv("LEONIE_REQUIRE_SESSION_TOKEN", "false")
    monkeypatch.setenv("SHOPIFY_STORE_DOMAIN", _SHOP)
    monkeypatch.setenv("SHOPIFY_ACCESS_TOKEN", "test-token")


def test_get_opportunities_returns_schema(mock_env) -> None:
    with (
        patch("app.api.opportunities._load_snapshot", return_value=_SNAPSHOT),
        patch("app.api.opportunities.get_validated_niche_hypothesis", return_value=None),
        patch("app.api.opportunities._load_crawl_findings", return_value=[]),
        patch("app.api.opportunities._find_gsc_file", return_value=None),
        patch("app.api.opportunities._load_gsc_query_rows", return_value=[]),
    ):
        client = _make_client()
        resp = client.get(f"/api/shops/{_SHOP}/opportunities")

    assert resp.status_code == 200
    data = resp.json()
    assert "opportunities" in data
    assert "summary" in data
    assert "total_products_scanned" in data
    assert "by_tier" in data["summary"]
    for opp in data["opportunities"]:
        assert "product_id" in opp
        assert "opportunity_score" in opp
        assert "tier" in opp
        assert "primary_reason" in opp
        assert "signals" in opp
        assert "confidence" in opp
        assert 0 <= opp["opportunity_score"] <= 100


def test_get_opportunities_scope_active(mock_env) -> None:
    with (
        patch("app.api.opportunities._load_snapshot", return_value=_SNAPSHOT),
        patch("app.api.opportunities.get_validated_niche_hypothesis", return_value=None),
        patch("app.api.opportunities._load_crawl_findings", return_value=[]),
        patch("app.api.opportunities._find_gsc_file", return_value=None),
        patch("app.api.opportunities._load_gsc_query_rows", return_value=[]),
    ):
        client = _make_client()
        resp = client.get(f"/api/shops/{_SHOP}/opportunities?scope=active")

    assert resp.status_code == 200
    data = resp.json()
    handles = [opp["handle"] for opp in data["opportunities"]]
    assert "harnais-chien" in handles
    assert "laisse-cuir" not in handles


def test_get_opportunities_filters_by_intent(mock_env) -> None:
    gsc_query_rows = [
        {"query": "meilleur harnais chien", "impressions": 50, "clicks": 2, "position": 15.0},
    ]
    with (
        patch("app.api.opportunities._load_snapshot", return_value=_SNAPSHOT),
        patch("app.api.opportunities.get_validated_niche_hypothesis", return_value=None),
        patch("app.api.opportunities._load_crawl_findings", return_value=[]),
        patch("app.api.opportunities._find_gsc_file", return_value=None),
        patch("app.api.opportunities._load_gsc_query_rows", return_value=gsc_query_rows),
    ):
        client = _make_client()
        resp_all = client.get(f"/api/shops/{_SHOP}/opportunities")
        resp_filtered = client.get(f"/api/shops/{_SHOP}/opportunities?intent=transactional")

    assert resp_all.status_code == 200
    assert resp_filtered.status_code == 200
    # All items in filtered response must have the requested intent
    for opp in resp_filtered.json()["opportunities"]:
        assert "transactional" in opp["matched_intents"]
