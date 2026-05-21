"""Tests for the Safe Apply API routes."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.content_actions.schema import (
    ConstraintsCheck,
    ContentActionResult,
    ContentOutput,
    ContentStatus,
    ContentType,
    QualityResult,
)
from app.main import app

_SHOP = "testshop.myshopify.com"


def _make_client() -> TestClient:
    return TestClient(app, raise_server_exceptions=True)


@pytest.fixture()
def mock_env(monkeypatch):
    monkeypatch.setenv("LEONIE_REQUIRE_SESSION_TOKEN", "false")
    monkeypatch.setenv("SHOPIFY_STORE_DOMAIN", _SHOP)
    monkeypatch.setenv("SHOPIFY_ACCESS_TOKEN", "test-token")


def _make_result(
    status: ContentStatus = ContentStatus.APPROVED,
    violations: list[str] | None = None,
    length_ok: bool = True,
) -> ContentActionResult:
    return ContentActionResult(
        action_id="act-1",
        content_type=ContentType.META_TITLE,
        resource_id="gid://shopify/Product/1",
        generated_at="2026-05-21T10:00:00+00:00",
        output=ContentOutput(primary_text="Harnais chien nylon réglable"),
        constraints_check=ConstraintsCheck(
            length_ok=length_ok,
            forbidden_promise_violations=violations or [],
        ),
        quality=QualityResult(score=75, label="bon"),
        status=status,
    )


# ── GET /diff ─────────────────────────────────────────────────────────────────


def test_get_diff_returns_schema(mock_env) -> None:
    result = _make_result()
    with patch("app.safe_apply.diff._load_action", return_value=result):
        client = _make_client()
        resp = client.get(
            f"/api/shops/{_SHOP}/safe-apply/diff",
            params={"action_id": "act-1"},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["action_id"] == "act-1"
    assert "decision_state" in body
    assert "merchant_view" in body


def test_get_diff_returns_404_when_not_found(mock_env) -> None:
    with patch("app.safe_apply.diff._load_action", return_value=None):
        client = _make_client()
        resp = client.get(
            f"/api/shops/{_SHOP}/safe-apply/diff",
            params={"action_id": "ghost"},
        )
    assert resp.status_code == 404


# ── POST /decision ────────────────────────────────────────────────────────────


def test_decision_accept_returns_approved(mock_env) -> None:
    result = _make_result(status=ContentStatus.DRAFT)
    with (
        patch("app.content_actions.runner._load_action", return_value=result),
        patch("app.content_actions.runner._update_action_status"),
        patch("app.safe_apply.decisions._retry_count", return_value=0),
        patch("app.safe_apply.decisions._insert_decision"),
    ):
        client = _make_client()
        resp = client.post(
            f"/api/shops/{_SHOP}/safe-apply/decision",
            json={"action_id": "act-1", "decision": "accept"},
        )
    assert resp.status_code == 200
    assert resp.json()["new_status"] == ContentStatus.APPROVED.value


def test_decision_accept_blocked_returns_422(mock_env) -> None:
    result = _make_result(violations=["guérit"])
    with (
        patch("app.content_actions.runner._load_action", return_value=result),
        patch("app.safe_apply.decisions._retry_count", return_value=0),
    ):
        client = _make_client()
        resp = client.post(
            f"/api/shops/{_SHOP}/safe-apply/decision",
            json={"action_id": "act-1", "decision": "accept"},
        )
    assert resp.status_code == 422


# ── POST /dry-run ─────────────────────────────────────────────────────────────


def test_dry_run_returns_preview(mock_env) -> None:
    result = _make_result(status=ContentStatus.APPROVED)
    with patch("app.api.safe_apply._load_action", return_value=result):
        client = _make_client()
        resp = client.post(
            f"/api/shops/{_SHOP}/safe-apply/dry-run",
            json={"action_id": "act-1"},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["dry_run"] is True
    assert body["would_succeed"] is True
    assert "seo.title" in body["would_change_fields"]


def test_dry_run_blocked_when_not_approved(mock_env) -> None:
    result = _make_result(status=ContentStatus.DRAFT)
    with patch("app.api.safe_apply._load_action", return_value=result):
        client = _make_client()
        resp = client.post(
            f"/api/shops/{_SHOP}/safe-apply/dry-run",
            json={"action_id": "act-1"},
        )
    assert resp.status_code == 422


# ── POST /live ────────────────────────────────────────────────────────────────


def test_live_apply_blocked_for_free_plan(mock_env) -> None:
    client = _make_client()
    resp = client.post(
        f"/api/shops/{_SHOP}/safe-apply/live?plan=free",
        json={"action_id": "act-1", "confirm_live_write": True},
    )
    assert resp.status_code == 403


def test_live_apply_blocked_without_confirmation(mock_env) -> None:
    result = _make_result(status=ContentStatus.APPROVED)
    with (
        patch("app.api.safe_apply._load_action", return_value=result),
        patch("app.api.safe_apply.get_features") as mock_features,
    ):
        mock_features.return_value.can_apply = True
        client = _make_client()
        resp = client.post(
            f"/api/shops/{_SHOP}/safe-apply/live?plan=pro",
            json={"action_id": "act-1", "confirm_live_write": False},
        )
    assert resp.status_code == 409


def test_live_apply_pilot_safe_mode_blocked(mock_env, monkeypatch) -> None:
    monkeypatch.setenv("LEONIE_PILOT_SAFE_MODE", "true")
    result = _make_result(status=ContentStatus.APPROVED)
    with (
        patch("app.api.safe_apply._load_action", return_value=result),
        patch("app.api.safe_apply.get_features") as mock_features,
    ):
        mock_features.return_value.can_apply = True
        client = _make_client()
        resp = client.post(
            f"/api/shops/{_SHOP}/safe-apply/live?plan=pro",
            json={"action_id": "act-1", "confirm_live_write": True},
        )
    assert resp.status_code == 403
