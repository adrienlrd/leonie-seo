"""Tests for the learning API routes."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.db import init_db
from app.learning.store import (
    create_observation,
    create_pending_approval,
    record_decision,
    upsert_weight,
)
from app.main import app

SHOP = "learn.myshopify.com"

ENV = {
    "LEONIE_REQUIRE_SESSION_TOKEN": "false",
    "SHOPIFY_STORE_DOMAIN": SHOP,
    "SHOPIFY_ACCESS_TOKEN": "shpat_test",
    "SHOPIFY_CLIENT_ID": "client_id",
    "SHOPIFY_CLIENT_SECRET": "client_secret",
    "SHOPIFY_SCOPES": "read_products,write_products",
    "APP_URL": "https://example.com",
    "INTERNAL_API_SECRET": "internal-secret",
}


@pytest.fixture()
def db(tmp_path: Path) -> Path:
    path = tmp_path / "learning-api.db"
    init_db(path)
    return path


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch, db: Path) -> TestClient:
    for key, value in ENV.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setattr("app.api.learning.DB_PATH", db)
    with (
        patch("app.api.deps.get_token", return_value=None),
        patch("app.api.deps.get_plan_for_shop", return_value="pro"),
    ):
        yield TestClient(app)


def _approval(db: Path, *, field: str = "meta_title", risk: str = "low") -> int:
    return create_pending_approval(
        shop=SHOP,
        resource_type="product",
        resource_id="gid://shopify/Product/1",
        action_type=field,
        field=field,
        old_value="Old",
        proposed_value="New",
        confidence_score=88,
        risk_level=risk,
        expected_impact={"score_delta": 8},
        explanation={"reason": "High confidence safe update."},
        db_path=db,
    )


def test_get_learning_status_returns_default_settings(client: TestClient) -> None:
    response = client.get(f"/api/shops/{SHOP}/learning/status")

    assert response.status_code == 200
    body = response.json()
    assert body["shop"] == SHOP
    assert body["settings"]["mode"] == "semi_auto"
    assert body["settings"]["enabled"] is True


def test_list_learning_weights_observations_and_decisions(
    client: TestClient,
    db: Path,
) -> None:
    upsert_weight(
        scope="merchant",
        shop=SHOP,
        feature_key="action_type",
        feature_value="meta_title",
        weight=0.42,
        sample_size=4,
        confidence=61,
        db_path=db,
    )
    create_observation(
        shop=SHOP,
        resource_type="product",
        resource_id="gid://shopify/Product/1",
        action_type="meta_title",
        surface="product_page",
        keyword_source="gsc",
        before_metrics={"clicks": 10},
        after_metrics={"clicks": 18},
        control_metrics={},
        window_days=28,
        window_label="J+28",
        is_primary_window=True,
        outcome_score=35,
        confidence_score=82,
        db_path=db,
    )
    record_decision(
        shop=SHOP,
        resource_id="gid://shopify/Product/1",
        action_type="meta_title",
        previous_score=50,
        learning_score=8,
        final_score=72,
        mode="semi_auto",
        approval_required=True,
        risk_level="low",
        explanation={"summary": "Learning boost."},
        db_path=db,
    )

    weights = client.get(f"/api/shops/{SHOP}/learning/weights")
    observations = client.get(f"/api/shops/{SHOP}/learning/observations")
    decisions = client.get(f"/api/shops/{SHOP}/learning/decisions")

    assert weights.status_code == 200
    assert observations.status_code == 200
    assert decisions.status_code == 200
    assert weights.json()["weights"][0]["feature_value"] == "meta_title"
    assert observations.json()["observations"][0]["is_primary_window"] is True
    assert decisions.json()["decisions"][0]["approval_required"] is True


def test_update_learning_settings_accepts_only_two_modes(client: TestClient) -> None:
    ok = client.put(
        f"/api/shops/{SHOP}/learning/settings",
        json={"mode": "auto_apply", "min_confidence_to_auto_apply": 91},
    )
    rejected = client.put(f"/api/shops/{SHOP}/learning/settings", json={"mode": "manual"})

    assert ok.status_code == 200
    assert ok.json()["settings"]["mode"] == "auto_apply"
    assert rejected.status_code == 422


def test_update_learning_settings_accepts_reanalysis_and_publish_scopes(client: TestClient) -> None:
    resp = client.put(
        f"/api/shops/{SHOP}/learning/settings",
        json={"reanalysis_frequency_days": 14, "auto_publish_scopes": ["meta_title", "alt_text"]},
    )

    assert resp.status_code == 200
    settings = resp.json()["settings"]
    assert settings["reanalysis_frequency_days"] == 14
    assert settings["auto_publish_scopes"] == ["meta_title", "alt_text"]


def test_learning_run_endpoint_delegates_to_scheduler(client: TestClient) -> None:
    with patch(
        "app.api.learning.run_learning_cycle",
        return_value={
            "status": "completed",
            "observations_created": 1,
            "weights_updated": 2,
            "actions_reprioritized": 3,
            "approvals_created": 4,
            "auto_applied_count": 0,
            "errors": [],
        },
    ) as run_cycle:
        response = client.post(
            f"/api/shops/{SHOP}/learning/run",
            json={"confirm_live_write": False, "max_actions": 3},
        )

    assert response.status_code == 200
    assert response.json()["status"] == "completed"
    run_cycle.assert_called_once()


def test_pending_approvals_endpoints_cover_approve_reject_edit_and_bulk(
    client: TestClient,
    db: Path,
) -> None:
    approval_id = _approval(db)
    listed = client.get(f"/api/shops/{SHOP}/learning/pending-approvals")

    assert listed.status_code == 200
    assert listed.json()["approvals"][0]["id"] == approval_id

    with patch("app.api.learning.apply_approval", return_value={"applied": True}) as apply_mock:
        approved = client.post(
            f"/api/shops/{SHOP}/learning/approvals/{approval_id}/approve",
            json={"confirm_live_write": True},
        )
    assert approved.status_code == 200
    apply_mock.assert_called_once()

    rejected_id = _approval(db, field="meta_description")
    rejected = client.post(f"/api/shops/{SHOP}/learning/approvals/{rejected_id}/reject")
    assert rejected.status_code == 200
    assert rejected.json()["approval"]["status"] == "rejected"

    edited_id = _approval(db, field="product_description")
    edited = client.patch(
        f"/api/shops/{SHOP}/learning/approvals/{edited_id}/edit",
        json={"proposed_value": "Edited value"},
    )
    assert edited.status_code == 200
    assert edited.json()["approval"]["status"] == "edited"
    assert edited.json()["approval"]["proposed_value"] == "Edited value"

    with patch(
        "app.api.learning.bulk_approve_safe",
        return_value={"applied": 1, "skipped": 0, "errors": []},
    ) as bulk_mock:
        bulk = client.post(
            f"/api/shops/{SHOP}/learning/approvals/bulk-approve-safe",
            json={"confirm_live_write": True},
        )
    assert bulk.status_code == 200
    assert bulk.json()["applied"] == 1
    bulk_mock.assert_called_once()


def test_learning_approve_returns_422_for_missing_approval(client: TestClient) -> None:
    response = client.post(
        f"/api/shops/{SHOP}/learning/approvals/999/approve",
        json={"confirm_live_write": True},
    )

    assert response.status_code == 422


def test_internal_learning_run_requires_secret(client: TestClient) -> None:
    blocked = client.post("/api/internal/learning/run")

    with patch(
        "app.api.learning.run_all_installed_shops",
        return_value={"shops_seen": 1, "runs": [{"shop": SHOP, "status": "completed"}]},
    ) as run_all:
        allowed = client.post(
            "/api/internal/learning/run",
            headers={"X-Internal-Secret": ENV["INTERNAL_API_SECRET"]},
        )

    assert blocked.status_code == 403
    assert allowed.status_code == 200
    assert allowed.json()["shops_seen"] == 1
    run_all.assert_called_once()
