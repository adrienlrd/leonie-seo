"""Tests for learning outcome and confidence scoring."""

from __future__ import annotations

from app.learning.outcomes import calculate_confidence, calculate_outcome


def test_outcome_score_positive_when_metrics_improve() -> None:
    result = calculate_outcome(
        before_metrics={"gsc": {"impressions": 100, "clicks": 5, "ctr": 0.05, "position": 12}},
        after_metrics={"gsc": {"impressions": 150, "clicks": 10, "ctr": 0.07, "position": 8}},
        score_before=50,
        score_after=65,
    )

    assert result["outcome_score"] > 0


def test_outcome_score_negative_when_metrics_decline() -> None:
    result = calculate_outcome(
        before_metrics={"gsc": {"impressions": 200, "clicks": 20, "ctr": 0.10, "position": 5}},
        after_metrics={"gsc": {"impressions": 120, "clicks": 8, "ctr": 0.06, "position": 11}},
        score_before=70,
        score_after=55,
    )

    assert result["outcome_score"] < 0


def test_outcome_score_neutral_when_metrics_are_stable() -> None:
    result = calculate_outcome(
        before_metrics={"gsc": {"impressions": 100, "clicks": 5, "ctr": 0.05, "position": 12}},
        after_metrics={"gsc": {"impressions": 100, "clicks": 5, "ctr": 0.05, "position": 12}},
        score_before=50,
        score_after=50,
    )

    assert abs(result["outcome_score"]) < 1


def test_confidence_score_caps_j14_when_volume_is_high() -> None:
    outcome = calculate_outcome(
        before_metrics={"gsc": {"impressions": 2000, "clicks": 100, "ctr": 0.05}},
        after_metrics={"gsc": {"impressions": 3000, "clicks": 180, "ctr": 0.06}},
    )
    confidence = calculate_confidence(
        before_metrics={"gsc": {"impressions": 2000, "clicks": 100}},
        after_metrics={"gsc": {"impressions": 3000, "clicks": 180}},
        control_metrics={"impressions_before": 2000, "impressions_after": 2100},
        window_days=14,
        outcome_deltas=outcome["deltas"],
    )

    assert confidence <= 75


def test_confidence_score_uses_j28_as_primary_window() -> None:
    outcome = calculate_outcome(
        before_metrics={"gsc": {"impressions": 2000, "clicks": 100}, "ga4": {"conversions": 8}},
        after_metrics={"gsc": {"impressions": 3000, "clicks": 180}, "ga4": {"conversions": 12}},
    )
    confidence = calculate_confidence(
        before_metrics={"gsc": {"impressions": 2000, "clicks": 100}, "ga4": {"conversions": 8}},
        after_metrics={"gsc": {"impressions": 3000, "clicks": 180}, "ga4": {"conversions": 12}},
        control_metrics={"impressions_before": 2000, "impressions_after": 2100},
        window_days=28,
        outcome_deltas=outcome["deltas"],
    )

    assert confidence > 75


def test_confidence_score_stays_low_when_volume_is_too_small() -> None:
    outcome = calculate_outcome(
        before_metrics={"gsc": {"impressions": 8, "clicks": 1}},
        after_metrics={"gsc": {"impressions": 20, "clicks": 3}},
    )
    confidence = calculate_confidence(
        before_metrics={"gsc": {"impressions": 8, "clicks": 1}},
        after_metrics={"gsc": {"impressions": 20, "clicks": 3}},
        control_metrics=None,
        window_days=28,
        outcome_deltas=outcome["deltas"],
    )

    assert confidence <= 35


def test_confidence_score_falls_back_without_gsc_or_ga4() -> None:
    outcome = calculate_outcome(
        before_metrics={"impressions": 100},
        after_metrics={"impressions": 120},
    )
    confidence = calculate_confidence(
        before_metrics={"impressions": 100},
        after_metrics={"impressions": 120},
        control_metrics=None,
        window_days=28,
        outcome_deltas=outcome["deltas"],
    )

    assert 0 < confidence < 70
