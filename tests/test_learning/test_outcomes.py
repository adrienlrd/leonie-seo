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


def test_outcome_score_treats_lower_numeric_position_as_positive() -> None:
    result = calculate_outcome(
        before_metrics={"gsc": {"position": 12}},
        after_metrics={"gsc": {"position": 8}},
    )

    assert result["deltas"]["position"] > 0
    assert result["outcome_score"] > 0


def test_outcome_score_tracks_ctr_delta() -> None:
    result = calculate_outcome(
        before_metrics={"gsc": {"ctr": 0.03}},
        after_metrics={"gsc": {"ctr": 0.08}},
    )

    assert result["deltas"]["ctr"] == 0.05
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


def test_outcome_score_includes_relative_uplift_against_control_group() -> None:
    without_control = calculate_outcome(
        before_metrics={"gsc": {"impressions": 100}},
        after_metrics={"gsc": {"impressions": 140}},
    )
    with_control = calculate_outcome(
        before_metrics={"gsc": {"impressions": 100}},
        after_metrics={"gsc": {"impressions": 140}},
        control_metrics={"impressions_before": 100, "impressions_after": 90},
    )

    assert with_control["control_uplift"] > 0
    assert with_control["outcome_score"] > without_control["outcome_score"]


def test_outcome_score_is_bounded_between_minus_100_and_plus_100() -> None:
    positive = calculate_outcome(
        before_metrics={"gsc": {"impressions": 1, "clicks": 1, "position": 100}},
        after_metrics={
            "gsc": {"impressions": 1_000_000, "clicks": 500_000, "position": 1},
            "ga4": {"conversions": 100_000, "revenue": 1_000_000},
        },
        score_before=0,
        score_after=1000,
    )
    negative = calculate_outcome(
        before_metrics={
            "gsc": {"impressions": 1_000_000, "clicks": 500_000, "position": 1},
            "ga4": {"conversions": 100_000, "revenue": 1_000_000},
        },
        after_metrics={"gsc": {"impressions": 0, "clicks": 0, "position": 100}},
        score_before=1000,
        score_after=0,
    )

    assert -100 <= positive["outcome_score"] <= 100
    assert -100 <= negative["outcome_score"] <= 100


def test_outcome_score_falls_back_when_ga4_is_absent() -> None:
    result = calculate_outcome(
        before_metrics={"gsc": {"impressions": 100, "clicks": 5}},
        after_metrics={"gsc": {"impressions": 130, "clicks": 7}},
    )

    assert result["outcome_score"] > 0


def test_outcome_score_falls_back_when_gsc_is_absent() -> None:
    result = calculate_outcome(
        before_metrics={"ga4": {"conversions": 2, "revenue": 100}},
        after_metrics={"ga4": {"conversions": 4, "revenue": 180}},
    )

    assert result["outcome_score"] > 0


def test_low_volume_outcome_can_move_but_confidence_stays_weak() -> None:
    outcome = calculate_outcome(
        before_metrics={"gsc": {"impressions": 3, "clicks": 0}},
        after_metrics={"gsc": {"impressions": 9, "clicks": 1}},
    )
    confidence = calculate_confidence(
        before_metrics={"gsc": {"impressions": 3, "clicks": 0}},
        after_metrics={"gsc": {"impressions": 9, "clicks": 1}},
        control_metrics=None,
        window_days=28,
        outcome_deltas=outcome["deltas"],
    )

    assert outcome["outcome_score"] > 0
    assert confidence <= 35


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


def test_confidence_score_increases_with_gsc_presence() -> None:
    deltas = {
        "impressions": 0.5,
        "clicks": 0.5,
        "ctr": 0,
        "position": 0,
        "conversions": 0,
        "revenue": 0,
        "score": 0,
    }

    without_gsc = calculate_confidence(
        before_metrics={"other": {"impressions": 500}},
        after_metrics={"other": {"impressions": 600}},
        control_metrics=None,
        window_days=28,
        outcome_deltas=deltas,
    )
    with_gsc = calculate_confidence(
        before_metrics={"gsc": {"impressions": 500}},
        after_metrics={"gsc": {"impressions": 600}},
        control_metrics=None,
        window_days=28,
        outcome_deltas=deltas,
    )

    assert with_gsc > without_gsc


def test_confidence_score_increases_with_ga4_presence() -> None:
    deltas = {
        "impressions": 0.5,
        "clicks": 0.5,
        "ctr": 0,
        "position": 0,
        "conversions": 0.4,
        "revenue": 0.3,
        "score": 0,
    }

    without_ga4 = calculate_confidence(
        before_metrics={"gsc": {"impressions": 500}},
        after_metrics={"gsc": {"impressions": 600}},
        control_metrics=None,
        window_days=28,
        outcome_deltas=deltas,
    )
    with_ga4 = calculate_confidence(
        before_metrics={"gsc": {"impressions": 500}, "ga4": {"conversions": 4}},
        after_metrics={"gsc": {"impressions": 600}, "ga4": {"conversions": 6}},
        control_metrics=None,
        window_days=28,
        outcome_deltas=deltas,
    )

    assert with_ga4 > without_ga4


def test_confidence_score_increases_with_control_group() -> None:
    deltas = {
        "impressions": 0.5,
        "clicks": 0.5,
        "ctr": 0,
        "position": 0,
        "conversions": 0,
        "revenue": 0,
        "score": 0,
    }

    without_control = calculate_confidence(
        before_metrics={"gsc": {"impressions": 500}},
        after_metrics={"gsc": {"impressions": 600}},
        control_metrics=None,
        window_days=28,
        outcome_deltas=deltas,
    )
    with_control = calculate_confidence(
        before_metrics={"gsc": {"impressions": 500}},
        after_metrics={"gsc": {"impressions": 600}},
        control_metrics={"impressions_before": 500, "impressions_after": 520},
        window_days=28,
        outcome_deltas=deltas,
    )

    assert with_control > without_control


def test_confidence_score_reduces_when_signals_contradict() -> None:
    consistent = calculate_confidence(
        before_metrics={"gsc": {"impressions": 500}, "ga4": {"conversions": 4}},
        after_metrics={"gsc": {"impressions": 800}, "ga4": {"conversions": 8}},
        control_metrics={"impressions_before": 500, "impressions_after": 520},
        window_days=28,
        outcome_deltas={
            "impressions": 0.5,
            "clicks": 0.5,
            "ctr": 0.1,
            "position": 0.2,
            "conversions": 0.5,
            "revenue": 0.5,
            "score": 0.5,
        },
    )
    contradictory = calculate_confidence(
        before_metrics={"gsc": {"impressions": 500}, "ga4": {"conversions": 4}},
        after_metrics={"gsc": {"impressions": 800}, "ga4": {"conversions": 1}},
        control_metrics={"impressions_before": 500, "impressions_after": 520},
        window_days=28,
        outcome_deltas={
            "impressions": 0.5,
            "clicks": -0.5,
            "ctr": 0.1,
            "position": -0.2,
            "conversions": -0.5,
            "revenue": 0.5,
            "score": -0.5,
        },
    )

    assert contradictory < consistent


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
