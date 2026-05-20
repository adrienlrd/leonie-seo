"""Tests for the Content Actions API endpoints."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import app

_SHOP = "testshop.myshopify.com"

_RUN_BODY = {
    "content_type": "meta_title",
    "resource": {
        "id": "gid://shopify/Product/101",
        "type": "product",
        "handle": "harnais-nylon",
        "title": "Harnais nylon chien",
    },
}

_RESULT_JSON = {
    "action_id": "test-action-123",
    "content_type": "meta_title",
    "resource_id": "gid://shopify/Product/101",
    "generated_at": "2026-05-20T12:00:00+00:00",
    "output": {"primary_text": "Harnais nylon chien réglable — confort quotidien", "structured": None},
    "facts_used": [],
    "claims_unverified": [],
    "queries_targeted": [],
    "intents_targeted": [],
    "constraints_check": {
        "length_ok": True,
        "language_ok": True,
        "forbidden_promise_violations": [],
        "do_not_say_violations": [],
    },
    "quality": {"score": 65, "label": "bon"},
    "status": "draft",
    "llm_meta": {
        "tier": "low-cost",
        "provider": "openai",
        "model": "gpt-4o-mini",
        "prompt_version": "2.0",
        "tokens_in": 0,
        "tokens_out": 0,
        "cost_usd": 0.0,
        "cache_hit": False,
    },
}


def _make_client() -> TestClient:
    return TestClient(app, raise_server_exceptions=True)


@pytest.fixture()
def mock_env(monkeypatch):
    monkeypatch.setenv("LEONIE_REQUIRE_SESSION_TOKEN", "false")
    monkeypatch.setenv("SHOPIFY_STORE_DOMAIN", _SHOP)
    monkeypatch.setenv("SHOPIFY_ACCESS_TOKEN", "test-token")


def _make_result_obj():
    from app.content_actions.schema import ContentActionResult  # noqa: PLC0415
    return ContentActionResult.model_validate(_RESULT_JSON)


def test_run_action_returns_schema(mock_env) -> None:
    with (
        patch("app.api.content_actions.get_validated_niche_hypothesis", return_value=None),
        patch("app.api.content_actions.run_content_action", return_value=_make_result_obj()),
    ):
        client = _make_client()
        resp = client.post(f"/api/shops/{_SHOP}/content-actions/run", json=_RUN_BODY)
    assert resp.status_code == 200
    data = resp.json()
    assert "action_id" in data
    assert "output" in data
    assert "status" in data


def test_run_action_422_on_missing_niche(mock_env) -> None:
    with (
        patch("app.api.content_actions.get_validated_niche_hypothesis", return_value=None),
        patch(
            "app.api.content_actions.run_content_action",
            side_effect=ValueError("requires a merchant-validated niche hypothesis"),
        ),
    ):
        client = _make_client()
        body = {**_RUN_BODY, "content_type": "product_description"}
        resp = client.post(f"/api/shops/{_SHOP}/content-actions/run", json=body)
    assert resp.status_code == 422


def test_get_action_not_found(mock_env) -> None:
    with patch("app.api.content_actions._load_action", return_value=None):
        client = _make_client()
        resp = client.get(f"/api/shops/{_SHOP}/content-actions/nonexistent-id")
    assert resp.status_code == 404


def test_get_action_returns_result(mock_env) -> None:
    with patch("app.api.content_actions._load_action", return_value=_make_result_obj()):
        client = _make_client()
        resp = client.get(f"/api/shops/{_SHOP}/content-actions/test-action-123")
    assert resp.status_code == 200
    assert resp.json()["action_id"] == "test-action-123"


def test_retry_action_422_on_max_retries(mock_env) -> None:
    with (
        patch("app.api.content_actions.get_validated_niche_hypothesis", return_value=None),
        patch(
            "app.api.content_actions.retry_content_action",
            side_effect=ValueError("Maximum 3 retries reached"),
        ),
    ):
        client = _make_client()
        resp = client.post(
            f"/api/shops/{_SHOP}/content-actions/test-action-123/retry",
            json={"feedback": "Trop générique"},
        )
    assert resp.status_code == 422


def test_export_action_returns_json(mock_env) -> None:
    with (
        patch("app.api.content_actions._load_action", return_value=_make_result_obj()),
        patch("app.api.content_actions._update_action_status"),
    ):
        client = _make_client()
        resp = client.post(
            f"/api/shops/{_SHOP}/content-actions/test-action-123/export",
            json={"format": "json"},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["format"] == "json"
    assert "output" in data
