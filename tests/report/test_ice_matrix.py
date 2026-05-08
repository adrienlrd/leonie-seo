"""Tests for scripts.report.ice_matrix."""

import pandas as pd

from scripts.models import Issue, Severity
from scripts.report.ice_matrix import build_ice_matrix, score_issue


def _make_gsc(url: str, impressions: int, position: float) -> pd.DataFrame:
    return pd.DataFrame([{"url": url, "clicks": 5, "impressions": impressions, "ctr": 0.05, "position": position}])


# ── score_issue ───────────────────────────────────────────────────────────────


def test_score_issue_no_gsc_data():
    issue = Issue(
        resource_type="product",
        resource_id="gid://shopify/Product/1",
        resource_title="Test Produit",
        issue_type="missing_meta_title",
        severity=Severity.CRITICAL,
        detail="Meta title is missing.",
    )
    row = score_issue(issue, None, pd.DataFrame())
    assert row["ice_score"] > 0
    assert row["confidence"] == 9
    assert row["effort"] == 2
    assert row["impressions"] == 0
    assert row["position"] is None


def test_score_issue_with_high_impressions_boosts_impact():
    issue = Issue(
        resource_type="product",
        resource_id="gid://shopify/Product/1",
        resource_title="Produit A",
        issue_type="missing_meta_title",
        severity=Severity.CRITICAL,
        detail="Meta title is missing.",
    )
    gsc_low = _make_gsc("http://example.com/a", impressions=5, position=15.0)
    gsc_high = _make_gsc("http://example.com/a", impressions=200, position=15.0)

    row_low = score_issue(issue, "http://example.com/a", gsc_low)
    row_high = score_issue(issue, "http://example.com/a", gsc_high)

    assert row_high["ice_score"] > row_low["ice_score"]


def test_score_issue_position_4_10_multiplier():
    issue = Issue(
        resource_type="product",
        resource_id="gid://shopify/Product/1",
        resource_title="Produit B",
        issue_type="missing_meta_description",
        severity=Severity.HIGH,
        detail="desc missing",
    )
    gsc_top = _make_gsc("http://example.com/b", impressions=100, position=5.0)
    gsc_far = _make_gsc("http://example.com/b", impressions=100, position=50.0)

    row_top = score_issue(issue, "http://example.com/b", gsc_top)
    row_far = score_issue(issue, "http://example.com/b", gsc_far)

    assert row_top["ice_score"] > row_far["ice_score"]


# ── build_ice_matrix ──────────────────────────────────────────────────────────


def test_build_ice_matrix_sorted_descending():
    products = [
        {
            "id": "gid://shopify/Product/1",
            "title": "Produit A",
            "handle": "produit-a",
            "seo": {"title": None, "description": None},
            "images": {"edges": []},
            "collections": {"edges": []},
        }
    ]
    matrix = build_ice_matrix(products, [], pd.DataFrame())
    scores = [r["ice_score"] for r in matrix]
    assert scores == sorted(scores, reverse=True)


def test_build_ice_matrix_empty_snapshot():
    matrix = build_ice_matrix([], [], pd.DataFrame())
    assert matrix == []


def test_build_ice_matrix_url_joined_from_handle():
    products = [
        {
            "id": "gid://shopify/Product/99",
            "title": "Le Pardessus",
            "handle": "le-pardessus",
            "seo": {"title": None, "description": None},
            "images": {"edges": []},
            "collections": {"edges": []},
        }
    ]
    gsc = _make_gsc(
        "https://www.leoniedelacroix.com/products/le-pardessus",
        impressions=150,
        position=6.0,
    )
    matrix = build_ice_matrix(products, [], gsc)
    top = matrix[0]
    assert top["impressions"] == 150
    assert top["url"] == "https://www.leoniedelacroix.com/products/le-pardessus"
