"""Tests for learning persistence helpers."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.db import init_db
from app.learning.models import ApprovalStatus, LearningMode
from app.learning.store import (
    create_observation,
    create_pending_approval,
    get_settings,
    list_decisions,
    list_observations,
    list_pending_approvals,
    list_runs,
    list_weights,
    observation_exists,
    record_decision,
    record_run,
    update_approval_status,
    update_settings,
    upsert_weight,
)

SHOP = "store.myshopify.com"


def test_get_settings_creates_semi_auto_defaults(tmp_path: Path) -> None:
    db = tmp_path / "history.db"
    init_db(db)

    settings = get_settings(SHOP, db_path=db)

    assert settings.enabled is True
    assert settings.mode == LearningMode.SEMI_AUTO
    assert settings.min_confidence_to_auto_apply == 80


def test_update_settings_rejects_unknown_mode(tmp_path: Path) -> None:
    db = tmp_path / "history.db"
    init_db(db)

    with pytest.raises(ValueError):
        update_settings(SHOP, {"mode": "manual"}, db_path=db)


def test_create_and_list_observation_round_trips_json(tmp_path: Path) -> None:
    db = tmp_path / "history.db"
    init_db(db)

    observation_id = create_observation(
        shop=SHOP,
        ledger_event_id=12,
        resource_type="product",
        resource_id="p1",
        action_type="meta_title",
        surface="product_page",
        keyword_source="gsc",
        before_metrics={"gsc": {"impressions": 10}},
        after_metrics={"gsc": {"impressions": 20}},
        control_metrics={"impressions_before": 10, "impressions_after": 11},
        window_days=28,
        window_label="J+28",
        is_primary_window=True,
        outcome_score=42,
        confidence_score=80,
        metadata={"experiment_verdict": "positive_high_confidence"},
        db_path=db,
    )

    rows = list_observations(SHOP, db_path=db)
    assert observation_id > 0
    assert rows[0]["ledger_event_id"] == 12
    assert rows[0]["before_metrics"]["gsc"]["impressions"] == 10
    assert rows[0]["is_primary_window"] is True
    assert rows[0]["metadata"]["experiment_verdict"] == "positive_high_confidence"
    assert observation_exists(
        shop=SHOP,
        resource_id="p1",
        action_type="meta_title",
        window_label="J+28",
        db_path=db,
    )


def test_observation_exists_can_scope_to_ledger_event_id(tmp_path: Path) -> None:
    db = tmp_path / "history.db"
    init_db(db)
    create_observation(
        shop=SHOP,
        ledger_event_id=12,
        resource_type="product",
        resource_id="p1",
        action_type="meta_title",
        surface="product_page",
        keyword_source="gsc",
        before_metrics={},
        after_metrics={},
        control_metrics={},
        window_days=28,
        window_label="J+28",
        is_primary_window=True,
        outcome_score=0,
        confidence_score=40,
        db_path=db,
    )

    assert observation_exists(
        shop=SHOP,
        ledger_event_id=12,
        resource_id="p1",
        action_type="meta_title",
        window_label="J+28",
        db_path=db,
    )
    assert not observation_exists(
        shop=SHOP,
        ledger_event_id=13,
        resource_id="p1",
        action_type="meta_title",
        window_label="J+28",
        db_path=db,
    )


def test_weight_decision_run_and_approval_lists_return_serialized_payloads(
    tmp_path: Path,
) -> None:
    db = tmp_path / "history.db"
    init_db(db)
    upsert_weight(
        scope="merchant",
        shop=SHOP,
        feature_key="action_type",
        feature_value="meta_title",
        weight=0.3,
        sample_size=2,
        confidence=50,
        db_path=db,
    )
    decision_id = record_decision(
        shop=SHOP,
        resource_id="p1",
        action_type="meta_title",
        previous_score=50,
        learning_score=10,
        final_score=70,
        mode="semi_auto",
        approval_required=True,
        risk_level="low",
        explanation={"reason": "test"},
        db_path=db,
    )
    approval_id = create_pending_approval(
        shop=SHOP,
        resource_type="product",
        resource_id="p1",
        action_type="meta_title",
        field="meta_title",
        old_value="Old",
        proposed_value="New",
        confidence_score=90,
        risk_level="low",
        expected_impact={"score_delta_estimate": 2},
        explanation={"reason": "test"},
        db_path=db,
    )
    run_id = record_run(
        shop=SHOP,
        status="completed",
        observations_created=1,
        weights_updated=2,
        actions_reprioritized=3,
        approvals_created=4,
        auto_applied_count=5,
        errors=[],
        db_path=db,
    )

    assert list_weights(SHOP, db_path=db)[0]["weight"] == 0.3
    assert list_decisions(SHOP, db_path=db)[0]["id"] == decision_id
    assert list_pending_approvals(SHOP, db_path=db)[0]["id"] == approval_id
    assert list_runs(SHOP, db_path=db)[0]["id"] == run_id


def test_update_approval_status_updates_review_and_apply_dates(tmp_path: Path) -> None:
    db = tmp_path / "history.db"
    init_db(db)
    approval_id = create_pending_approval(
        shop=SHOP,
        resource_type="product",
        resource_id="p1",
        action_type="meta_title",
        field="meta_title",
        old_value="Old",
        proposed_value="New",
        confidence_score=90,
        risk_level="low",
        expected_impact={},
        explanation={},
        db_path=db,
    )

    edited = update_approval_status(
        shop=SHOP,
        approval_id=approval_id,
        status=ApprovalStatus.EDITED,
        proposed_value="Edited",
        db_path=db,
    )
    applied = update_approval_status(
        shop=SHOP,
        approval_id=approval_id,
        status=ApprovalStatus.APPLIED,
        db_path=db,
    )

    assert edited is not None
    assert edited["status"] == "edited"
    assert edited["proposed_value"] == "Edited"
    assert applied is not None
    assert applied["applied_at"] is not None
