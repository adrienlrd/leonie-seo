"""Tests for GET /api/help/faq — bilingual FAQ endpoint."""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import app

_ENV = {
    "SHOPIFY_CLIENT_ID": "client_id",
    "SHOPIFY_CLIENT_SECRET": "client_secret",
    "SHOPIFY_SCOPES": "read_products",
    "APP_URL": "https://example.com",
}


@pytest.fixture()
def client():
    with patch.dict("os.environ", _ENV):
        yield TestClient(app)


def test_faq_returns_200(client: TestClient):
    resp = client.get("/api/help/faq")
    assert resp.status_code == 200


def test_faq_has_categories_and_items(client: TestClient):
    body = client.get("/api/help/faq").json()
    assert "categories" in body
    assert "items" in body
    assert len(body["categories"]) > 0
    assert len(body["items"]) > 0


def test_faq_default_lang_is_fr(client: TestClient):
    body = client.get("/api/help/faq").json()
    first = body["items"][0]
    assert "question" in first and "answer" in first
    # FR content contains French words
    assert any(
        word in first["question"].lower() or word in first["answer"].lower()
        for word in ("comment", "l'", "votre", "les", "est")
    )


def test_faq_lang_en_returns_english(client: TestClient):
    body = client.get("/api/help/faq?lang=en").json()
    questions = [i["question"] for i in body["items"]]
    # At least one item should contain typical English words
    assert any("how" in q.lower() or "what" in q.lower() or "can" in q.lower() for q in questions)


def test_faq_invalid_lang_falls_back_to_fr(client: TestClient):
    resp = client.get("/api/help/faq?lang=de")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["items"]) > 0


def test_faq_items_have_required_fields(client: TestClient):
    body = client.get("/api/help/faq").json()
    for item in body["items"]:
        assert "id" in item
        assert "category" in item
        assert "question" in item
        assert "answer" in item


def test_faq_categories_have_id_and_label(client: TestClient):
    body = client.get("/api/help/faq").json()
    for cat in body["categories"]:
        assert "id" in cat
        assert "label" in cat


def test_faq_items_categories_match_declared(client: TestClient):
    body = client.get("/api/help/faq").json()
    cat_ids = {c["id"] for c in body["categories"]}
    for item in body["items"]:
        assert item["category"] in cat_ids


def test_faq_has_apply_and_plans_categories(client: TestClient):
    body = client.get("/api/help/faq").json()
    cat_ids = {c["id"] for c in body["categories"]}
    assert "apply" in cat_ids
    assert "plans" in cat_ids


def _find(items: list[dict], item_id: str) -> dict:
    return next(i for i in items if i["id"] == item_id)


def test_faq_data_privacy_app_store_mode_mentions_neon(client: TestClient):
    """In app_store mode the data-privacy answer must mention Neon Postgres
    and NOT claim the tool is self-hosted (App Store review-safe wording)."""
    with patch.dict("os.environ", {"LEONIE_MODE": "app_store"}):
        body = client.get("/api/help/faq").json()
    answer = _find(body["items"], "data-privacy")["answer"]
    assert "Neon Postgres" in answer
    assert "auto-hébergé" not in answer


def test_faq_data_privacy_self_hosted_mode_mentions_self_hosted(client: TestClient):
    """In self_hosted mode the FAQ may claim self-hosted (it's true)."""
    with patch.dict("os.environ", {"LEONIE_MODE": "self_hosted"}):
        body = client.get("/api/help/faq").json()
    answer = _find(body["items"], "data-privacy")["answer"]
    assert "self-hosted" in answer or "auto-hébergé" in answer


def test_faq_theme_compatibility_no_longer_mentions_manual_liquid(client: TestClient):
    """The theme.liquid manual-edit guidance was wrong: hreflang/JSON-LD go
    through the Theme App Extension. The FAQ must reflect that."""
    body = client.get("/api/help/faq?lang=en").json()
    answer = _find(body["items"], "theme-compatibility")["answer"]
    assert "manually integrated into `theme.liquid`" not in answer
    assert "Theme App Extension" in answer
