"""Tests for scripts.audit.detect_gsc_opportunities."""

import pandas as pd

from scripts.audit.detect_gsc_opportunities import (
    _estimated_gain,
    _page_type,
    classify_url,
    detect_opportunities,
    score_opportunity,
)

# ── _page_type ────────────────────────────────────────────────────────────────


def test_page_type_product():
    assert _page_type("https://www.leoniedelacroix.com/products/labreuvoir") == "product"


def test_page_type_collection():
    assert _page_type("https://www.leoniedelacroix.com/collections/chien") == "collection"


def test_page_type_homepage():
    assert _page_type("https://www.leoniedelacroix.com/") == "homepage"


# ── classify_url ──────────────────────────────────────────────────────────────


def test_classify_url_quick_win():
    zone = classify_url("https://example.com/products/x", 15.0, 100, 0.02)
    assert zone == "quick_win"


def test_classify_url_low_ctr():
    zone = classify_url("https://example.com/products/x", 6.0, 100, 0.02)
    assert zone == "low_ctr"


def test_classify_url_long_term():
    zone = classify_url("https://example.com/products/x", 30.0, 80, 0.01)
    assert zone == "long_term"


def test_classify_url_none_below_min_impressions():
    zone = classify_url("https://example.com/products/x", 15.0, 5, 0.02, min_impressions=10)
    assert zone is None


def test_classify_url_none_good_ctr_page1():
    # pos 6, CTR 8% — already performing well, not a low_ctr opportunity
    zone = classify_url("https://example.com/products/x", 6.0, 100, 0.08)
    assert zone is None


def test_classify_url_none_outside_all_zones():
    # pos 51, high impressions — beyond long_term range
    zone = classify_url("https://example.com/products/x", 55.0, 200, 0.01)
    assert zone is None


# ── score_opportunity ─────────────────────────────────────────────────────────


def test_score_opportunity_higher_impressions_higher_score():
    assert score_opportunity(200, 15.0) > score_opportunity(100, 15.0)


def test_score_opportunity_closer_to_page1_higher_score():
    assert score_opportunity(100, 11.0) > score_opportunity(100, 20.0)


def test_score_opportunity_zero_position():
    assert score_opportunity(100, 0) == 0.0


# ── _estimated_gain ───────────────────────────────────────────────────────────


def test_estimated_gain_positive_when_target_better():
    gain = _estimated_gain(impressions=500, current_ctr=0.01, target_pos=5)
    assert gain > 0


def test_estimated_gain_zero_when_already_at_target_ctr():
    # ctr already at 0.28 (pos 1 benchmark), target pos 1 → no gain
    gain = _estimated_gain(impressions=100, current_ctr=0.28, target_pos=1)
    assert gain == 0


# ── detect_opportunities ──────────────────────────────────────────────────────


def _make_df(rows: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(rows, columns=["url", "clicks", "impressions", "ctr", "position"])


def test_detect_opportunities_returns_quick_wins():
    df = _make_df([
        {"url": "https://x.com/products/a", "clicks": 2, "impressions": 150, "ctr": 0.013, "position": 13.5},
        {"url": "https://x.com/products/b", "clicks": 1, "impressions": 20, "ctr": 0.05, "position": 4.0},
    ])
    opps = detect_opportunities(df)
    zones = {o["zone"] for o in opps}
    assert "quick_win" in zones


def test_detect_opportunities_sorted_by_score_desc():
    df = _make_df([
        {"url": "https://x.com/products/a", "clicks": 2, "impressions": 50, "ctr": 0.04, "position": 12.0},
        {"url": "https://x.com/products/b", "clicks": 5, "impressions": 300, "ctr": 0.017, "position": 11.0},
    ])
    opps = detect_opportunities(df)
    scores = [o["opportunity_score"] for o in opps]
    assert scores == sorted(scores, reverse=True)


def test_detect_opportunities_filters_min_impressions():
    df = _make_df([
        {"url": "https://x.com/products/low", "clicks": 0, "impressions": 5, "ctr": 0.0, "position": 14.0},
        {"url": "https://x.com/products/ok", "clicks": 2, "impressions": 50, "ctr": 0.04, "position": 12.0},
    ])
    opps = detect_opportunities(df, min_impressions=10)
    urls = [o["url"] for o in opps]
    assert "https://x.com/products/low" not in urls
    assert "https://x.com/products/ok" in urls


def test_detect_opportunities_respects_top_limit():
    rows = [
        {"url": f"https://x.com/products/{i}", "clicks": 1, "impressions": 100, "ctr": 0.01, "position": 12.0}
        for i in range(10)
    ]
    df = _make_df(rows)
    opps = detect_opportunities(df, top=3)
    assert len(opps) <= 3


def test_detect_opportunities_empty_df():
    df = pd.DataFrame(columns=["url", "clicks", "impressions", "ctr", "position"])
    opps = detect_opportunities(df)
    assert opps == []


def test_detect_opportunities_includes_gain_and_action():
    df = _make_df([
        {"url": "https://x.com/products/a", "clicks": 2, "impressions": 100, "ctr": 0.02, "position": 14.0},
    ])
    opps = detect_opportunities(df)
    assert len(opps) == 1
    assert opps[0]["estimated_gain_clicks"] >= 0
    assert isinstance(opps[0]["action"], str)
    assert len(opps[0]["action"]) > 0
