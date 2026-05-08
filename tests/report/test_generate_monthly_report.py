"""Tests for scripts.report.generate_monthly_report."""

import pandas as pd

from scripts.report.generate_monthly_report import (
    compute_kpis,
    load_json,
    quick_wins,
    render_html,
    top_pages,
    top_queries_from_opportunities,
)


def _gsc_df(rows: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(rows, columns=["url", "clicks", "impressions", "ctr", "position"])


# ── compute_kpis ───────────────────────────────────────────────────────────


def test_compute_kpis_empty_df():
    kpis = compute_kpis(_gsc_df([]))
    assert kpis["clicks"] == 0
    assert kpis["impressions"] == 0


def test_compute_kpis_sums_clicks():
    df = _gsc_df(
        [
            {"url": "a", "clicks": 10, "impressions": 100, "ctr": 0.10, "position": 5.0},
            {"url": "b", "clicks": 20, "impressions": 200, "ctr": 0.10, "position": 8.0},
        ]
    )
    kpis = compute_kpis(df)
    assert kpis["clicks"] == 30
    assert kpis["impressions"] == 300


def test_compute_kpis_ctr_as_percentage():
    df = _gsc_df(
        [
            {"url": "a", "clicks": 5, "impressions": 100, "ctr": 0.05, "position": 5.0},
        ]
    )
    kpis = compute_kpis(df)
    assert kpis["ctr"] == 5.0


def test_compute_kpis_pages_count():
    df = _gsc_df(
        [
            {"url": "a", "clicks": 1, "impressions": 10, "ctr": 0.1, "position": 3.0},
            {"url": "b", "clicks": 2, "impressions": 20, "ctr": 0.1, "position": 4.0},
        ]
    )
    assert compute_kpis(df)["pages"] == 2


# ── top_pages ──────────────────────────────────────────────────────────────


def test_top_pages_empty():
    assert top_pages(_gsc_df([])) == []


def test_top_pages_returns_n_rows():
    rows = [
        {"url": f"/{i}", "clicks": i, "impressions": i * 10, "ctr": 0.05, "position": 5.0}
        for i in range(20)
    ]
    result = top_pages(_gsc_df(rows), n=5)
    assert len(result) == 5


def test_top_pages_sorted_by_clicks():
    df = _gsc_df(
        [
            {"url": "/a", "clicks": 5, "impressions": 50, "ctr": 0.1, "position": 3.0},
            {"url": "/b", "clicks": 50, "impressions": 500, "ctr": 0.1, "position": 2.0},
        ]
    )
    result = top_pages(df)
    assert result[0]["url"] == "/b"


# ── quick_wins ─────────────────────────────────────────────────────────────


def test_quick_wins_filters_zone():
    opps = [
        {"query": "q1", "zone": "quick_win", "impressions": 100, "position": 12.0},
        {"query": "q2", "zone": "long_term", "impressions": 200, "position": 25.0},
    ]
    result = quick_wins(opps)
    assert len(result) == 1
    assert result[0]["query"] == "q1"


def test_quick_wins_respects_n_limit():
    opps = [
        {"query": f"q{i}", "zone": "quick_win", "impressions": i * 10, "position": 12.0}
        for i in range(10)
    ]
    assert len(quick_wins(opps, n=3)) == 3


# ── top_queries_from_opportunities ────────────────────────────────────────


def test_top_queries_sorted_by_impressions():
    opps = [
        {"query": "rare", "impressions": 5, "position": 15.0, "zone": "long_term"},
        {"query": "popular", "impressions": 500, "position": 12.0, "zone": "quick_win"},
    ]
    result = top_queries_from_opportunities(opps)
    assert result[0]["query"] == "popular"


# ── render_html ────────────────────────────────────────────────────────────


def test_render_html_contains_date():
    kpis = {"clicks": 0, "impressions": 0, "ctr": 0.0, "position": 0.0, "pages": 0}
    html = render_html(kpis, [], [], [], [], [], "2026-05-08")
    assert "2026-05-08" in html


def test_render_html_is_html_document():
    html = render_html(
        {"clicks": 0, "impressions": 0, "ctr": 0.0, "position": 0.0, "pages": 0},
        [],
        [],
        [],
        [],
        [],
        "2026-05-08",
    )
    assert "<!DOCTYPE html>" in html
    assert "<html" in html
    assert "</html>" in html


def test_render_html_contains_kpi_section():
    kpis = {"clicks": 1234, "impressions": 50000, "ctr": 2.5, "position": 18.3, "pages": 20}
    html = render_html(kpis, [], [], [], [], [], "2026-05-08")
    assert "1,234" in html or "1234" in html
    assert "50,000" in html or "50000" in html


def test_render_html_no_gsc_data_shows_fallback():
    html = render_html(
        {"clicks": 0, "impressions": 0, "ctr": 0.0, "position": 0.0, "pages": 0},
        [],
        [],
        [],
        [],
        [],
        "2026-05-08",
    )
    assert "non disponibles" in html or "Aucun" in html or "0" in html


# ── load_json ──────────────────────────────────────────────────────────────


def test_load_json_returns_empty_list_when_missing():
    result = load_json("/nonexistent/file.json")
    assert result == []
