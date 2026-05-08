"""Tests for scripts.audit.analyze_longtail."""

import pandas as pd

from scripts.audit.analyze_longtail import (
    _site_tokens,
    _tokenize,
    build_gap_report,
    classify_coverage,
    match_keyword_to_gsc,
    match_keyword_to_site,
)

_PRODUCTS = [
    {"title": "Le Pardessus Pour Chien", "handle": "le-pardessus-pour-chien"},
    {"title": "La Fontaine Smart", "handle": "fontaine-smart-cordless"},
]
_COLLECTIONS = [
    {"title": "Chien", "handle": "chien"},
    {"title": "Chat", "handle": "chat"},
]

_GSC_DF = pd.DataFrame(
    [
        {
            "url": "https://www.leoniedelacroix.com/products/le-pardessus-pour-chien",
            "clicks": 5,
            "impressions": 120,
            "ctr": 0.04,
            "position": 8.0,
        },
        {
            "url": "https://www.leoniedelacroix.com/collections/chien",
            "clicks": 2,
            "impressions": 40,
            "ctr": 0.05,
            "position": 5.0,
        },
        {
            "url": "https://www.leoniedelacroix.com/products/fontaine-smart-cordless",
            "clicks": 1,
            "impressions": 80,
            "ctr": 0.012,
            "position": 15.0,
        },
    ]
)


# ── _tokenize ─────────────────────────────────────────────────────────────────


def test_tokenize_removes_stop_words():
    tokens = _tokenize("pardessus pour chien de france")
    assert "pour" not in tokens
    assert "de" not in tokens
    assert "pardessus" in tokens
    assert "chien" in tokens


def test_tokenize_handles_accents():
    tokens = _tokenize("Léonie élégant")
    assert "léonie" in tokens


# ── match_keyword_to_gsc ──────────────────────────────────────────────────────


def test_match_keyword_to_gsc_finds_product():
    matches = match_keyword_to_gsc("pardessus chien", _GSC_DF)
    assert len(matches) == 1
    assert "pardessus" in matches.iloc[0]["url"]


def test_match_keyword_to_gsc_no_match():
    matches = match_keyword_to_gsc("griffoir design chat", _GSC_DF)
    assert matches.empty


def test_match_keyword_to_gsc_empty_df():
    empty = pd.DataFrame(columns=["url", "clicks", "impressions", "ctr", "position"])
    assert match_keyword_to_gsc("pardessus chien", empty).empty


# ── match_keyword_to_site ─────────────────────────────────────────────────────


def test_match_keyword_to_site_finds_product():
    entries = _site_tokens(_PRODUCTS, _COLLECTIONS)
    matches = match_keyword_to_site("pardessus chien", entries)
    assert any("pardessus" in m["path"] for m in matches)


def test_match_keyword_to_site_finds_collection():
    entries = _site_tokens(_PRODUCTS, _COLLECTIONS)
    matches = match_keyword_to_site("collection chien accessoires", entries)
    assert any("chien" in m["path"] for m in matches)


def test_match_keyword_to_site_no_match():
    entries = _site_tokens(_PRODUCTS, _COLLECTIONS)
    matches = match_keyword_to_site("croquettes alimentation premium", entries)
    assert matches == []


# ── classify_coverage ─────────────────────────────────────────────────────────


def test_classify_coverage_ranking():
    gsc = _GSC_DF[_GSC_DF["url"].str.contains("pardessus")]
    result = classify_coverage("pardessus chien", gsc, [])
    assert result["status"] == "ranking"
    assert result["impressions"] == 120
    assert result["position"] == 8.0


def test_classify_coverage_on_site():
    result = classify_coverage(
        "griffoir chat",
        pd.DataFrame(columns=["url", "clicks", "impressions", "ctr", "position"]),
        [{"label": "Griffoir", "path": "/products/griffoir"}],
    )
    assert result["status"] == "on_site"
    assert result["site_page"] == "/products/griffoir"


def test_classify_coverage_gap():
    result = classify_coverage(
        "croquettes chien",
        pd.DataFrame(columns=["url", "clicks", "impressions", "ctr", "position"]),
        [],
    )
    assert result["status"] == "gap"
    assert result["site_page"] is None
    assert "créer" in result["recommendation"].lower()


def test_classify_coverage_quick_win_when_position_over_10():
    gsc = _GSC_DF[_GSC_DF["url"].str.contains("fontaine")]
    result = classify_coverage("fontaine chat", gsc, [])
    assert result["status"] == "ranking"
    assert "quick win" in result["recommendation"].lower()


# ── build_gap_report ──────────────────────────────────────────────────────────


def test_build_gap_report_sorted_ranking_first():
    kw = {"chien": ["pardessus chien", "griffoir chat design"]}
    report = build_gap_report(kw, _GSC_DF, _PRODUCTS, _COLLECTIONS)
    statuses = [r["status"] for r in report]
    # ranking should come before gap
    ranking_idx = next(i for i, s in enumerate(statuses) if s == "ranking")
    gap_indices = [i for i, s in enumerate(statuses) if s == "gap"]
    assert all(ranking_idx < gi for gi in gap_indices)


def test_build_gap_report_includes_category():
    kw = {"accessoires": ["pardessus chien premium"]}
    report = build_gap_report(kw, _GSC_DF, _PRODUCTS, _COLLECTIONS)
    assert all(r["category"] == "accessoires" for r in report)


def test_build_gap_report_empty_keywords():
    report = build_gap_report({}, _GSC_DF, _PRODUCTS, _COLLECTIONS)
    assert report == []
