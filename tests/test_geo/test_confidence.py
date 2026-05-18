"""Tests for the GEO impact confidence scorer (task 121)."""

from __future__ import annotations

from datetime import UTC, datetime

from app.geo.confidence import compute_catalog_confidence, compute_event_confidence


def _event(
    *,
    created_at: str = "2026-04-19T10:00:00+00:00",
    status: str = "applied",
    score_before: int | None = 60,
    score_after: int | None = None,
    impressions_before: int = 200,
    impressions_after: int | None = None,
    observed_revenue: float | None = None,
    inventory: int | None = 5,
    price_before: str | None = "49.90",
    price_after: str | None = None,
) -> dict:
    metrics_before = {"gsc": {"impressions": impressions_before, "clicks": 10, "ctr": 0.05, "position": 12.0}}
    metrics_after = (
        {"gsc": {"impressions": impressions_after, "clicks": 15, "ctr": 0.07, "position": 10.0}}
        if impressions_after is not None
        else None
    )
    observed_impact = {"revenue": observed_revenue} if observed_revenue is not None else None
    before_snapshot = {
        "commerce": {"inventory_quantity": inventory, "price": price_before}
    }
    after_snapshot = (
        {"commerce": {"inventory_quantity": inventory, "price": price_after or price_before}}
        if price_after or price_after is not None
        else None
    )
    return {
        "id": 42,
        "created_at": created_at,
        "status": status,
        "measurement_status": "baseline_captured",
        "score_before": score_before,
        "score_after": score_after,
        "status_history": [{"status": "applied", "changed_at": created_at}],
        "metrics_before": metrics_before,
        "metrics_after": metrics_after,
        "observed_impact": observed_impact,
        "before_snapshot": before_snapshot,
        "after_snapshot": after_snapshot,
        "estimated_impact": {"revenue_estimate": 100.0},
    }


_NOW = datetime(2026, 5, 19, tzinfo=UTC)


def test_confidence_label_is_insuffisant_when_event_too_recent() -> None:
    event = _event(created_at="2026-05-18T10:00:00+00:00")  # 1 day ago
    result = compute_event_confidence(event, now=_NOW)

    assert result["label"] == "données_insuffisantes"
    assert result["factors"]["elapsed_score"] == 0
    assert result["score"] < 25  # well below signal_faible threshold
    assert any("tôt" in note for note in result["notes"])


def test_confidence_elapsed_score_is_40_after_90_days() -> None:
    event = _event(created_at="2026-02-17T10:00:00+00:00")  # 91 days ago
    result = compute_event_confidence(event, now=_NOW)

    assert result["factors"]["elapsed_score"] == 40
    assert result["factors"]["elapsed_days"] >= 90


def test_confidence_delta_score_is_15_when_geo_score_improved() -> None:
    event = _event(
        created_at="2026-02-18T10:00:00+00:00",
        score_before=60,
        score_after=75,
    )
    result = compute_event_confidence(event, now=_NOW)

    assert result["factors"]["delta_score"] == 15
    assert any("GEO" in note for note in result["notes"])


def test_confidence_delta_score_is_zero_when_no_improvement() -> None:
    event = _event(
        created_at="2026-02-18T10:00:00+00:00",
        score_before=60,
        score_after=60,
    )
    result = compute_event_confidence(event, now=_NOW)

    assert result["factors"]["delta_score"] == 0


def test_confidence_revenue_score_is_10_when_observed_revenue_positive() -> None:
    event = _event(
        created_at="2026-02-18T10:00:00+00:00",
        observed_revenue=250.0,
    )
    result = compute_event_confidence(event, now=_NOW)

    assert result["factors"]["revenue_score"] == 10
    assert any("Revenu" in note for note in result["notes"])


def test_confidence_score_is_zero_for_rolled_back_event() -> None:
    event = _event(status="rolled_back")
    result = compute_event_confidence(event, now=_NOW)

    assert result["score"] == 0
    assert result["label"] == "données_insuffisantes"
    assert any("rolled_back" in note for note in result["notes"])


def test_confidence_label_is_impact_fort_when_score_75_plus() -> None:
    # 90 days → 40 pts elapsed
    # 1000 impressions → 15 pts volume
    # score improved → 15 pts delta
    # revenue → 10 pts
    # = 80 pts → impact_fort
    event = _event(
        created_at="2026-02-18T10:00:00+00:00",
        score_before=60,
        score_after=80,
        impressions_before=1000,
        impressions_after=1200,
        observed_revenue=300.0,
    )
    result = compute_event_confidence(event, now=_NOW)

    assert result["score"] >= 75
    assert result["label"] == "impact_fort"


def test_confidence_gsc_score_awarded_when_impressions_increased() -> None:
    event = _event(
        created_at="2026-02-18T10:00:00+00:00",
        impressions_before=500,
        impressions_after=800,
    )
    result = compute_event_confidence(event, now=_NOW)

    assert result["factors"]["gsc_score"] == 10


def test_confidence_gsc_score_zero_when_no_metrics_after() -> None:
    event = _event(created_at="2026-02-18T10:00:00+00:00", impressions_after=None)
    result = compute_event_confidence(event, now=_NOW)

    assert result["factors"]["gsc_score"] == 0


def test_compute_catalog_confidence_returns_summary_over_multiple_events() -> None:
    events = [
        _event(created_at="2026-02-18T10:00:00+00:00", score_before=60, score_after=80),  # will score high
        _event(created_at="2026-05-18T10:00:00+00:00"),  # recent → low score
    ]
    result = compute_catalog_confidence(events, now=_NOW)

    assert result["summary"]["total_events"] == 2
    assert sum(result["summary"]["by_label"].values()) == 2
    assert 0 <= result["summary"]["avg_score"] <= 100
    assert len(result["scores"]) == 2
