"""Tests for the lazy measurement loop (measurement_loop.py)."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from app.geo.measurement_loop import (
    build_verdict_summary,
    collect_metrics_for_url,
    run_measurement_loop,
)


@pytest.fixture()
def db_path(tmp_path: Path) -> Path:
    path = tmp_path / "history.db"
    conn = sqlite3.connect(str(path))
    conn.execute(
        """CREATE TABLE IF NOT EXISTS geo_impact_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            shop TEXT NOT NULL,
            created_at TEXT NOT NULL,
            event_type TEXT NOT NULL,
            resource_type TEXT NOT NULL,
            resource_id TEXT NOT NULL,
            resource_title TEXT NOT NULL DEFAULT '',
            action_type TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'planned',
            source TEXT NOT NULL DEFAULT 'geo',
            job_id TEXT,
            snapshot_id INTEGER,
            hypothesis TEXT,
            score_before INTEGER,
            score_after INTEGER,
            measurement_status TEXT NOT NULL DEFAULT 'not_started',
            status_history TEXT,
            before_snapshot TEXT NOT NULL,
            after_snapshot TEXT,
            metrics_before TEXT NOT NULL,
            metrics_after TEXT,
            estimated_impact TEXT NOT NULL,
            observed_impact TEXT,
            notes TEXT
        )"""
    )
    conn.commit()
    conn.close()
    return path


def _insert_event(
    db_path: Path,
    *,
    shop: str = "test.myshopify.com",
    days_ago: int = 20,
    status: str = "applied",
    measurement_status: str = "baseline_captured",
    metrics_after: str | None = None,
    resource_path: str = "/products/harnais-premium",
) -> int:
    import json

    now = datetime.now(UTC)
    created_at = (now - timedelta(days=days_ago)).isoformat()
    status_history = json.dumps(
        [{"status": "applied", "changed_at": created_at}]
    )
    before_snapshot = json.dumps({"path": resource_path})
    metrics_before = json.dumps({
        "gsc": {"clicks": 10, "impressions": 200, "ctr": 0.05, "position": 15.0},
    })

    conn = sqlite3.connect(str(db_path))
    conn.execute(
        """INSERT INTO geo_impact_events
           (shop, created_at, event_type, resource_type, resource_id, resource_title,
            action_type, status, source, measurement_status, status_history,
            before_snapshot, metrics_before, metrics_after, estimated_impact)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            shop, created_at, "applied_optimization", "product",
            "gid://shopify/Product/123", "Harnais Premium",
            "enrich_facts", status, "auto_apply",
            measurement_status, status_history,
            before_snapshot, metrics_before, metrics_after, "{}",
        ),
    )
    conn.commit()
    last_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.close()
    return last_id


def test_collect_metrics_for_url_finds_matching_gsc_row() -> None:
    gsc_rows = {
        "https://test.myshopify.com/products/harnais-premium": {
            "clicks": 25, "impressions": 500, "ctr": 0.05, "position": 8.0,
        }
    }
    result = collect_metrics_for_url("/products/harnais-premium", gsc_rows)

    assert result["gsc"]["clicks"] == 25
    assert result["gsc"]["impressions"] == 500


def test_collect_metrics_for_url_returns_zeros_when_no_match() -> None:
    result = collect_metrics_for_url("/products/unknown", {})

    assert result["gsc"]["clicks"] == 0
    assert result["gsc"]["impressions"] == 0


def test_collect_metrics_for_url_includes_ga4_data() -> None:
    ga4_data = {
        "/products/harnais-premium": {
            "sessions": 100, "conversions": 5, "revenue": 250.0,
        }
    }
    result = collect_metrics_for_url("/products/harnais-premium", {}, ga4_data)

    assert result["ga4"]["sessions"] == 100
    assert result["ga4"]["revenue"] == 250.0


def test_run_measurement_loop_measures_mature_event(db_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _insert_event(db_path, days_ago=20)

    monkeypatch.setattr(
        "app.geo.measurement_loop._refresh_gsc_if_needed",
        lambda shop: {"status": "fresh"},
    )
    monkeypatch.setattr(
        "app.geo.measurement_loop._find_gsc_file",
        lambda shop: None,
    )
    monkeypatch.setattr(
        "app.geo.measurement_loop._load_ga4_page_data",
        lambda shop: None,
    )

    result = run_measurement_loop("test.myshopify.com", db_path=db_path)

    assert result["events_checked"] == 1
    assert result["events_updated"] == 1

    # Verify event was updated
    import json
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM geo_impact_events WHERE id = 1").fetchone()
    conn.close()

    assert row["status"] == "measured"
    assert "j14_measured" in row["measurement_status"]
    assert row["metrics_after"] is not None
    observed = json.loads(row["observed_impact"])
    assert "impressions_delta_pct" in observed


def test_run_measurement_loop_skips_already_measured_event(db_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _insert_event(db_path, days_ago=20, measurement_status="j14_measured")

    monkeypatch.setattr(
        "app.geo.measurement_loop._refresh_gsc_if_needed",
        lambda shop: {"status": "fresh"},
    )
    monkeypatch.setattr(
        "app.geo.measurement_loop._find_gsc_file",
        lambda shop: None,
    )
    monkeypatch.setattr(
        "app.geo.measurement_loop._load_ga4_page_data",
        lambda shop: None,
    )

    result = run_measurement_loop("test.myshopify.com", db_path=db_path)

    assert result["events_checked"] == 1
    assert result["events_updated"] == 0
    assert result["events_skipped"] == 1


def test_run_measurement_loop_skips_too_recent_event(db_path: Path) -> None:
    _insert_event(db_path, days_ago=5)

    result = run_measurement_loop("test.myshopify.com", db_path=db_path)

    assert result["events_checked"] == 1
    assert result["events_updated"] == 0


def test_run_measurement_loop_measures_j28_window(db_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _insert_event(db_path, days_ago=30, measurement_status="j14_measured")

    monkeypatch.setattr(
        "app.geo.measurement_loop._refresh_gsc_if_needed",
        lambda shop: {"status": "fresh"},
    )
    monkeypatch.setattr(
        "app.geo.measurement_loop._find_gsc_file",
        lambda shop: None,
    )
    monkeypatch.setattr(
        "app.geo.measurement_loop._load_ga4_page_data",
        lambda shop: None,
    )

    result = run_measurement_loop("test.myshopify.com", db_path=db_path)

    assert result["events_updated"] == 1

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM geo_impact_events WHERE id = 1").fetchone()
    conn.close()
    assert "j28_measured" in row["measurement_status"]


def test_build_verdict_summary_with_gsc_deltas() -> None:
    report = {
        "gsc": {
            "impressions_before": 200,
            "impressions_after": 350,
            "clicks_before": 10,
            "clicks_after": 18,
            "position_before": 15.0,
            "position_after": 9.2,
        },
        "scores": {"geo_delta": 12},
    }
    summary = build_verdict_summary(report, locale="fr")

    assert "Impressions +75 %" in summary
    assert "score GEO +12 pts" in summary


def test_build_verdict_summary_awaiting_data() -> None:
    report = {
        "gsc": {"impressions_before": 200, "impressions_after": None},
        "scores": {"geo_delta": None},
    }
    summary = build_verdict_summary(report, locale="fr")

    assert "attente" in summary.lower()


def test_build_verdict_summary_no_change() -> None:
    report = {
        "gsc": {
            "impressions_before": 0,
            "impressions_after": 0,
            "clicks_before": 0,
            "clicks_after": 0,
            "position_before": 0.0,
            "position_after": 0.0,
        },
        "scores": {"geo_delta": 0},
    }
    summary = build_verdict_summary(report, locale="fr")

    assert "changement" in summary.lower()
