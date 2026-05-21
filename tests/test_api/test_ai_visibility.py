"""Tests for the AI Visibility status endpoint."""

from __future__ import annotations

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


def test_ai_visibility_status_returns_disabled(mock_env) -> None:
    client = _make_client()
    resp = client.get(f"/api/shops/{_SHOP}/ai-visibility/status")
    assert resp.status_code == 200
    body = resp.json()
    assert body["enabled"] is False


def test_ai_visibility_status_returns_v2_info(mock_env) -> None:
    client = _make_client()
    resp = client.get(f"/api/shops/{_SHOP}/ai-visibility/status")
    body = resp.json()
    assert body["available_in"] == "v2"
    assert body["axis"] == "ai_visibility"


def test_ai_visibility_status_returns_messages(mock_env) -> None:
    client = _make_client()
    resp = client.get(f"/api/shops/{_SHOP}/ai-visibility/status")
    body = resp.json()
    assert "message_fr" in body
    assert "message_en" in body
    assert len(body["message_fr"]) > 20
    assert len(body["message_en"]) > 20
