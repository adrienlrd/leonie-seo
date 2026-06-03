"""Focused tests for learning policy scoring and safety gates."""

from __future__ import annotations

from pathlib import Path

from app.db import init_db
from app.learning.models import CandidateAction, LearningMode, RiskLevel
from app.learning.policy import is_auto_apply_eligible, rank_candidates, score_candidate
from app.learning.store import (
    get_settings,
    list_pending_approvals,
    update_settings,
    upsert_weight,
)

SHOP = "store.myshopify.com"


def _candidate(
    *,
    resource_id: str = "gid://shopify/Product/1",
    score: float = 70,
    confidence: int = 90,
    risk: RiskLevel = RiskLevel.LOW,
    field: str = "meta_title",
    action_type: str | None = None,
    locked_negative_tag: bool = False,
) -> CandidateAction:
    action = action_type or field
    return CandidateAction(
        shop=SHOP,
        resource_type="product",
        resource_id=resource_id,
        resource_title="Harnais",
        action_type=action,
        field=field,
        surface="product_page",
        current_score=score,
        potential_score=score,
        confidence_score=confidence,
        risk_level=risk,
        keyword_source="gsc",
        content_quality_score=90,
        old_value="Old",
        proposed_value="New",
        tags=[{"label": "forbidden angle", "status": "negative", "locked_by_merchant": True}]
        if locked_negative_tag
        else [],
    )


def test_semi_auto_creates_approval_instead_of_auto_apply(tmp_path: Path) -> None:
    db = tmp_path / "history.db"
    init_db(db)
    update_settings(SHOP, {"mode": "semi_auto", "enabled": True}, db_path=db)

    decisions = rank_candidates(
        SHOP,
        [_candidate()],
        plan="agency",
        writer_supported_by_field={"meta_title": True},
        confirm_live_write=True,
        db_path=db,
    )

    assert decisions[0].auto_apply_eligible is False
    assert decisions[0].approval_required is True
    assert len(list_pending_approvals(SHOP, db_path=db)) == 1


def test_auto_apply_is_eligible_only_when_all_conditions_are_met(tmp_path: Path) -> None:
    db = tmp_path / "history.db"
    init_db(db)
    update_settings(SHOP, {"mode": "auto_apply", "enabled": True}, db_path=db)

    decisions = rank_candidates(
        SHOP,
        [_candidate()],
        plan="pro",
        writer_supported_by_field={"meta_title": True},
        confirm_live_write=True,
        db_path=db,
    )

    assert decisions[0].auto_apply_eligible is True
    assert decisions[0].approval_required is False


def test_auto_apply_is_blocked_for_free_plan(tmp_path: Path) -> None:
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


def test_auto_apply_requires_confirm_live_write(tmp_path: Path) -> None:
    db = tmp_path / "history.db"
    init_db(db)
    update_settings(SHOP, {"mode": "auto_apply", "enabled": True}, db_path=db)

    decisions = rank_candidates(
        SHOP,
        [_candidate()],
        plan="pro",
        writer_supported_by_field={"meta_title": True},
        confirm_live_write=False,
        db_path=db,
    )

    assert decisions[0].auto_apply_eligible is False


def test_auto_apply_requires_supported_writer(tmp_path: Path) -> None:
    db = tmp_path / "history.db"
    init_db(db)
    update_settings(SHOP, {"mode": "auto_apply", "enabled": True}, db_path=db)

    decisions = rank_candidates(
        SHOP,
        [_candidate()],
        plan="pro",
        writer_supported_by_field={"meta_title": False},
        confirm_live_write=True,
        db_path=db,
    )

    assert decisions[0].auto_apply_eligible is False


def test_auto_apply_blocks_unsupported_field(tmp_path: Path) -> None:
    db = tmp_path / "history.db"
    init_db(db)
    update_settings(SHOP, {"mode": "auto_apply", "enabled": True}, db_path=db)

    decisions = rank_candidates(
        SHOP,
        [_candidate(field="blog", action_type="blog", risk=RiskLevel.LOW)],
        plan="agency",
        writer_supported_by_field={"blog": True},
        confirm_live_write=True,
        db_path=db,
    )

    assert decisions[0].auto_apply_eligible is False


def test_auto_apply_blocks_medium_and_high_risk(tmp_path: Path) -> None:
    db = tmp_path / "history.db"
    init_db(db)
    update_settings(SHOP, {"mode": "auto_apply", "enabled": True}, db_path=db)

    decisions = rank_candidates(
        SHOP,
        [
            _candidate(resource_id="m", risk=RiskLevel.MEDIUM),
            _candidate(resource_id="h", risk=RiskLevel.HIGH),
        ],
        plan="pro",
        writer_supported_by_field={"meta_title": True},
        confirm_live_write=True,
        db_path=db,
    )

    assert all(not decision.auto_apply_eligible for decision in decisions)
    assert len(list_pending_approvals(SHOP, db_path=db)) == 2


def test_auto_apply_blocks_locked_negative_tag(tmp_path: Path) -> None:
    db = tmp_path / "history.db"
    init_db(db)
    update_settings(SHOP, {"mode": "auto_apply", "enabled": True}, db_path=db)

    decision = rank_candidates(
        SHOP,
        [_candidate(locked_negative_tag=True)],
        plan="pro",
        writer_supported_by_field={"meta_title": True},
        confirm_live_write=True,
        db_path=db,
    )[0]

    assert decision.auto_apply_eligible is False


def test_min_confidence_to_suggest_controls_pending_approval_creation(tmp_path: Path) -> None:
    db = tmp_path / "history.db"
    init_db(db)
    update_settings(
        SHOP,
        {"mode": "semi_auto", "enabled": True, "min_confidence_to_suggest": 70},
        db_path=db,
    )

    rank_candidates(
        SHOP,
        [_candidate(confidence=60)],
        plan="pro",
        writer_supported_by_field={"meta_title": True},
        confirm_live_write=True,
        db_path=db,
    )

    assert list_pending_approvals(SHOP, db_path=db) == []


def test_ranking_sorts_by_final_score(tmp_path: Path) -> None:
    db = tmp_path / "history.db"
    init_db(db)
    update_settings(SHOP, {"mode": "semi_auto", "enabled": True}, db_path=db)

    decisions = rank_candidates(
        SHOP,
        [
            _candidate(resource_id="low", score=30),
            _candidate(resource_id="high", score=90),
        ],
        plan="pro",
        writer_supported_by_field={"meta_title": True},
        confirm_live_write=True,
        db_path=db,
    )

    assert decisions[0].candidate.resource_id == "high"


def test_risk_penalty_lowers_final_score(tmp_path: Path) -> None:
    db = tmp_path / "history.db"
    init_db(db)
    settings = get_settings(SHOP, db_path=db)

    low = score_candidate(_candidate(risk=RiskLevel.LOW), settings=settings, db_path=db)
    high = score_candidate(_candidate(risk=RiskLevel.HIGH), settings=settings, db_path=db)

    assert high.final_score < low.final_score


def test_merchant_and_global_weights_influence_score(tmp_path: Path) -> None:
    db = tmp_path / "history.db"
    init_db(db)
    settings = get_settings(SHOP, db_path=db)
    base = score_candidate(_candidate(), settings=settings, db_path=db)
    for scope, shop in (("merchant", SHOP), ("global", None)):
        upsert_weight(
            scope=scope,
            shop=shop,
            feature_key="action_type",
            feature_value="meta_title",
            weight=0.5,
            sample_size=5,
            confidence=80,
            db_path=db,
        )

    boosted = score_candidate(_candidate(), settings=settings, db_path=db)

    assert boosted.final_score > base.final_score
    assert boosted.learning_score > 0


def test_is_auto_apply_eligible_has_no_third_mode(tmp_path: Path) -> None:
    db = tmp_path / "history.db"
    init_db(db)
    settings = update_settings(SHOP, {"mode": LearningMode.AUTO_APPLY.value}, db_path=db)

    assert is_auto_apply_eligible(
        _candidate(),
        settings,
        plan="pro",
        writer_supported=True,
        confirm_live_write=True,
    )
