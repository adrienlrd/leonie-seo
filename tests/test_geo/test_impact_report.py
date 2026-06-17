"""Tests for the GEO before/after impact report (task 122)."""

from __future__ import annotations

from app.geo.impact_report import (
    build_catalog_report,
    build_event_report,
    render_markdown,
)


def _event(
    *,
    eid: int = 1,
    resource_title: str = "Harnais nylon chien",
    action_type: str = "enrich_facts",
    score_before: int | None = 60,
    score_after: int | None = 75,
    impressions_before: int = 500,
    impressions_after: int | None = 800,
    observed_revenue: float | None = None,
    status: str = "applied",
) -> dict:
    metrics_before = {
        "gsc": {
            "impressions": impressions_before,
            "clicks": 30,
            "ctr": 0.06,
            "position": 12.0,
        }
    }
    metrics_after = (
        {
            "gsc": {
                "impressions": impressions_after,
                "clicks": 50,
                "ctr": 0.063,
                "position": 10.5,
            }
        }
        if impressions_after is not None
        else None
    )
    observed_impact = {"revenue": observed_revenue} if observed_revenue is not None else None
    return {
        "id": eid,
        "resource_type": "product",
        "resource_id": "gid://shopify/Product/123",
        "resource_title": resource_title,
        "action_type": action_type,
        "status": status,
        "created_at": "2026-02-18T10:00:00+00:00",
        "status_history": [{"status": "applied", "changed_at": "2026-02-18T10:00:00+00:00"}],
        "score_before": score_before,
        "score_after": score_after,
        "metrics_before": metrics_before,
        "metrics_after": metrics_after,
        "observed_impact": observed_impact,
        "before_snapshot": {},
        "after_snapshot": None,
        "estimated_impact": {"revenue_estimate": 200.0},
    }


def _confidence(*, eid: int = 1, score: int = 65, label: str = "impact_probable") -> dict:
    return {"event_id": eid, "score": score, "label": label}


def test_geo_delta_is_computed_from_score_before_and_after() -> None:
    event = _event(score_before=60, score_after=75)
    report = build_event_report(event, _confidence())

    assert report["scores"]["geo_before"] == 60
    assert report["scores"]["geo_after"] == 75
    assert report["scores"]["geo_delta"] == 15


def test_geo_delta_is_none_when_score_after_missing() -> None:
    event = _event(score_before=60, score_after=None)
    report = build_event_report(event, _confidence())

    assert report["scores"]["geo_delta"] is None


def test_verdict_is_positif_probable_when_confidence_high_and_geo_delta_positive() -> None:
    event = _event(score_before=60, score_after=75)
    report = build_event_report(event, _confidence(score=65))

    assert report["verdict"] == "positif_probable"
    assert report["next_recommendation"] == "répliquer"


def test_verdict_is_negatif_possible_when_geo_delta_negative_and_no_gsc_improvement() -> None:
    event = _event(score_before=75, score_after=60, impressions_after=None)
    report = build_event_report(event, _confidence(score=70))

    assert report["verdict"] == "négatif_possible"
    assert report["next_recommendation"] == "rollback"


def test_verdict_is_neutre_when_geo_delta_negative_but_gsc_impressions_up() -> None:
    event = _event(score_before=75, score_after=60, impressions_before=500, impressions_after=800)
    report = build_event_report(event, _confidence(score=70))

    assert report["verdict"] == "neutre"
    assert report["next_recommendation"] == "ajuster"


def test_verdict_is_inconclusif_when_confidence_below_25() -> None:
    event = _event(score_before=60, score_after=60)
    report = build_event_report(event, _confidence(score=10, label="données_insuffisantes"))

    assert report["verdict"] == "inconclusif"
    assert report["next_recommendation"] == "attendre"


def test_gsc_impressions_delta_is_computed() -> None:
    event = _event(impressions_before=500, impressions_after=800)
    report = build_event_report(event, _confidence())

    assert report["gsc"]["impressions_before"] == 500
    assert report["gsc"]["impressions_after"] == 800
    assert report["gsc"]["impressions_delta"] == 300


def test_gsc_fields_are_none_when_no_metrics_after() -> None:
    event = _event(impressions_after=None)
    report = build_event_report(event, _confidence())

    assert report["gsc"]["impressions_after"] is None
    assert report["gsc"]["impressions_delta"] is None


def test_render_markdown_contains_resource_title() -> None:
    event = _event(resource_title="Harnais nylon chien")
    report = build_event_report(event, _confidence())
    md = render_markdown([report])

    assert "Harnais nylon chien" in md
    assert "# Rapport d'impact GEO" in md


def test_build_catalog_report_returns_correct_summary() -> None:
    events = [
        _event(eid=1, score_before=60, score_after=75),
        _event(eid=2, score_before=70, score_after=65, impressions_after=None),
    ]
    confidences = [
        _confidence(eid=1, score=65, label="impact_probable"),
        _confidence(eid=2, score=70, label="impact_probable"),
    ]
    result = build_catalog_report(events, confidences)

    assert result["summary"]["total"] == 2
    assert result["summary"]["by_verdict"]["positif_probable"] >= 1
    assert result["summary"]["by_verdict"]["négatif_possible"] >= 1
    assert len(result["reports"]) == 2
