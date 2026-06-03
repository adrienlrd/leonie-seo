"""Tests for learning weights and policy decisions."""

from __future__ import annotations

from pathlib import Path

from app.db import init_db
from app.learning.learner import update_weights_from_observation
from app.learning.models import CandidateAction, LearningMode, LearningObservation, RiskLevel
from app.learning.policy import rank_candidates
from app.learning.store import get_weight, list_pending_approvals, update_settings

SHOP = "store.myshopify.com"


def _observation(confidence: int = 80, outcome: float = 60) -> LearningObservation:
    return LearningObservation(
        shop=SHOP,
        resource_type="product",
        resource_id="gid://shopify/Product/1",
        action_type="meta_title",
        surface="product_page",
        keyword_source="gsc",
        before_metrics={},
        after_metrics={},
        control_metrics={},
        window_days=28,
        window_label="J+28",
        is_primary_window=True,
        outcome_score=outcome,
        confidence_score=confidence,
        features=[("action_type", "meta_title"), ("surface", "product_page")],
    )


def _candidate(
    *,
    confidence: int = 90,
    risk: RiskLevel = RiskLevel.LOW,
    field: str = "meta_title",
    locked_negative_tag: bool = False,
) -> CandidateAction:
    return CandidateAction(
        shop=SHOP,
        resource_type="product",
        resource_id="gid://shopify/Product/1",
        resource_title="Harnais",
        action_type=field,
        field=field,
        surface="product_page",
        current_score=70,
        potential_score=85,
        confidence_score=confidence,
        risk_level=risk,
        keyword_source="gsc",
        content_quality_score=90,
        old_value="Old",
        proposed_value="New",
        tags=[{"label": "unsafe promise", "status": "negative", "locked_by_merchant": True}]
        if locked_negative_tag
        else [],
    )


def test_update_learning_weights_when_observation_has_confidence(tmp_path: Path) -> None:
    db = tmp_path / "history.db"
    init_db(db)

    updated = update_weights_from_observation(_observation(), db_path=db)
    weight = get_weight(
        scope="merchant",
        shop=SHOP,
        feature_key="action_type",
        feature_value="meta_title",
        db_path=db,
    )

    assert updated == 4
    assert weight is not None
    assert weight.weight > 0
    assert weight.sample_size == 1


def test_no_auto_apply_when_confidence_too_low(tmp_path: Path) -> None:
    db = tmp_path / "history.db"
    init_db(db)
    update_settings(SHOP, {"mode": "auto_apply", "enabled": True}, db_path=db)

    decisions = rank_candidates(
        SHOP,
        [_candidate(confidence=50)],
        plan="pro",
        writer_supported_by_field={"meta_title": True},
        confirm_live_write=True,
        db_path=db,
    )

    assert decisions[0].auto_apply_eligible is False
    assert decisions[0].approval_required is True


def test_no_auto_apply_when_plan_is_free(tmp_path: Path) -> None:
    db = tmp_path / "history.db"
    init_db(db)
    update_settings(SHOP, {"mode": "auto_apply", "enabled": True}, db_path=db)

    decisions = rank_candidates(
        SHOP,
        [_candidate()],
        plan="free",
        writer_supported_by_field={"meta_title": True},
        confirm_live_write=True,
        db_path=db,
    )

    assert decisions[0].auto_apply_eligible is False


def test_no_auto_apply_when_setting_is_disabled(tmp_path: Path) -> None:
    db = tmp_path / "history.db"
    init_db(db)
    update_settings(SHOP, {"mode": "auto_apply", "enabled": False}, db_path=db)

    decisions = rank_candidates(
        SHOP,
        [_candidate()],
        plan="pro",
        writer_supported_by_field={"meta_title": True},
        confirm_live_write=True,
        db_path=db,
    )

    assert decisions[0].auto_apply_eligible is False


def test_medium_risk_goes_to_pending_approval(tmp_path: Path) -> None:
    db = tmp_path / "history.db"
    init_db(db)
    update_settings(SHOP, {"mode": "auto_apply", "enabled": True}, db_path=db)

    decisions = rank_candidates(
        SHOP,
        [_candidate(risk=RiskLevel.MEDIUM)],
        plan="pro",
        writer_supported_by_field={"meta_title": True},
        confirm_live_write=True,
        db_path=db,
    )
    approvals = list_pending_approvals(SHOP, db_path=db)

    assert decisions[0].auto_apply_eligible is False
    assert decisions[0].approval_required is True
    assert len(approvals) == 1


def test_semi_auto_creates_pending_approval(tmp_path: Path) -> None:
    db = tmp_path / "history.db"
    init_db(db)
    update_settings(SHOP, {"mode": LearningMode.SEMI_AUTO.value, "enabled": True}, db_path=db)

    rank_candidates(
        SHOP,
        [_candidate()],
        plan="pro",
        writer_supported_by_field={"meta_title": True},
        confirm_live_write=True,
        db_path=db,
    )

    assert len(list_pending_approvals(SHOP, db_path=db)) == 1


def test_locked_negative_tag_blocks_auto_apply(tmp_path: Path) -> None:
    db = tmp_path / "history.db"
    init_db(db)
    update_settings(SHOP, {"mode": "auto_apply", "enabled": True}, db_path=db)

    decisions = rank_candidates(
        SHOP,
        [_candidate(locked_negative_tag=True)],
        plan="pro",
        writer_supported_by_field={"meta_title": True},
        confirm_live_write=True,
        db_path=db,
    )

    assert decisions[0].auto_apply_eligible is False
