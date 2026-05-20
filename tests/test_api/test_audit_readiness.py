"""Tests for the unified audit readiness endpoint."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import app

_SNAPSHOT = {
    "snapshot_date": "2026-05-20T10:00:00",
    "products": [
        {
            "id": "gid://shopify/Product/1",
            "title": "Harnais chien nylon",
            "handle": "harnais-chien",
            "status": "ACTIVE",
            "onlineStoreUrl": "https://test.myshopify.com/products/harnais-chien",
            "seo": {
                "title": "Harnais chien nylon réglable pour promenade",
                "description": "Harnais chien réglable, lavable et confortable.",
            },
            "description": "Harnais en nylon réglable, lavable et confortable. Fabriqué en France.",
            "images": {"edges": [{"node": {"url": "https://example.com/img.jpg"}}]},
            "variants": {"edges": [{"node": {"price": "49.90"}}]},
        }
    ],
    "collections": [],
}

_SHOP = "test.myshopify.com"


def _client_with_snapshot(snapshot=None, niche_hypothesis=None, crawl_findings=None):
    client = TestClient(app, raise_server_exceptions=True)
    snap = snapshot if snapshot is not None else _SNAPSHOT

    def _mock_load_snapshot(ctx):
        return snap

    def _mock_get_niche(shop):
        return niche_hypothesis

    def _mock_crawl(shop, db_path=None):
        return crawl_findings or []

    return client, _mock_load_snapshot, _mock_get_niche, _mock_crawl


def _make_client():
    return TestClient(app, raise_server_exceptions=True)


@pytest.fixture()
def mock_env(monkeypatch, tmp_path):
    monkeypatch.setenv("LEONIE_REQUIRE_SESSION_TOKEN", "false")
    monkeypatch.setenv("SHOPIFY_STORE_DOMAIN", _SHOP)
    monkeypatch.setenv("SHOPIFY_ACCESS_TOKEN", "test-token")
    return tmp_path


def test_get_audit_readiness_returns_global_score(mock_env) -> None:
    with (
        patch("app.api.audit._load_snapshot", return_value=_SNAPSHOT),
        patch("app.api.audit.get_validated_niche_hypothesis", return_value=None),
        patch("app.api.audit._load_crawl_findings", return_value=[]),
    ):
        client = _make_client()
        resp = client.get(f"/api/shops/{_SHOP}/audit/readiness")

    assert resp.status_code == 200
    data = resp.json()
    assert "global_score" in data
    assert "global_level" in data
    assert 0 <= data["global_score"] <= 100
    assert data["global_level"] in {"excellent", "bon", "partiel", "faible"}
    assert "products" in data
    assert "summary" in data
    assert "crawl_health" in data
    assert "niche_alerts" in data


def test_get_audit_readiness_with_scope_active(mock_env) -> None:
    snapshot = {
        "snapshot_date": "2026-05-20T10:00:00",
        "products": [
            {
                "id": "gid://shopify/Product/1",
                "title": "Produit actif",
                "handle": "produit-actif",
                "status": "ACTIVE",
                "onlineStoreUrl": "https://test.myshopify.com/products/produit-actif",
                "description": "Description produit actif.",
            },
            {
                "id": "gid://shopify/Product/2",
                "title": "Produit brouillon",
                "handle": "produit-brouillon",
                "status": "DRAFT",
                "onlineStoreUrl": None,
                "description": "",
            },
        ],
        "collections": [],
    }
    with (
        patch("app.api.audit._load_snapshot", return_value=snapshot),
        patch("app.api.audit.get_validated_niche_hypothesis", return_value=None),
        patch("app.api.audit._load_crawl_findings", return_value=[]),
    ):
        client = _make_client()
        resp = client.get(f"/api/shops/{_SHOP}/audit/readiness?scope=active")

    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["products"][0]["handle"] == "produit-actif"


def test_get_audit_readiness_with_niche_alerts(mock_env) -> None:
    niche = {
        "status": "validated_by_merchant",
        "forbidden_promises": [{"promise": "guérit", "reason": "health_claim"}],
        "brand_voice": {"do_not_say": []},
        "conversational_intents": [],
    }
    snapshot = {
        "snapshot_date": "2026-05-20T10:00:00",
        "products": [
            {
                "id": "gid://shopify/Product/1",
                "title": "Huile chien",
                "handle": "huile-chien",
                "status": "ACTIVE",
                "onlineStoreUrl": "https://test.myshopify.com/products/huile-chien",
                "description": "Cette huile guérit les problèmes de peau.",
            }
        ],
        "collections": [],
    }
    with (
        patch("app.api.audit._load_snapshot", return_value=snapshot),
        patch("app.api.audit.get_validated_niche_hypothesis", return_value=niche),
        patch("app.api.audit._load_crawl_findings", return_value=[]),
    ):
        client = _make_client()
        resp = client.get(f"/api/shops/{_SHOP}/audit/readiness")

    assert resp.status_code == 200
    data = resp.json()
    assert len(data["niche_alerts"]) > 0
    assert data["niche_alerts"][0]["type"] == "forbidden_promise"


def test_get_audit_readiness_with_crawl_findings(mock_env) -> None:
    findings = [
        {"url": "https://test.myshopify.com/products/harnais-chien", "issue_type": "page_404", "severity": "critical", "detail": "404"},
        {"url": "https://test.myshopify.com/collections/chiens", "issue_type": "redirect_chain", "severity": "high", "detail": "chain"},
    ]
    with (
        patch("app.api.audit._load_snapshot", return_value=_SNAPSHOT),
        patch("app.api.audit.get_validated_niche_hypothesis", return_value=None),
        patch("app.api.audit._load_crawl_findings", return_value=findings),
    ):
        client = _make_client()
        resp = client.get(f"/api/shops/{_SHOP}/audit/readiness")

    assert resp.status_code == 200
    data = resp.json()
    assert data["crawl_health"]["available"] is True
    assert data["crawl_health"]["critical"] == 1
    assert data["crawl_health"]["high"] == 1


def test_get_audit_readiness_freshness_warning_when_snapshot_old(mock_env) -> None:
    old_snapshot = {**_SNAPSHOT, "snapshot_date": "2025-01-01T00:00:00"}
    with (
        patch("app.api.audit._load_snapshot", return_value=old_snapshot),
        patch("app.api.audit.get_validated_niche_hypothesis", return_value=None),
        patch("app.api.audit._load_crawl_findings", return_value=[]),
    ):
        client = _make_client()
        resp = client.get(f"/api/shops/{_SHOP}/audit/readiness")

    assert resp.status_code == 200
    data = resp.json()
    assert data["snapshot_freshness_warning"] is True
    assert data["snapshot_age_days"] is not None
    assert data["snapshot_age_days"] > 7


def test_get_audit_readiness_no_snapshot_returns_404(mock_env) -> None:
    with (
        patch("app.api.audit._load_snapshot", side_effect=Exception("no snapshot")),
        patch("app.api.audit.get_validated_niche_hypothesis", return_value=None),
        patch("app.api.audit._load_crawl_findings", return_value=[]),
    ):
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get(f"/api/shops/{_SHOP}/audit/readiness")

    assert resp.status_code in {404, 500}


def test_geo_readiness_redirects_to_audit_readiness(mock_env) -> None:
    client = _make_client()
    resp = client.get(f"/api/shops/{_SHOP}/geo/readiness", follow_redirects=False)
    assert resp.status_code == 301
    assert f"/api/shops/{_SHOP}/audit/readiness" in resp.headers["location"]
