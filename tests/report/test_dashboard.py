"""Tests for scripts.report.dashboard (data functions only, not Live rendering)."""

import json
import tempfile

import pandas as pd

from scripts.report.dashboard import (
    cannibalization_summary,
    eeat_summary,
    gsc_summary,
    quick_wins_list,
    top_pages_list,
)


def _write_json(data: object) -> str:
    with tempfile.NamedTemporaryFile(suffix=".json", mode="w", delete=False, encoding="utf-8") as f:
        json.dump(data, f)
        return f.name


def _write_csv(df: pd.DataFrame) -> str:
    with tempfile.NamedTemporaryFile(suffix=".csv", mode="w", delete=False, encoding="utf-8") as f:
        df.to_csv(f, index=False)
        return f.name


# ── gsc_summary ────────────────────────────────────────────────────────────


def test_gsc_summary_missing_file_returns_nulls():
    s = gsc_summary("/nonexistent/file.csv")
    assert s["clicks"] is None
    assert s["pages"] == 0


def test_gsc_summary_aggregates_correctly():
    df = pd.DataFrame(
        [
            {"url": "a", "clicks": 10, "impressions": 100, "ctr": 0.10, "position": 5.0},
            {"url": "b", "clicks": 20, "impressions": 200, "ctr": 0.20, "position": 10.0},
        ]
    )
    path = _write_csv(df)
    s = gsc_summary(path)
    assert s["clicks"] == 30
    assert s["impressions"] == 300
    assert s["ctr"] == 15.0
    assert s["pages"] == 2


# ── eeat_summary ───────────────────────────────────────────────────────────


def test_eeat_summary_missing_file():
    s = eeat_summary("/nonexistent/file.json")
    assert s["avg"] is None
    assert s["total"] == 0


def test_eeat_summary_computes_avg_and_weak():
    data = [
        {"global_score": 0.20},
        {"global_score": 0.50},
        {"global_score": 0.60},
    ]
    path = _write_json(data)
    s = eeat_summary(path)
    assert s["total"] == 3
    assert s["weak"] == 1  # only 0.20 < 0.45
    assert 43 <= s["avg"] <= 44  # (0.20+0.50+0.60)/3 * 100 ≈ 43.3


# ── cannibalization_summary ────────────────────────────────────────────────


def test_cannibalization_summary_missing_file():
    s = cannibalization_summary("/nonexistent/file.json")
    assert s["high"] is None


def test_cannibalization_summary_counts_high_severity():
    data = [
        {"severity": 0.8},
        {"severity": 0.4},
        {"severity": 0.7},
    ]
    path = _write_json(data)
    s = cannibalization_summary(path)
    assert s["high"] == 2
    assert s["total"] == 3


# ── quick_wins_list ────────────────────────────────────────────────────────


def test_quick_wins_list_missing_file():
    assert quick_wins_list("/nonexistent/file.json") == []


def test_quick_wins_list_filters_zone():
    data = [
        {"query": "q1", "zone": "quick_win", "impressions": 100, "position": 12.0},
        {"query": "q2", "zone": "long_term", "impressions": 200, "position": 25.0},
    ]
    path = _write_json(data)
    result = quick_wins_list(path)
    assert len(result) == 1
    assert result[0]["query"] == "q1"


def test_quick_wins_list_respects_n():
    data = [
        {"query": f"q{i}", "zone": "quick_win", "impressions": i * 10, "position": 12.0}
        for i in range(10)
    ]
    path = _write_json(data)
    assert len(quick_wins_list(path, n=3)) == 3


# ── top_pages_list ─────────────────────────────────────────────────────────


def test_top_pages_list_missing_file():
    assert top_pages_list("/nonexistent/file.csv") == []


def test_top_pages_list_sorted_by_clicks():
    df = pd.DataFrame(
        [
            {"url": "/a", "clicks": 5, "impressions": 50, "ctr": 0.1, "position": 3.0},
            {"url": "/b", "clicks": 50, "impressions": 500, "ctr": 0.1, "position": 2.0},
        ]
    )
    path = _write_csv(df)
    result = top_pages_list(path)
    assert result[0]["url"] == "/b"
