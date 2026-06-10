"""Integration tests for continuous agent learning decisions."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.content_actions.schema import (
    ConstraintsCheck,
    ContentActionRequest,
    ContentActionResult,
    ContentOutput,
    ContentStatus,
    ContentType,
    QualityResult,
)
from app.db import init_db
from app.geo.continuous_agent import run_continuous_improvement_agent
from app.geo.continuous_improvement import set_product_tag
from app.learning.store import list_pending_approvals, update_settings

SHOP = "learn.myshopify.com"
PRODUCT_1 = "gid://shopify/Product/1"
PRODUCT_2 = "gid://shopify/Product/2"


def _latest_result() -> dict[str, Any]:
    return {
        "products": [
            {
                "product_id": PRODUCT_1,
                "product_title": "Harnais confort",
                "product_handle": "harnais-confort",
                "target_customer": "Chien sensible",
                "buying_intents": ["choisir un harnais confortable"],
                "opportunity_score": 72,
                "seo_keywords": [
                    {
                        "query": "harnais chien confortable",
                        "data_source": "gsc",
                        "product_fit_score": 85,
                    }
                ],
                "content_test_pack": {
                    "current_meta_title": "Harnais",
                    "current_meta_description": "Ancienne description",
                    "current_product_description_summary": "Ancienne fiche",
                    "proposed_meta_title": "",
                    "proposed_meta_description": "",
                    "proposed_product_description": "",
                    "facts_missing": [],
                },
            },
            {
                "product_id": PRODUCT_2,
                "product_title": "Pull chien",
                "product_handle": "pull-chien",
                "target_customer": "Chien frileux",
                "buying_intents": ["trouver un pull chaud"],
                "opportunity_score": 64,
                "seo_keywords": [
                    {
                        "query": "pull chien chaud",
                        "data_source": "google_suggest",
                        "product_fit_score": 76,
                    }
                ],
                "content_test_pack": {
                    "current_meta_title": "Pull",
                    "current_meta_description": "Ancienne description",
                    "current_product_description_summary": "Ancienne fiche",
                    "proposed_meta_title": "",
                    "proposed_meta_description": "",
                    "proposed_product_description": "",
                    "facts_missing": [],
                },
            },
        ]
    }


def _content_result(
    request: ContentActionRequest,
    *,
    score: int = 92,
    status: ContentStatus = ContentStatus.DRAFT,
) -> ContentActionResult:
    return ContentActionResult(
        action_id=f"action-{request.resource.id.rsplit('/', 1)[-1]}-{request.content_type.value}",
        content_type=request.content_type,
        resource_id=request.resource.id,
        generated_at=datetime.now(UTC).isoformat(),
        output=ContentOutput(primary_text=f"Improved {request.content_type.value}"),
        constraints_check=ConstraintsCheck(),
        quality=QualityResult(score=score, label="excellent"),
        status=status,
    )


def _prepare(
    tmp_path: Path,
    monkeypatch,
    *,
    auto_apply: bool = False,
    settings: dict[str, Any] | None = None,
) -> Path:
    db = tmp_path / "continuous-learning.db"
    init_db(db)
    update_settings(
        SHOP,
        {
            "mode": "auto_apply" if auto_apply else "semi_auto",
            "min_confidence_to_auto_apply": 80,
            "min_confidence_to_suggest": 45,
            **(settings or {}),
        },
        db_path=db,
    )
    monkeypatch.setattr("app.geo.continuous_agent.DB_PATH", db)
    monkeypatch.setattr("app.geo.continuous_improvement.DB_PATH", db)
    monkeypatch.setattr("app.content_actions.runner.DB_PATH", db, raising=False)
    monkeypatch.setattr(
        "app.geo.continuous_agent.load_latest_result", lambda shop: _latest_result()
    )
    monkeypatch.setattr(
        "app.geo.continuous_agent.get_validated_niche_hypothesis",
        lambda shop: None,
    )
    return db


def test_agent_calls_learning_policy_and_creates_semi_auto_approvals(
    tmp_path: Path,
    monkeypatch,
) -> None:
    db = _prepare(tmp_path, monkeypatch)
    calls: list[list[Any]] = []

    from app.learning.policy import rank_candidates as real_rank_candidates

    def spy_rank(shop: str, candidates: list[Any], **kwargs: Any) -> list[Any]:
        calls.append(candidates)
        return real_rank_candidates(shop, candidates, **kwargs)

    monkeypatch.setattr("app.geo.continuous_agent.rank_candidates", spy_rank)
    monkeypatch.setattr(
        "app.geo.continuous_agent.run_content_action",
        lambda request, *args, **kwargs: _content_result(request),
    )

    result = run_continuous_improvement_agent(
        SHOP,
        plan="pro",
        auto_apply=False,
        confirm_live_write=False,
        max_actions=1,
        db_path=db,
    )

    assert calls
    assert result["summary"]["learning_approvals_created"] == 1
    assert result["summary"]["applied"] == 0
    approvals = list_pending_approvals(SHOP, db_path=db)
    assert len(approvals) == 1
    proposal = result["proposals"][0]
    assert proposal["learning_score"] >= 0
    assert proposal["confidence_score"] == 92
    assert proposal["risk_level"] == "low"
    assert proposal["learning_explanation"]


def test_agent_auto_apply_only_low_risk_high_confidence_when_confirmed(
    tmp_path: Path,
    monkeypatch,
) -> None:
    db = _prepare(tmp_path, monkeypatch, auto_apply=True)
    monkeypatch.setattr(
        "app.geo.continuous_agent.run_content_action",
        lambda request, *args, **kwargs: _content_result(request, score=93),
    )
    monkeypatch.setattr("app.geo.continuous_agent.is_live_supported", lambda content_type: True)
    monkeypatch.setattr(
        "app.geo.continuous_agent._mark_action_approved",
        lambda *args, **kwargs: {"ok": True},
    )
    applied_calls: list[dict[str, Any]] = []

    def fake_apply(**kwargs: Any) -> dict[str, Any]:
        applied_calls.append(kwargs)
        return {"applied": True, "field": "seo.title", "applied_at": "now"}

    monkeypatch.setattr("app.geo.continuous_agent._apply_safe_action", fake_apply)

    result = run_continuous_improvement_agent(
        SHOP,
        access_token="shpat_test",
        plan="pro",
        auto_apply=True,
        confirm_live_write=True,
        max_actions=1,
        db_path=db,
    )

    assert result["summary"]["applied"] == 1
    assert applied_calls
    assert result["proposals"][0]["auto_apply_attempted"] is True
    assert result["proposals"][0]["applied"] is True


def test_agent_does_not_auto_apply_outside_auto_publish_scopes(
    tmp_path: Path,
    monkeypatch,
) -> None:
    db = _prepare(tmp_path, monkeypatch, auto_apply=True)
    monkeypatch.setattr(
        "app.geo.continuous_agent.run_content_action",
        lambda request, *args, **kwargs: _content_result(request, score=93),
    )
    monkeypatch.setattr("app.geo.continuous_agent.is_live_supported", lambda content_type: True)
    monkeypatch.setattr(
        "app.geo.continuous_agent._mark_action_approved",
        lambda *args, **kwargs: {"ok": True},
    )
    applied_calls: list[dict[str, Any]] = []

    def fake_apply(**kwargs: Any) -> dict[str, Any]:
        applied_calls.append(kwargs)
        return {"applied": True, "field": "seo.title", "applied_at": "now"}

    monkeypatch.setattr("app.geo.continuous_agent._apply_safe_action", fake_apply)

    result = run_continuous_improvement_agent(
        SHOP,
        access_token="shpat_test",
        plan="pro",
        auto_apply=True,
        confirm_live_write=True,
        max_actions=1,
        db_path=db,
        auto_publish_scopes=["blog_publish"],
    )

    assert result["summary"]["applied"] == 0
    assert not applied_calls
    assert result["proposals"][0]["auto_apply_attempted"] is False


def test_agent_keeps_medium_risk_actions_in_approval_queue(
    tmp_path: Path,
    monkeypatch,
) -> None:
    db = _prepare(tmp_path, monkeypatch, auto_apply=True)
    monkeypatch.setattr(
        "app.geo.continuous_agent.run_content_action",
        lambda request, *args, **kwargs: _content_result(request, score=95),
    )
    monkeypatch.setattr("app.geo.continuous_agent.is_live_supported", lambda content_type: True)
    monkeypatch.setattr("app.geo.continuous_agent._apply_safe_action", lambda **kwargs: None)

    from app.learning.models import RiskLevel

    monkeypatch.setattr(
        "app.geo.continuous_agent.assess_action_risk", lambda *args, **kwargs: RiskLevel.MEDIUM
    )

    result = run_continuous_improvement_agent(
        SHOP,
        access_token="shpat_test",
        plan="pro",
        auto_apply=True,
        confirm_live_write=True,
        max_actions=1,
        db_path=db,
    )

    assert result["summary"]["applied"] == 0
    assert result["summary"]["learning_approvals_created"] == 1
    assert list_pending_approvals(SHOP, db_path=db)[0]["risk_level"] == "medium"


def test_agent_respects_learning_boost_when_selecting_candidates(
    tmp_path: Path,
    monkeypatch,
) -> None:
    db = _prepare(tmp_path, monkeypatch)
    monkeypatch.setattr(
        "app.geo.continuous_agent.learning_boost_for_action",
        lambda **kwargs: {
            "learning_boost": 30 if kwargs["action_type"] == "meta_description" else 0,
        },
    )

    generated: list[ContentType] = []

    def fake_run(request: ContentActionRequest, *args: Any, **kwargs: Any) -> ContentActionResult:
        generated.append(request.content_type)
        return _content_result(request)

    monkeypatch.setattr("app.geo.continuous_agent.run_content_action", fake_run)

    run_continuous_improvement_agent(SHOP, plan="pro", max_actions=1, db_path=db)

    assert generated == [ContentType.META_DESCRIPTION]


def test_agent_continues_when_one_product_fails(tmp_path: Path, monkeypatch) -> None:
    db = _prepare(tmp_path, monkeypatch)
    calls = 0

    def flaky_run(request: ContentActionRequest, *args: Any, **kwargs: Any) -> ContentActionResult:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("generation failed")
        return _content_result(request)

    monkeypatch.setattr("app.geo.continuous_agent.run_content_action", flaky_run)

    result = run_continuous_improvement_agent(SHOP, plan="pro", max_actions=2, db_path=db)

    assert result["summary"]["errors"] == 1
    assert result["summary"]["proposals_created"] == 1
    assert result["errors"][0]["error"] == "generation failed"


def test_locked_tags_are_not_modified_by_feedback(tmp_path: Path, monkeypatch) -> None:
    db = _prepare(tmp_path, monkeypatch)
    set_product_tag(
        SHOP,
        PRODUCT_1,
        label="premium",
        tag_type="keyword",
        status="neutral",
        locked_by_merchant=True,
        db_path=db,
    )
    monkeypatch.setattr(
        "app.geo.continuous_agent.run_content_action",
        lambda request, *args, **kwargs: _content_result(request),
    )

    result = run_continuous_improvement_agent(SHOP, plan="pro", max_actions=1, db_path=db)

    assert result["summary"]["feedback_tag_decisions"] == 0
