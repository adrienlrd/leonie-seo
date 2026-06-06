"""Tests for semantic analysis and E-E-A-T scoring endpoint."""

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
            "title": "Harnais Chien",
            "handle": "harnais-chien",
            "seo": {"title": None, "description": None},
            "description": "",
            "images": {"edges": []},
        },
        {
            "id": "gid://shopify/Product/2",
            "title": "Collier Garantie Chat",
            "handle": "collier-chat",
            "seo": {
                "title": "Collier élégant pour chat — boutique Giulio Geo",
                "description": "Découvrez notre collier pour chat, élégant, résistant et certifié vétérinaire. Livraison garantie.",
            },
            "description": "Un collier de qualité certifié, fabriqué avec des matières résistantes. Recommandé par les vétérinaires. Satisfaction garantie ou remboursé. Livraison rapide et service client disponible.",
            "images": {"edges": []},
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
    p = tmp_path / "shopify_snapshot.json"
    p.write_text(json.dumps(_SNAPSHOT))
    return p


def test_semantics_returns_products(client, snapshot_file) -> None:
    with (
        patch("app.api.deps.get_token", return_value=None),
        patch("app.api.deps._SNAPSHOT_DEFAULT", snapshot_file),
        patch("app.api.semantics.load_snapshot_from_file_or_db", return_value=_SNAPSHOT),
    ):
        resp = client.get(f"/api/shops/{SHOP}/audit/semantics")

    assert resp.status_code == 200
    data = resp.json()
    assert data["available"] is True
    assert data["total"] == 2
    assert len(data["products"]) == 2


def test_semantics_scores_present(client, snapshot_file) -> None:
    with (
        patch("app.api.deps.get_token", return_value=None),
        patch("app.api.deps._SNAPSHOT_DEFAULT", snapshot_file),
        patch("app.api.semantics.load_snapshot_from_file_or_db", return_value=_SNAPSHOT),
    ):
        resp = client.get(f"/api/shops/{SHOP}/audit/semantics")

    products = resp.json()["products"]
    for p in products:
        assert "global_score" in p
        assert "eeat_global" in p
        assert "experience_score" in p
        assert "expertise_score" in p
        assert "authority_score" in p
        assert "trust_score" in p
        assert "content_score" in p
        assert "recommendations" in p


def test_semantics_empty_product_worse_than_rich(client, snapshot_file) -> None:
    with (
        patch("app.api.deps.get_token", return_value=None),
        patch("app.api.deps._SNAPSHOT_DEFAULT", snapshot_file),
        patch("app.api.semantics.load_snapshot_from_file_or_db", return_value=_SNAPSHOT),
    ):
        resp = client.get(f"/api/shops/{SHOP}/audit/semantics")

    products = resp.json()["products"]
    by_handle = {p["handle"]: p for p in products}
    # Harnais (empty) should score lower than Collier (rich description with trust signals)
    assert by_handle["harnais-chien"]["global_score"] < by_handle["collier-chat"]["global_score"]


def test_semantics_empty_desc_flagged(client, snapshot_file) -> None:
    with (
        patch("app.api.deps.get_token", return_value=None),
        patch("app.api.deps._SNAPSHOT_DEFAULT", snapshot_file),
        patch("app.api.semantics.load_snapshot_from_file_or_db", return_value=_SNAPSHOT),
    ):
        resp = client.get(f"/api/shops/{SHOP}/audit/semantics")

    products = resp.json()["products"]
    empty_p = next(p for p in products if p["handle"] == "harnais-chien")
    assert empty_p["desc_grade"] == "missing"
    assert empty_p["word_count"] == 0
    assert len(empty_p["recommendations"]) > 0


def test_semantics_seo_issues_detected(client, snapshot_file) -> None:
    with (
        patch("app.api.deps.get_token", return_value=None),
        patch("app.api.deps._SNAPSHOT_DEFAULT", snapshot_file),
        patch("app.api.semantics.load_snapshot_from_file_or_db", return_value=_SNAPSHOT),
    ):
        resp = client.get(f"/api/shops/{SHOP}/audit/semantics")

    products = resp.json()["products"]
    harnais = next(p for p in products if p["handle"] == "harnais-chien")
    assert "missing_meta_title" in harnais["seo_issues"]
    assert "missing_meta_description" in harnais["seo_issues"]


def test_semantics_summary_present(client, snapshot_file) -> None:
    with (
        patch("app.api.deps.get_token", return_value=None),
        patch("app.api.deps._SNAPSHOT_DEFAULT", snapshot_file),
        patch("app.api.semantics.load_snapshot_from_file_or_db", return_value=_SNAPSHOT),
    ):
        resp = client.get(f"/api/shops/{SHOP}/audit/semantics")

    summary = resp.json()["summary"]
    assert "avg_global_score" in summary
    assert "avg_eeat_score" in summary
    assert "products_needing_description" in summary
    assert "products_with_seo_issues" in summary
    assert summary["products_needing_description"] >= 1


def test_semantics_sorted_worst_first(client, snapshot_file) -> None:
    with (
        patch("app.api.deps.get_token", return_value=None),
        patch("app.api.deps._SNAPSHOT_DEFAULT", snapshot_file),
        patch("app.api.semantics.load_snapshot_from_file_or_db", return_value=_SNAPSHOT),
    ):
        resp = client.get(f"/api/shops/{SHOP}/audit/semantics")

    products = resp.json()["products"]
    scores = [p["global_score"] for p in products]
    assert scores == sorted(scores)


def test_semantics_no_snapshot_returns_404(client, tmp_path) -> None:
    with (
        patch("app.api.deps.get_token", return_value=None),
        patch("app.api.deps._SNAPSHOT_DEFAULT", tmp_path / "missing.json"),
        patch("app.api.semantics.load_snapshot_from_file_or_db", return_value=None),
    ):
        resp = client.get(f"/api/shops/{SHOP}/audit/semantics")

    assert resp.status_code == 404


def test_score_product_unit() -> None:
    from app.api.semantics import _score_product

    p = {
        "id": "gid://shopify/Product/99",
        "title": "Produit Test",
        "handle": "produit-test",
        "seo": {"title": "Produit test — boutique", "description": "Une belle description de produit pour le test."},
        "description": "Un produit fabriqué avec soin, garanti et recommandé. Service client disponible. Livraison rapide.",
    }
    result = _score_product(p)
    assert 0.0 <= result["global_score"] <= 1.0
    assert 0.0 <= result["eeat_global"] <= 1.0
    assert isinstance(result["recommendations"], list)
    assert result["desc_grade"] in ("missing", "too_short", "short", "ok")
