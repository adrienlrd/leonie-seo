"""Tests for the 14/28-day automatic re-analysis cycle (Task 7)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi import HTTPException

from app.agent_schedule import reanalysis, scheduler
from app.agent_schedule.reanalysis import (
    is_reanalysis_due,
    run_market_reanalysis,
    run_scheduled_reanalysis,
)
from app.agent_schedule.scheduler import run_due_agent_schedules
from app.agent_schedule.store import get_schedule, upsert_schedule
from app.db import init_db
from app.learning.store import update_settings

SHOP = "store.myshopify.com"


@pytest.fixture(autouse=True)
def _paid_plan(monkeypatch: pytest.MonkeyPatch) -> None:
    """Auto-analysis is plan-gated; these tests exercise reanalysis, not billing."""
    monkeypatch.setattr(scheduler, "auto_analysis_allowed", lambda shop: True)


def _db(tmp_path: Path) -> Path:
    db = tmp_path / "history.db"
    init_db(db)
    return db


# ── is_reanalysis_due ────────────────────────────────────────────────────────


def test_is_reanalysis_due_when_never_run() -> None:
    assert is_reanalysis_due(None, 28, now=datetime.now(UTC)) is True


def test_is_reanalysis_due_false_within_14_day_window() -> None:
    now = datetime.now(UTC)
    last = (now - timedelta(days=10)).isoformat()
    assert is_reanalysis_due(last, 14, now=now) is False


def test_is_reanalysis_due_true_after_14_day_window() -> None:
    now = datetime.now(UTC)
    last = (now - timedelta(days=15)).isoformat()
    assert is_reanalysis_due(last, 14, now=now) is True


def test_is_reanalysis_due_true_after_1_day_window() -> None:
    now = datetime.now(UTC)
    last = (now - timedelta(days=1, minutes=1)).isoformat()
    assert is_reanalysis_due(last, 1, now=now) is True


def test_is_reanalysis_due_false_within_1_day_window() -> None:
    now = datetime.now(UTC)
    last = (now - timedelta(hours=2)).isoformat()
    assert is_reanalysis_due(last, 1, now=now) is False


def test_is_reanalysis_due_false_within_28_day_window() -> None:
    now = datetime.now(UTC)
    last = (now - timedelta(days=20)).isoformat()
    assert is_reanalysis_due(last, 28, now=now) is False


def test_is_reanalysis_due_true_after_28_day_window() -> None:
    now = datetime.now(UTC)
    last = (now - timedelta(days=29)).isoformat()
    assert is_reanalysis_due(last, 28, now=now) is True


# ── run_scheduled_reanalysis ─────────────────────────────────────────────────


def test_run_market_reanalysis_uses_rich_inputs_and_plan_cap(tmp_path: Path) -> None:
    """Re-analysis feeds GA4 + labels and restricts to managed products (parity with /jobs)."""
    db = _db(tmp_path)
    captured: dict = {}

    inputs = {
        "snapshot": {"collections": [], "articles": []},
        "products": [{"product_id": str(i)} for i in range(10)],
        "shop_domain": SHOP,
        "niche_hypothesis": {},
        "crawl_findings": [],
        "gsc_page_rows": {},
        "gsc_query_rows": [],
        "ga4_page_rows": {"p1": {"clicks": 5}},
        "identifications": {"1": "label"},
        "merchant_facts": {},
        "retired_questions": {},
        "business_profile": {},
        "merged_articles": [{"id": "a1"}],
    }

    def _fake_run(*args, **kwargs):
        captured["products"] = args[0]
        captured["kwargs"] = kwargs
        return {
            "analyzed_at": "2026-06-10T00:00:00+00:00",
            "active_product_count": 3,
            "analyzed_product_count": 3,
            "total_opportunity_count": 0,
            "sources_used": [],
            "products": [],
        }

    with (
        patch.object(reanalysis, "_gather_analysis_inputs", return_value=inputs),
        patch.object(
            reanalysis,
            "filter_managed_products",
            side_effect=lambda shop, products, db_path=None: products[:3],
        ),
        patch.object(reanalysis, "run_market_analysis", side_effect=_fake_run),
        patch.object(reanalysis, "get_shop_retired_tags", return_value=[]),
        patch.object(reanalysis, "_apply_retired_and_locked_keywords"),
        patch.object(reanalysis, "_attach_business_profile_context_status", side_effect=lambda d, *a, **k: d),
        patch.object(reanalysis, "enrich_market_analysis_result", side_effect=lambda s, d, *a, **k: d),
        patch.object(reanalysis, "_carry_forward_auto_publish_selection"),
        patch.object(reanalysis, "save_latest_result"),
        patch.object(reanalysis, "_auto_sync_schema_facts"),
        patch.object(reanalysis, "auto_create_orphan_drafts"),
        patch.object(reanalysis, "auto_publish_checked_proposals", return_value={"published": 0}),
    ):
        run_market_reanalysis(SHOP, access_token="shpat_test", plan="free", db_path=db)

    # Managed selection applied (10 products → 3) and rich inputs forwarded to the engine.
    assert len(captured["products"]) == 3
    assert captured["kwargs"]["ga4_page_rows"] == {"p1": {"clicks": 5}}
    assert captured["kwargs"]["product_labels"] == {"1": "label"}
    assert captured["kwargs"]["articles"] == [{"id": "a1"}]


def test_run_scheduled_reanalysis_runs_pipeline_in_order(tmp_path: Path) -> None:
    db = _db(tmp_path)
    calls: list[str] = []

    with (
        patch.object(
            reanalysis,
            "check_budget",
            return_value={"over_budget": False, "budget_usd": 20.0, "spent_usd": 0.0},
        ),
        patch.object(
            reanalysis,
            "_enqueue_refresh_jobs",
            side_effect=lambda *a, **k: calls.append("enqueue_refresh_jobs"),
        ),
        patch.object(
            reanalysis,
            "run_market_reanalysis",
            side_effect=lambda *a, **k: (calls.append("run_market_reanalysis") or {
                "analyzed_at": "2026-06-10T00:00:00+00:00",
                "analyzed_product_count": 1,
            }),
        ),
        patch.object(reanalysis, "get_plan_for_shop", return_value="pro"),
    ):
        outcome = run_scheduled_reanalysis(SHOP, access_token="shpat_test", db_path=db)

    assert outcome["status"] == "completed"
    assert calls == ["enqueue_refresh_jobs", "run_market_reanalysis"]


def test_run_scheduled_reanalysis_skips_heavy_pipeline_when_over_budget(tmp_path: Path) -> None:
    db = _db(tmp_path)

    with (
        patch.object(
            reanalysis,
            "check_budget",
            return_value={"over_budget": True, "budget_usd": 2.0, "spent_usd": 5.0},
        ),
        patch.object(reanalysis, "get_plan_for_shop", return_value="free"),
        patch.object(reanalysis, "_enqueue_refresh_jobs") as enqueue_jobs,
        patch.object(reanalysis, "run_market_reanalysis") as run_reanalysis,
    ):
        outcome = run_scheduled_reanalysis(SHOP, access_token="shpat_test", db_path=db)

    assert outcome["status"] == "skipped"
    assert outcome["reason"] == "budget_exceeded"
    enqueue_jobs.assert_not_called()
    run_reanalysis.assert_not_called()


def test_run_scheduled_reanalysis_skips_when_no_snapshot_on_disk(tmp_path: Path) -> None:
    db = _db(tmp_path)

    with (
        patch.object(
            reanalysis,
            "check_budget",
            return_value={"over_budget": False, "budget_usd": 20.0, "spent_usd": 0.0},
        ),
        patch.object(reanalysis, "get_plan_for_shop", return_value="pro"),
        patch.object(reanalysis, "_enqueue_refresh_jobs"),
        patch.object(
            reanalysis,
            "run_market_reanalysis",
            side_effect=HTTPException(status_code=404, detail="No crawl data found"),
        ),
    ):
        outcome = run_scheduled_reanalysis(SHOP, access_token="shpat_test", db_path=db)

    assert outcome["status"] == "skipped"
    assert outcome["reason"] == "no_snapshot"


# ── run_due_agent_schedules wiring ───────────────────────────────────────────


def test_run_due_triggers_reanalysis_when_due_and_updates_last_reanalysis_at(
    tmp_path: Path,
) -> None:
    db = _db(tmp_path)
    past = (datetime.now(UTC) - timedelta(minutes=1)).isoformat()
    upsert_schedule(SHOP, {"enabled": True, "next_run_at": past}, db_path=db)

    with (
        patch.object(scheduler, "load_latest_result", return_value={"products": []}),
        patch.object(
            scheduler, "run_learning_cycle", return_value={"run_id": 1, "status": "completed"}
        ),
        patch.object(scheduler, "get_token", return_value={"access_token": "shpat_test"}),
        patch.object(
            scheduler,
            "run_scheduled_reanalysis",
            return_value={"status": "completed", "analyzed_at": "2026-06-10T00:00:00+00:00"},
        ) as run_reanalysis,
    ):
        result = run_due_agent_schedules(db_path=db)

    run_reanalysis.assert_called_once()
    assert result["ran"][0]["reanalysis"]["status"] == "completed"
    schedule = get_schedule(SHOP, db_path=db)
    assert schedule.last_reanalysis_at is not None


def test_run_due_does_not_trigger_reanalysis_when_not_due(tmp_path: Path) -> None:
    db = _db(tmp_path)
    past = (datetime.now(UTC) - timedelta(minutes=1)).isoformat()
    recent_reanalysis = (datetime.now(UTC) - timedelta(days=1)).isoformat()
    upsert_schedule(
        SHOP,
        {"enabled": True, "next_run_at": past, "last_reanalysis_at": recent_reanalysis},
        db_path=db,
    )
    update_settings(SHOP, {"reanalysis_frequency_days": 28}, db_path=db)

    with (
        patch.object(scheduler, "load_latest_result", return_value={"products": []}),
        patch.object(
            scheduler, "run_learning_cycle", return_value={"run_id": 2, "status": "completed"}
        ),
        patch.object(scheduler, "run_scheduled_reanalysis") as run_reanalysis,
    ):
        result = run_due_agent_schedules(db_path=db)

    run_reanalysis.assert_not_called()
    assert result["ran"][0]["reanalysis"] is None
    schedule = get_schedule(SHOP, db_path=db)
    assert schedule.last_reanalysis_at == recent_reanalysis


def test_test_run_forces_reanalysis_even_when_not_due(tmp_path: Path) -> None:
    db = _db(tmp_path)
    past_test = (datetime.now(UTC) - timedelta(minutes=1)).isoformat()
    recent_reanalysis = (datetime.now(UTC) - timedelta(hours=1)).isoformat()
    upsert_schedule(
        SHOP,
        {"test_run_at": past_test, "last_reanalysis_at": recent_reanalysis},
        db_path=db,
    )
    update_settings(SHOP, {"reanalysis_frequency_days": 28}, db_path=db)

    with (
        patch.object(scheduler, "load_latest_result", return_value={"products": []}),
        patch.object(
            scheduler, "run_learning_cycle", return_value={"run_id": 9, "status": "completed"}
        ),
        patch.object(scheduler, "get_token", return_value={"access_token": "shpat_test"}),
        patch.object(
            scheduler,
            "run_scheduled_reanalysis",
            return_value={"status": "completed", "analyzed_at": "2026-06-10T00:00:00+00:00"},
        ) as run_reanalysis,
    ):
        result = run_due_agent_schedules(db_path=db)

    # Forced by the one-shot test even though the 28-day window has not elapsed.
    run_reanalysis.assert_called_once()
    assert result["ran"][0]["kind"] == "test"
    assert result["ran"][0]["reanalysis"]["status"] == "completed"


def test_run_due_skips_reanalysis_without_access_token_but_runs_learning_cycle(
    tmp_path: Path,
) -> None:
    db = _db(tmp_path)
    past = (datetime.now(UTC) - timedelta(minutes=1)).isoformat()
    upsert_schedule(SHOP, {"enabled": True, "next_run_at": past}, db_path=db)

    with (
        patch.object(scheduler, "load_latest_result", return_value={"products": []}),
        patch.object(
            scheduler, "run_learning_cycle", return_value={"run_id": 3, "status": "completed"}
        ) as run_cycle,
        patch.object(scheduler, "get_token", return_value=None),
    ):
        result = run_due_agent_schedules(db_path=db)

    run_cycle.assert_called_once()
    assert result["ran"][0]["reanalysis"] == {"status": "skipped", "reason": "no_access_token"}
    schedule = get_schedule(SHOP, db_path=db)
    assert schedule.last_reanalysis_at is None


def test_run_due_runs_learning_cycle_even_when_reanalysis_budget_exceeded(
    tmp_path: Path,
) -> None:
    db = _db(tmp_path)
    past = (datetime.now(UTC) - timedelta(minutes=1)).isoformat()
    upsert_schedule(SHOP, {"enabled": True, "next_run_at": past}, db_path=db)

    with (
        patch.object(scheduler, "load_latest_result", return_value={"products": []}),
        patch.object(
            scheduler, "run_learning_cycle", return_value={"run_id": 4, "status": "completed"}
        ) as run_cycle,
        patch.object(scheduler, "get_token", return_value={"access_token": "shpat_test"}),
        patch.object(
            scheduler,
            "run_scheduled_reanalysis",
            return_value={"status": "skipped", "reason": "budget_exceeded"},
        ),
    ):
        result = run_due_agent_schedules(db_path=db)

    run_cycle.assert_called_once()
    assert result["ran"][0]["reanalysis"]["reason"] == "budget_exceeded"
    schedule = get_schedule(SHOP, db_path=db)
    # Budget skip must not advance the cadence — retried on the next due tick.
    assert schedule.last_reanalysis_at is None


# ── _carry_forward_auto_publish_selection ────────────────────────────────────


def _completed(*product_ids: str) -> dict:
    return {
        "products": [
            {"product_id": pid, "content_test_pack": {"proposed_meta_title": "New"}}
            for pid in product_ids
        ]
    }


def test_carry_forward_uses_explicit_selection() -> None:
    data = _completed("gid://1", "gid://2")
    reanalysis._carry_forward_auto_publish_selection(
        SHOP, data, {"gid://1": ["meta_title"], "gid://2": ["description"]}
    )
    packs = {p["product_id"]: p["content_test_pack"] for p in data["products"]}
    assert packs["gid://1"]["auto_publish_fields"] == ["meta_title"]
    assert packs["gid://2"]["auto_publish_fields"] == ["description"]


def test_carry_forward_preserves_empty_selection() -> None:
    # Uncheck-all must survive: [] means "publish nothing for this product".
    data = _completed("gid://1")
    reanalysis._carry_forward_auto_publish_selection(SHOP, data, {"gid://1": []})
    assert data["products"][0]["content_test_pack"]["auto_publish_fields"] == []


def test_carry_forward_filters_unknown_fields() -> None:
    data = _completed("gid://1")
    reanalysis._carry_forward_auto_publish_selection(SHOP, data, {"gid://1": ["meta_title", "faq"]})
    assert data["products"][0]["content_test_pack"]["auto_publish_fields"] == ["meta_title"]


def test_carry_forward_reads_persisted_selection_when_none() -> None:
    data = _completed("gid://1", "gid://2")
    prior = {
        "products": [
            {"product_id": "gid://1", "content_test_pack": {"auto_publish_fields": []}},
            {"product_id": "gid://2", "content_test_pack": {"auto_publish_fields": ["meta_title"]}},
        ]
    }
    with patch.object(reanalysis, "load_latest_result", return_value=prior):
        reanalysis._carry_forward_auto_publish_selection(SHOP, data, None)
    packs = {p["product_id"]: p["content_test_pack"] for p in data["products"]}
    assert packs["gid://1"]["auto_publish_fields"] == []
    assert packs["gid://2"]["auto_publish_fields"] == ["meta_title"]
