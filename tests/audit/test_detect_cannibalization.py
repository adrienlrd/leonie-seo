"""Tests for scripts.audit.detect_cannibalization."""

import tempfile

import pandas as pd

from scripts.audit.detect_cannibalization import (
    _recommendation,
    detect_cannibal_pairs,
    load_gsc_query_page,
    render_markdown,
)


def _make_df(rows: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(rows, columns=["query", "url", "clicks", "impressions", "ctr", "position"])


# ── load_gsc_query_page ────────────────────────────────────────────────────


def test_load_gsc_query_page_returns_empty_when_missing():
    df = load_gsc_query_page("/nonexistent/path.csv")
    assert df.empty
    assert list(df.columns) == ["query", "url", "clicks", "impressions", "ctr", "position"]


def test_load_gsc_query_page_reads_csv():
    with tempfile.NamedTemporaryFile(suffix=".csv", mode="w", delete=False) as f:
        f.write("query,url,clicks,impressions,ctr,position\n")
        f.write("manteau chien,https://example.com/products/manteau,5,100,0.05,3.2\n")
        path = f.name
    df = load_gsc_query_page(path)
    assert len(df) == 1
    assert df.iloc[0]["query"] == "manteau chien"


# ── detect_cannibal_pairs ──────────────────────────────────────────────────


def test_detect_cannibal_pairs_empty_df_returns_empty():
    df = _make_df([])
    assert detect_cannibal_pairs(df) == []


def test_detect_cannibal_pairs_single_page_per_query_returns_empty():
    df = _make_df([
        {"query": "manteau chien", "url": "https://ex.com/products/a", "clicks": 1,
         "impressions": 50, "ctr": 0.02, "position": 5.0},
    ])
    assert detect_cannibal_pairs(df) == []


def test_detect_cannibal_pairs_below_min_impressions_excluded():
    df = _make_df([
        {"query": "q", "url": "https://ex.com/products/a", "clicks": 0,
         "impressions": 3, "ctr": 0.0, "position": 5.0},
        {"query": "q", "url": "https://ex.com/products/b", "clicks": 0,
         "impressions": 4, "ctr": 0.0, "position": 8.0},
    ])
    assert detect_cannibal_pairs(df, min_impressions=10) == []


def test_detect_cannibal_pairs_detects_two_competing_pages():
    df = _make_df([
        {"query": "fontaine chat", "url": "https://ex.com/products/fontaine", "clicks": 5,
         "impressions": 80, "ctr": 0.06, "position": 4.0},
        {"query": "fontaine chat", "url": "https://ex.com/collections/fontaines", "clicks": 2,
         "impressions": 40, "ctr": 0.05, "position": 7.0},
    ])
    results = detect_cannibal_pairs(df)
    assert len(results) == 1
    r = results[0]
    assert r["query"] == "fontaine chat"
    assert r["primary_url"] == "https://ex.com/products/fontaine"
    assert r["cannibal_url"] == "https://ex.com/collections/fontaines"
    assert r["primary_position"] == 4.0
    assert r["cannibal_position"] == 7.0


def test_detect_cannibal_pairs_primary_is_best_position():
    df = _make_df([
        {"query": "q", "url": "https://ex.com/a", "clicks": 1,
         "impressions": 30, "ctr": 0.03, "position": 12.0},
        {"query": "q", "url": "https://ex.com/b", "clicks": 3,
         "impressions": 30, "ctr": 0.10, "position": 3.0},
    ])
    results = detect_cannibal_pairs(df)
    assert results[0]["primary_url"] == "https://ex.com/b"
    assert results[0]["cannibal_url"] == "https://ex.com/a"


def test_detect_cannibal_pairs_severity_is_float_between_0_and_1():
    df = _make_df([
        {"query": "q", "url": "https://ex.com/products/a", "clicks": 2,
         "impressions": 200, "ctr": 0.01, "position": 5.0},
        {"query": "q", "url": "https://ex.com/products/b", "clicks": 1,
         "impressions": 100, "ctr": 0.01, "position": 8.0},
    ])
    results = detect_cannibal_pairs(df)
    s = results[0]["severity"]
    assert isinstance(s, float)
    assert 0.0 <= s <= 1.0


def test_detect_cannibal_pairs_sorted_by_severity_descending():
    df = _make_df([
        # High impressions, close positions → high severity
        {"query": "q1", "url": "https://ex.com/products/a", "clicks": 5,
         "impressions": 400, "ctr": 0.01, "position": 4.0},
        {"query": "q1", "url": "https://ex.com/products/b", "clicks": 3,
         "impressions": 400, "ctr": 0.01, "position": 5.0},
        # Low impressions, far positions → low severity
        {"query": "q2", "url": "https://ex.com/products/c", "clicks": 0,
         "impressions": 15, "ctr": 0.00, "position": 2.0},
        {"query": "q2", "url": "https://ex.com/collections/d", "clicks": 0,
         "impressions": 12, "ctr": 0.00, "position": 25.0},
    ])
    results = detect_cannibal_pairs(df)
    assert results[0]["query"] == "q1"
    assert results[1]["query"] == "q2"
    assert results[0]["severity"] >= results[1]["severity"]


def test_detect_cannibal_pairs_pages_count_field():
    df = _make_df([
        {"query": "q", "url": "https://ex.com/a", "clicks": 1,
         "impressions": 20, "ctr": 0.05, "position": 3.0},
        {"query": "q", "url": "https://ex.com/b", "clicks": 1,
         "impressions": 20, "ctr": 0.05, "position": 6.0},
        {"query": "q", "url": "https://ex.com/c", "clicks": 1,
         "impressions": 20, "ctr": 0.05, "position": 9.0},
    ])
    results = detect_cannibal_pairs(df)
    assert results[0]["pages_count"] == 3


# ── _recommendation ────────────────────────────────────────────────────────


def test_recommendation_blog_vs_product():
    rec = _recommendation({
        "primary_type": "product",
        "cannibal_type": "blog",
        "primary_url": "https://ex.com/products/x",
        "position_gap": 10,
    })
    assert "canonical" in rec.lower()


def test_recommendation_collection_vs_product():
    rec = _recommendation({
        "primary_type": "product",
        "cannibal_type": "collection",
        "primary_url": "https://ex.com/products/x",
        "position_gap": 5,
    })
    assert "collection" in rec.lower() or "canonical" in rec.lower()


def test_recommendation_close_positions():
    rec = _recommendation({
        "primary_type": "product",
        "cannibal_type": "product",
        "primary_url": "https://ex.com/products/x",
        "position_gap": 2,
    })
    assert "fusion" in rec.lower() or "canonical" in rec.lower()


# ── render_markdown ────────────────────────────────────────────────────────


def test_render_markdown_has_date():
    md = render_markdown([], "2026-05-10")
    assert "2026-05-10" in md


def test_render_markdown_empty_results():
    md = render_markdown([], "2026-05-10")
    assert "Aucune cannibalisation" in md


def test_render_markdown_shows_query():
    results = [
        {
            "query": "fontaine pour chat",
            "pages_count": 2,
            "total_impressions": 150,
            "primary_url": "https://ex.com/products/fontaine",
            "primary_position": 4.0,
            "primary_type": "product",
            "cannibal_url": "https://ex.com/collections/fontaines",
            "cannibal_position": 9.0,
            "cannibal_type": "collection",
            "position_gap": 5.0,
            "severity": 0.55,
        }
    ]
    md = render_markdown(results, "2026-05-10")
    assert "fontaine pour chat" in md
    assert "JSON-LD" not in md
