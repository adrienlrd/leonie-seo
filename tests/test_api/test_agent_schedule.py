"""Tests for the daily GEO agent schedule API routes."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.agent_schedule.store import get_schedule
from app.db import init_db
from app.geo.ledger import create_geo_event
from app.learning.store import create_pending_approval, record_run
from app.main import app

SHOP = "schedule.myshopify.com"

ENV = {
    "LEONIE_REQUIRE_SESSION_TOKEN": "false",
    "SHOPIFY_STORE_DOMAIN": SHOP,
    "SHOPIFY_ACCESS_TOKEN": "shpat_test",
    "SHOPIFY_CLIENT_ID": "client_id",
    "SHOPIFY_CLIENT_SECRET": "client_secret",
    "SHOPIFY_SCOPES": "read_products,write_products",
    "APP_URL": "https://example.com",
    "INTERNAL_API_SECRET": "internal-secret",
    "AGENT_SCHEDULE_TICKER": "false",
}


@pytest.fixture()
def db(tmp_path: Path) -> Path:
    path = tmp_path / "agent-schedule-api.db"
    init_db(path)
    return path


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch, db: Path) -> TestClient:
    for key, value in ENV.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setattr("app.api.agent_schedule.DB_PATH", db)
    with (
        patch("app.api.deps.get_token", return_value=None),
        patch("app.api.deps.get_plan_for_shop", return_value="pro"),
    ):
        yield TestClient(app)


def test_status_defaults_disabled(client: TestClient) -> None:
    response = client.get(f"/api/shops/{SHOP}/agent-schedule/status")

    assert response.status_code == 200
    body = response.json()
    assert body["enabled"] is False
    assert body["mode"] == "semi_auto"


def test_put_settings_enables_daily(client: TestClient, db: Path) -> None:
    response = client.put(
        f"/api/shops/{SHOP}/agent-schedule/settings",
        json={"enabled": True, "mode": "semi_auto", "local_time": "08:00"},
    )

    assert response.status_code == 200
    schedule = response.json()["schedule"]
    assert schedule["enabled"] is True
    assert schedule["next_run_at"] is not None
    assert get_schedule(SHOP, db_path=db).enabled is True


def test_put_settings_rejects_invalid_time(client: TestClient) -> None:
    response = client.put(
        f"/api/shops/{SHOP}/agent-schedule/settings",
        json={"enabled": True, "local_time": "99:99"},
    )

    assert response.status_code == 422


def test_disable_endpoint(client: TestClient, db: Path) -> None:
    client.put(
        f"/api/shops/{SHOP}/agent-schedule/settings",
        json={"enabled": True, "mode": "semi_auto"},
    )

    response = client.post(f"/api/shops/{SHOP}/agent-schedule/disable")

    assert response.status_code == 200
    assert response.json()["schedule"]["enabled"] is False
    assert get_schedule(SHOP, db_path=db).enabled is False


def test_test_in_5_min_sets_test_without_enabling(client: TestClient, db: Path) -> None:
    response = client.post(f"/api/shops/{SHOP}/agent-schedule/test-in-5-min")

    assert response.status_code == 200
    schedule = response.json()["schedule"]
    assert schedule["test_run_at"] is not None
    assert schedule["enabled"] is False


def test_export_contains_all_sections(client: TestClient, db: Path) -> None:
    record_run(
        shop=SHOP,
        status="completed",
        observations_created=1,
        weights_updated=2,
        actions_reprioritized=3,
        approvals_created=1,
        auto_applied_count=0,
        errors=[],
        db_path=db,
    )
    create_pending_approval(
        shop=SHOP,
        resource_type="product",
        resource_id="gid://shopify/Product/1",
        action_type="meta_title",
        field="meta_title",
        old_value="Old",
        proposed_value="New",
        confidence_score=88,
        risk_level="low",
        expected_impact={"score_delta": 8},
        explanation={"reason": "safe"},
        db_path=db,
    )
    create_geo_event(
        shop=SHOP,
        event_type="continuous_improvement_proposal",
        resource_type="product",
        resource_id="gid://shopify/Product/1",
        resource_title="Harnais",
        action_type="meta_title",
        before_snapshot={},
        metrics_before={},
        estimated_impact={},
        db_path=db,
    )

    response = client.get(f"/api/shops/{SHOP}/agent-schedule/export")

    assert response.status_code == 200
    body = response.json()
    assert body["shop"] == SHOP
    assert body["settings"]["schedule"] is not None
    assert body["settings"]["learning"] is not None
    assert len(body["learning_runs"]) == 1
    assert len(body["pending_approvals"]) == 1
    assert len(body["geo_events"]) == 1
    assert "agent_runs" in body
    assert "events" in body


def test_effectiveness_endpoint_returns_verdicts(client: TestClient) -> None:
    response = client.get(f"/api/shops/{SHOP}/agent-schedule/effectiveness")

    assert response.status_code == 200
    body = response.json()
    assert body["seo"]["verdict"] in {"improving", "regressing", "no_effect", "inconclusive"}
    assert body["geo"]["verdict"] in {"improving", "regressing", "no_effect", "inconclusive"}
    assert len(body["recommendations"]) >= 1


def test_export_includes_effectiveness(client: TestClient) -> None:
    response = client.get(f"/api/shops/{SHOP}/agent-schedule/export")

    assert response.status_code == 200
    assert response.json()["effectiveness"] is not None


def test_internal_run_due_requires_secret(client: TestClient) -> None:
    unauth = client.post("/api/internal/agent-schedule/run-due")
    assert unauth.status_code == 403

    response = client.post(
        "/api/internal/agent-schedule/run-due",
        headers={"X-Internal-Secret": "internal-secret"},
    )
    assert response.status_code == 200
    body = response.json()
    assert "ran" in body and "skipped" in body
