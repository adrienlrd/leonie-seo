"""Tests for Niche Understanding API endpoints."""

from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app

SHOP = "store.myshopify.com"

ENV = {
    "SHOPIFY_STORE_DOMAIN": SHOP,
    "SHOPIFY_ACCESS_TOKEN": "shpat_test",
    "SHOPIFY_CLIENT_ID": "client_id",
    "SHOPIFY_CLIENT_SECRET": "client_secret",
    "SHOPIFY_SCOPES": "read_products",
    "APP_URL": "https://app.example.com",
    "INTERNAL_API_SECRET": "internal",
}

HEADERS = {
    "X-Leonie-Shop": SHOP,
    "X-Internal-Secret": "internal",
    "X-Shopify-Access-Token": "shpat_test",
}


def _hypothesis(status: str = "needs_review") -> dict:
    return {
        "status": status,
        "shop_summary": {
            "what_you_sell": "Des accessoires chien.",
            "primary_niche": "Accessoires chien",
            "sub_niches": ["Harnais"],
            "languages_detected": ["fr"],
            "markets_detected": ["FR"],
        },
        "customer_segments": [],
        "buying_motivations": [],
        "objections": [],
        "priority_products": [],
        "marketing_angles": [],
        "conversational_intents": [],
        "probable_competitors": [],
        "brand_voice": {
            "tone": "clair",
            "register": "professional",
            "do_say": [],
            "do_not_say": [],
            "confidence": "medium",
        },
        "forbidden_promises": [],
        "global_confidence": "medium",
        "missing_inputs": [],
    }


def test_post_niche_understand_generates_hypothesis(monkeypatch) -> None:
    monkeypatch.setenv("INTERNAL_API_SECRET", "internal")
    with (
        patch.dict("os.environ", ENV),
        patch("app.api.niche._load_snapshot", return_value=[{"title": "Harnais"}]),
        patch("app.api.niche._load_gsc", return_value=[]),
        patch("app.api.niche.generate_niche_hypothesis", return_value=_hypothesis()),
        patch("app.api.niche.get_niche_hypothesis_history", return_value=[]),
    ):
        resp = TestClient(app).post(
            f"/api/shops/{SHOP}/niche/understand",
            headers=HEADERS,
            json={"force_refresh": True, "use_llm": False},
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["available"] is True
    assert body["hypothesis"]["status"] == "needs_review"


def test_post_niche_understand_returns_404_without_inputs(monkeypatch) -> None:
    monkeypatch.setenv("INTERNAL_API_SECRET", "internal")
    with (
        patch.dict("os.environ", ENV),
        patch("app.api.niche._load_snapshot", return_value=[]),
        patch("app.api.niche._load_gsc", return_value=[]),
    ):
        resp = TestClient(app).post(
            f"/api/shops/{SHOP}/niche/understand",
            headers=HEADERS,
            json={},
        )

    assert resp.status_code == 404


def test_get_niche_hypothesis_returns_stored_payload(monkeypatch) -> None:
    monkeypatch.setenv("INTERNAL_API_SECRET", "internal")
    with (
        patch.dict("os.environ", ENV),
        patch("app.api.niche.get_niche_hypothesis", return_value=_hypothesis("validated_by_merchant")),
        patch("app.api.niche.get_niche_hypothesis_history", return_value=[_hypothesis()]),
    ):
        resp = TestClient(app).get(f"/api/shops/{SHOP}/niche/hypothesis", headers=HEADERS)

    assert resp.status_code == 200
    body = resp.json()
    assert body["available"] is True
    assert body["hypothesis"]["status"] == "validated_by_merchant"
    assert len(body["history"]) == 1


def test_patch_niche_hypothesis_persists_merchant_status(monkeypatch) -> None:
    monkeypatch.setenv("INTERNAL_API_SECRET", "internal")
    saved = _hypothesis("validated_by_merchant")
    with (
        patch.dict("os.environ", ENV),
        patch("app.api.niche.save_niche_hypothesis", return_value=saved) as save,
        patch("app.api.niche.get_niche_hypothesis_history", return_value=[]),
    ):
        resp = TestClient(app).patch(
            f"/api/shops/{SHOP}/niche/hypothesis",
            headers=HEADERS,
            json={"hypothesis": _hypothesis(), "status": "validated_by_merchant"},
        )

    assert resp.status_code == 200
    assert resp.json()["hypothesis"]["status"] == "validated_by_merchant"
    assert save.call_args.args[1]["status"] == "validated_by_merchant"
