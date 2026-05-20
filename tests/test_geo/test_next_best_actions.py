"""Tests for the GEO next best action loop (task 125)."""

from __future__ import annotations

from app.geo.next_best_actions import build_next_best_actions


def _report(
    *,
    eid: int = 1,
    resource_id: str = "p1",
    resource_title: str = "Harnais nylon",
    action_type: str = "enrich_facts",
    verdict: str = "positif_probable",
    next_recommendation: str = "répliquer",
) -> dict:
    return {
        "event_id": eid,
        "resource_id": resource_id,
        "resource_title": resource_title,
        "resource_type": "product",
        "action_type": action_type,
        "verdict": verdict,
        "next_recommendation": next_recommendation,
        "scores": {"geo_delta": 15},
    }


def _snapshot(*product_ids_types: tuple[str, str, str, str]) -> dict:
    """Build minimal snapshot with (id, title, product_type, vendor) tuples."""
    return {
        "products": [
            {"id": pid, "title": title, "product_type": ptype, "vendor": vendor}
            for pid, title, ptype, vendor in product_ids_types
        ]
    }


def test_win_report_produces_repliquer_action() -> None:
    reports = [_report(verdict="positif_probable", next_recommendation="répliquer")]
    result = build_next_best_actions(reports)

    assert result["actions"][0]["action_type"] == "répliquer"
    assert result["actions"][0]["priority"] == "high"
    assert result["dry_run"] is True


def test_risk_report_produces_rollback_action() -> None:
    reports = [_report(verdict="négatif_possible", next_recommendation="rollback")]
    result = build_next_best_actions(reports)

    assert result["actions"][0]["action_type"] == "rollback"
    assert result["actions"][0]["priority"] == "high"


def test_neutral_report_produces_ajuster_action() -> None:
    reports = [_report(verdict="neutre", next_recommendation="ajuster")]
    result = build_next_best_actions(reports)

    assert result["actions"][0]["action_type"] == "ajuster"
    assert result["actions"][0]["priority"] == "medium"


def test_inconclusive_report_produces_attendre_action() -> None:
    reports = [_report(verdict="inconclusif", next_recommendation="attendre")]
    result = build_next_best_actions(reports)

    assert result["actions"][0]["action_type"] == "attendre"
    assert result["actions"][0]["priority"] == "low"


def test_similar_products_suggested_for_win_with_snapshot() -> None:
    reports = [_report(resource_id="p1", verdict="positif_probable", next_recommendation="répliquer")]
    snapshot = _snapshot(
        ("p1", "Harnais nylon", "Harnais", "BrandA"),
        ("p2", "Harnais cuir", "Harnais", "BrandB"),
        ("p3", "Laisse sport", "Laisse", "BrandC"),
    )
    result = build_next_best_actions(reports, snapshot=snapshot)

    suggestions = result["actions"][0]["suggested_resources"]
    assert len(suggestions) == 1
    assert suggestions[0]["resource_id"] == "p2"


def test_similar_products_excludes_unlisted_products_when_scope_is_active() -> None:
    reports = [_report(resource_id="p1", verdict="positif_probable", next_recommendation="répliquer")]
    snapshot = {
        "products": [
            {
                "id": "p1",
                "title": "Harnais nylon",
                "product_type": "Harnais",
                "vendor": "BrandA",
                "status": "ACTIVE",
                "onlineStoreUrl": "https://example.com/products/p1",
            },
            {
                "id": "p2",
                "title": "Harnais cuir",
                "product_type": "Harnais",
                "vendor": "BrandA",
                "status": "ACTIVE",
                "onlineStoreUrl": None,
            },
        ]
    }

    result = build_next_best_actions(reports, snapshot=snapshot)

    assert result["actions"][0]["suggested_resources"] == []
    assert result["scope"]["counts"]["unlisted"] == 1


def test_already_optimized_pages_excluded_from_suggestions() -> None:
    reports = [
        _report(eid=1, resource_id="p1", verdict="positif_probable", next_recommendation="répliquer"),
        _report(eid=2, resource_id="p2", verdict="neutre", next_recommendation="ajuster"),
    ]
    snapshot = _snapshot(
        ("p1", "Harnais nylon", "Harnais", "BrandA"),
        ("p2", "Harnais cuir", "Harnais", "BrandA"),
        ("p3", "Harnais sport", "Harnais", "BrandA"),
    )
    result = build_next_best_actions(reports, snapshot=snapshot)

    win_action = next(a for a in result["actions"] if a["source_event_id"] == 1)
    suggested_ids = {s["resource_id"] for s in win_action["suggested_resources"]}
    assert "p2" not in suggested_ids  # p2 is already optimized
    assert "p3" in suggested_ids


def test_summary_counts_actions_by_type() -> None:
    reports = [
        _report(eid=1, verdict="positif_probable", next_recommendation="répliquer"),
        _report(eid=2, verdict="négatif_possible", next_recommendation="rollback"),
        _report(eid=3, verdict="inconclusif", next_recommendation="attendre"),
    ]
    result = build_next_best_actions(reports)

    assert result["summary"]["total_actions"] == 3
    assert result["summary"]["high_priority"] == 2
    assert result["summary"]["by_action"]["répliquer"] == 1
    assert result["summary"]["by_action"]["rollback"] == 1
    assert result["summary"]["by_action"]["attendre"] == 1


def test_high_priority_actions_sorted_first() -> None:
    reports = [
        _report(eid=1, verdict="inconclusif", next_recommendation="attendre"),
        _report(eid=2, verdict="positif_probable", next_recommendation="répliquer"),
        _report(eid=3, verdict="neutre", next_recommendation="ajuster"),
    ]
    result = build_next_best_actions(reports)

    priorities = [a["priority"] for a in result["actions"]]
    assert priorities[0] == "high"
    assert priorities[-1] == "low"
