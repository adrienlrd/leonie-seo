"""Tests for the learning scheduler."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from app.db import init_db
from app.db_adapter import get_conn
from app.geo.ledger import create_geo_event
from app.learning.models import LearningObservation
from app.learning.scheduler import create_due_observations, run_learning_cycle
from app.learning.store import list_observations, list_runs, update_settings

SHOP = "store.myshopify.com"
PRODUCT_ID = "gid://shopify/Product/1"


def _event(db: Path, *, age_days: int, metrics_after: dict | None = None) -> int:
    event_id = create_geo_event(
        shop=SHOP,
        event_type="content_applied",
        resource_type="product",
        resource_id=PRODUCT_ID,
        resource_title="Harnais",
        action_type="meta_title",
        status="applied",
        before_snapshot={},
        metrics_before={"gsc": {"impressions": 100, "clicks": 5}},
        metrics_after=metrics_after or {"gsc": {"impressions": 140, "clicks": 8}},
        estimated_impact={"keyword_source": "gsc"},
        score_before=50,
        score_after=65,
        db_path=db,
    )
    created = (datetime.now(UTC) - timedelta(days=age_days)).isoformat()
    history = json.dumps([{"status": "applied", "changed_at": created}])
    with get_conn(db) as conn:
        conn.execute(
            "UPDATE geo_impact_events SET created_at = ?, status_history = ? WHERE id = ?",
            (created, history, event_id),
        )
    return event_id


def test_create_due_observations_creates_j14_observation(tmp_path: Path) -> None:
    db = tmp_path / "history.db"
    init_db(db)
    _event(db, age_days=14)

    observations, skipped = create_due_observations(SHOP, db_path=db)

    assert skipped == 0
    assert len(observations) == 1
    assert observations[0].window_label == "J+14"
    assert observations[0].is_primary_window is False


def test_create_due_observations_creates_j28_primary_observation(tmp_path: Path) -> None:
    db = tmp_path / "history.db"
    init_db(db)
    _event(db, age_days=28)

    observations, _skipped = create_due_observations(SHOP, db_path=db)

    labels = {observation.window_label: observation for observation in observations}
    assert labels["J+14"].is_primary_window is False
    assert labels["J+28"].is_primary_window is True


def test_create_due_observations_does_not_create_before_j14(tmp_path: Path) -> None:
    db = tmp_path / "history.db"
    init_db(db)
    _event(db, age_days=13)

    observations, skipped = create_due_observations(SHOP, db_path=db)

    assert observations == []
    assert skipped == 0


def test_create_due_observations_does_not_duplicate_existing_observation(
    tmp_path: Path,
) -> None:
    db = tmp_path / "history.db"
    init_db(db)
    _event(db, age_days=14)

    first, _ = create_due_observations(SHOP, db_path=db)
    second, skipped = create_due_observations(SHOP, db_path=db)

    assert len(first) == 1
    assert second == []
    assert skipped == 1
    assert len(list_observations(SHOP, db_path=db)) == 1


def test_create_due_observations_marks_overlapping_actions_as_polluted(
    tmp_path: Path,
) -> None:
    db = tmp_path / "history.db"
    init_db(db)
    first_event_id = _event(db, age_days=60)
    second_event_id = _event(db, age_days=50)

    observations, _skipped = create_due_observations(SHOP, db_path=db)

    first_j28 = next(
        observation
        for observation in observations
        if observation.ledger_event_id == first_event_id and observation.window_label == "J+28"
    )
    second_j28 = next(
        observation
        for observation in observations
        if observation.ledger_event_id == second_event_id and observation.window_label == "J+28"
    )
    assert first_j28.metadata["experiment_verdict"] == "polluted_window"
    assert first_j28.metadata["learnable"] is False
    assert second_j28.metadata["learnable"] is True


def test_create_due_observations_builds_automatic_control_group(
    tmp_path: Path,
    monkeypatch,
) -> None:
    db = tmp_path / "history.db"
    init_db(db)
    data_dir = tmp_path / "data"
    shop_dir = data_dir / SHOP
    shop_dir.mkdir(parents=True)
    control_products = [
        {
            "product_id": PRODUCT_ID,
            "product_title": "Harnais chien",
            "product_type": "Harnais",
            "opportunity_score": 70,
            "seo_keywords": [
                {
                    "query": "harnais chien",
                    "target_role": "primary",
                    "data_source": "gsc",
                    "gsc_impressions": 1000,
                    "gsc_clicks": 50,
                    "gsc_position": 8,
                }
            ],
        }
    ]
    for index, before in enumerate((100, 200, 300), start=2):
        control_products.append(
            {
                "product_id": f"gid://shopify/Product/{index}",
                "product_title": f"Harnais témoin {index}",
                "product_type": "Harnais",
                "opportunity_score": 70,
                "seo_keywords": [
                    {
                        "query": "harnais chien",
                        "target_role": "primary",
                        "data_source": "gsc",
                        "gsc_impressions": 1000,
                        "gsc_clicks": 50,
                        "gsc_position": 8,
                    }
                ],
                "learning_metrics": {
                    "J+28": {
                        "before": {"gsc": {"impressions": before, "clicks": before // 10}},
                        "after": {
                            "gsc": {"impressions": int(before * 1.1), "clicks": before // 10 + 1}
                        },
                    }
                },
            }
        )
    (shop_dir / "market_analysis_latest.json").write_text(
        json.dumps({"products": control_products}, ensure_ascii=False),
        encoding="utf-8",
    )
    monkeypatch.setattr("app.market_analysis.jobs._DATA_DIR", data_dir)
    _event(db, age_days=28)

    observations, _skipped = create_due_observations(SHOP, db_path=db)

    j28 = next(observation for observation in observations if observation.window_label == "J+28")
    assert j28.control_metrics["control_size"] == 3
    assert j28.control_metrics["impressions_before"] == 200
    assert j28.control_metrics["impressions_after"] == 220


def test_create_due_observations_keeps_j60_as_historical_window(tmp_path: Path) -> None:
    db = tmp_path / "history.db"
    init_db(db)
    _event(db, age_days=60)

    observations, _ = create_due_observations(SHOP, db_path=db)

    labels = {observation.window_label: observation for observation in observations}
    assert labels["J+60"].is_primary_window is False
    assert labels["J+28"].is_primary_window is True


def test_run_learning_cycle_creates_observations_weights_and_run(tmp_path: Path) -> None:
    db = tmp_path / "history.db"
    init_db(db)
    _event(db, age_days=28)
    update_settings(SHOP, {"enabled": False}, db_path=db)

    result = run_learning_cycle(SHOP, db_path=db)

    runs = list_runs(SHOP, db_path=db)
    assert result["status"] == "completed"
    assert result["observations_created"] == 2
    assert result["weights_updated"] > 0
    assert runs[0]["id"] == result["run_id"]


def test_run_learning_cycle_launches_continuous_agent_when_enabled(tmp_path: Path) -> None:
    db = tmp_path / "history.db"
    init_db(db)
    update_settings(SHOP, {"enabled": True, "mode": "semi_auto"}, db_path=db)

    with patch(
        "app.geo.continuous_agent.run_continuous_improvement_agent",
        return_value={
            "summary": {
                "candidate_actions": 3,
                "learning_approvals_created": 2,
                "applied": 0,
            }
        },
    ) as run_agent:
        result = run_learning_cycle(SHOP, access_token="token", plan="pro", db_path=db)

    run_agent.assert_called_once()
    assert result["actions_reprioritized"] == 3
    assert result["approvals_created"] == 2


def test_run_learning_cycle_passes_auto_publish_scopes_to_continuous_agent(
    tmp_path: Path,
) -> None:
    db = tmp_path / "history.db"
    init_db(db)
    update_settings(
        SHOP,
        {"enabled": True, "mode": "auto_apply", "auto_publish_scopes": ["meta_title"]},
        db_path=db,
    )

    with patch(
        "app.geo.continuous_agent.run_continuous_improvement_agent",
        return_value={"summary": {"candidate_actions": 0, "applied": 0}},
    ) as run_agent:
        run_learning_cycle(SHOP, access_token="token", plan="pro", db_path=db)

    run_agent.assert_called_once()
    assert run_agent.call_args.kwargs["auto_publish_scopes"] == ["meta_title"]


def test_run_learning_cycle_fail_open_when_observation_stage_fails(tmp_path: Path) -> None:
    db = tmp_path / "history.db"
    init_db(db)
    update_settings(SHOP, {"enabled": False}, db_path=db)

    with patch(
        "app.learning.scheduler.create_due_observations",
        side_effect=RuntimeError("boom"),
    ):
        result = run_learning_cycle(SHOP, db_path=db)

    assert result["status"] == "completed_with_errors"
    assert result["errors"][0]["stage"] == "observations"
    assert list_runs(SHOP, db_path=db)[0]["status"] == "completed_with_errors"


def test_run_learning_cycle_fail_open_when_continuous_agent_fails(tmp_path: Path) -> None:
    db = tmp_path / "history.db"
    init_db(db)
    update_settings(SHOP, {"enabled": True, "mode": "semi_auto"}, db_path=db)
    observation = LearningObservation(
        shop=SHOP,
        resource_type="product",
        resource_id=PRODUCT_ID,
        action_type="meta_title",
        surface="product_page",
        keyword_source="gsc",
        before_metrics={},
        after_metrics={},
        control_metrics={},
        window_days=28,
        window_label="J+28",
        is_primary_window=True,
        outcome_score=80,
        confidence_score=80,
        features=[("action_type", "meta_title")],
    )

    with (
        patch("app.learning.scheduler.create_due_observations", return_value=([observation], 0)),
        patch(
            "app.geo.continuous_agent.run_continuous_improvement_agent",
            side_effect=RuntimeError("agent failed"),
        ),
    ):
        result = run_learning_cycle(SHOP, db_path=db)

    assert result["status"] == "completed_with_errors"
    assert result["weights_updated"] > 0
    assert result["errors"][0]["stage"] == "continuous_agent"
