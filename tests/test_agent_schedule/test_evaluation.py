"""Tests for the GEO agent effectiveness evaluation.

These tests answer the merchant's two questions explicitly:
- Is the agent improving SEO and GEO? (verdict per dimension)
- If not, how to improve it? (actionable recommendations)
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.agent_schedule.evaluation import evaluate_agent_effectiveness
from app.db import init_db
from app.db_adapter import get_conn
from app.learning.store import create_observation, create_pending_approval, record_run

SHOP = "eval.myshopify.com"


def _db(tmp_path: Path) -> Path:
    db = tmp_path / "history.db"
    init_db(db)
    return db


def _observation(
    db: Path,
    *,
    index: int,
    seo: float,
    geo: float,
    verdict: str,
    confidence: int = 80,
    outcome: float = 40.0,
    quality: int = 85,
    learnable: bool = True,
    field: str = "meta_title",
) -> None:
    create_observation(
        shop=SHOP,
        resource_type="product",
        resource_id=f"gid://shopify/Product/{index}",
        action_type=field,
        surface="product_page",
        keyword_source="gsc",
        before_metrics={"gsc": {"impressions": 100, "clicks": 5}},
        after_metrics={"gsc": {"impressions": 160, "clicks": 12}},
        control_metrics={},
        window_days=28,
        window_label="J+28",
        is_primary_window=True,
        outcome_score=outcome,
        confidence_score=confidence,
        metadata={
            "learnable": learnable,
            "experiment_verdict": verdict,
            "content_quality_score": quality,
            "field": field,
            "outcome_deltas": {
                "impressions": seo,
                "clicks": seo,
                "ctr": seo / 2,
                "position": seo / 2,
                "conversions": 0.0,
                "revenue": 0.0,
                "score": geo,
            },
        },
        db_path=db,
    )


def _agent_run(db: Path, *, proposals_created: int, applied: int) -> None:
    now = datetime.now(UTC).isoformat()
    with get_conn(db) as conn:
        conn.execute(
            """
            INSERT INTO continuous_improvement_agent_runs (
                shop, created_at, mode, status, summary_json, proposals_json, errors_json
            )
            VALUES (?, ?, 'semi_auto', 'completed', ?, '[]', '[]')
            """,
            (
                SHOP,
                now,
                f'{{"proposals_created": {proposals_created}, "applied": {applied}}}',
            ),
        )


def _learning_run(db: Path) -> None:
    record_run(
        shop=SHOP,
        status="completed",
        observations_created=3,
        weights_updated=2,
        actions_reprioritized=1,
        approvals_created=0,
        auto_applied_count=0,
        errors=[],
        db_path=db,
    )


def _codes(result: dict[str, Any]) -> set[str]:
    return {rec["code"] for rec in result["recommendations"]}


# ── Improving ────────────────────────────────────────────────────────────────


def test_agent_is_improving_seo_and_geo(tmp_path: Path) -> None:
    db = _db(tmp_path)
    _learning_run(db)
    for i in range(4):
        _observation(db, index=i, seo=0.6, geo=0.5, verdict="positive_high_confidence")

    result = evaluate_agent_effectiveness(SHOP, db_path=db)

    assert result["seo"]["verdict"] == "improving"
    assert result["geo"]["verdict"] == "improving"
    assert result["overall_verdict"] == "improving"
    assert result["seo"]["score"] > 0
    assert result["geo"]["score"] > 0
    assert "IMPROVING_KEEP" in _codes(result)


# ── Regressing ───────────────────────────────────────────────────────────────


def test_agent_is_regressing_recommends_rollback(tmp_path: Path) -> None:
    db = _db(tmp_path)
    _learning_run(db)
    for i in range(4):
        _observation(db, index=i, seo=-0.5, geo=-0.4, verdict="negative")

    result = evaluate_agent_effectiveness(SHOP, db_path=db)

    assert result["seo"]["verdict"] == "regressing"
    assert result["geo"]["verdict"] == "regressing"
    assert result["overall_verdict"] == "regressing"
    assert "REGRESSING" in _codes(result)


# ── GEO improves, SEO flat ───────────────────────────────────────────────────


def test_geo_ok_but_seo_flat_targets_keywords(tmp_path: Path) -> None:
    db = _db(tmp_path)
    _learning_run(db)
    for i in range(4):
        _observation(db, index=i, seo=0.0, geo=0.6, verdict="positive_high_confidence")

    result = evaluate_agent_effectiveness(SHOP, db_path=db)

    assert result["geo"]["verdict"] == "improving"
    assert result["seo"]["verdict"] in {"no_effect", "regressing"}
    assert "SEO_FLAT_GEO_OK" in _codes(result)


# ── Inconclusive ─────────────────────────────────────────────────────────────


def test_inconclusive_when_not_enough_samples(tmp_path: Path) -> None:
    db = _db(tmp_path)
    _learning_run(db)
    _observation(db, index=0, seo=0.6, geo=0.6, verdict="positive_low_confidence")

    result = evaluate_agent_effectiveness(SHOP, db_path=db)

    assert result["sample_size"] == 1
    assert result["seo"]["verdict"] == "inconclusive"
    assert result["geo"]["verdict"] == "inconclusive"


def test_low_confidence_recommends_connecting_analytics(tmp_path: Path) -> None:
    db = _db(tmp_path)
    _learning_run(db)
    for i in range(4):
        _observation(db, index=i, seo=0.6, geo=0.6, verdict="inconclusive", confidence=20)

    result = evaluate_agent_effectiveness(SHOP, db_path=db)

    assert result["seo"]["verdict"] == "inconclusive"
    assert "LOW_CONFIDENCE" in _codes(result)


# ── No run yet ───────────────────────────────────────────────────────────────


def test_no_runs_tells_merchant_to_run_agent(tmp_path: Path) -> None:
    db = _db(tmp_path)

    result = evaluate_agent_effectiveness(SHOP, db_path=db)

    assert result["overall_verdict"] in {"inconclusive", "no_effect"}
    assert "NO_RUNS" in _codes(result)


# ── Proposals awaiting validation ────────────────────────────────────────────


def test_proposals_awaiting_validation_is_flagged(tmp_path: Path) -> None:
    db = _db(tmp_path)
    _learning_run(db)
    _agent_run(db, proposals_created=2, applied=0)
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

    result = evaluate_agent_effectiveness(SHOP, db_path=db)

    assert "PROPOSALS_AWAITING_VALIDATION" in _codes(result)
    assert result["pending_approvals"] == 1


# ── by_field breakdown ───────────────────────────────────────────────────────


def test_by_field_breakdown_highlights_best_field(tmp_path: Path) -> None:
    db = _db(tmp_path)
    _learning_run(db)
    for i in range(3):
        _observation(db, index=i, seo=0.7, geo=0.6, verdict="positive_high_confidence",
                     field="meta_title")
    for i in range(3, 6):
        _observation(db, index=i, seo=-0.3, geo=-0.2, verdict="negative",
                     field="product_description", outcome=-25.0)

    result = evaluate_agent_effectiveness(SHOP, db_path=db)

    fields = {row["field"]: row for row in result["by_field"]}
    assert fields["meta_title"]["avg_outcome"] > fields["product_description"]["avg_outcome"]
    # Best-performing field is listed first.
    assert result["by_field"][0]["field"] == "meta_title"
