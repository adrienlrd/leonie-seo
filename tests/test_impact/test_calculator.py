"""Tests for impact calculator — CTR curve, per-URL impact, aggregate ROI."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from app.impact.calculator import (
    URLImpact,
    aggregate_impact,
    compute_url_impact,
    estimate_ctr,
)
from app.impact.report import _parse_gsc_csv, build_impact_report

# ---------------------------------------------------------------------------
# estimate_ctr
# ---------------------------------------------------------------------------


def test_estimate_ctr_position_1():
    assert abs(estimate_ctr(1) - 0.316) < 1e-9


def test_estimate_ctr_position_10():
    assert abs(estimate_ctr(10) - 0.015) < 1e-9


def test_estimate_ctr_position_zero_returns_zero():
    assert estimate_ctr(0) == 0.0


def test_estimate_ctr_negative_position_returns_zero():
    assert estimate_ctr(-5) == 0.0


def test_estimate_ctr_rounds_to_nearest_position():
    # 1.4 rounds to 1, 1.6 rounds to 2
    assert estimate_ctr(1.4) == estimate_ctr(1)
    assert estimate_ctr(1.6) == estimate_ctr(2)


def test_estimate_ctr_position_beyond_10_decays():
    ctr_10 = estimate_ctr(10)
    ctr_11 = estimate_ctr(11)
    ctr_20 = estimate_ctr(20)
    assert ctr_11 < ctr_10
    assert ctr_20 < ctr_11


def test_estimate_ctr_never_below_minimum():
    assert estimate_ctr(100) >= 0.001


# ---------------------------------------------------------------------------
# compute_url_impact
# ---------------------------------------------------------------------------


def test_compute_url_impact_clicks_gained_when_position_improves():
    impact = compute_url_impact(
        "product",
        "123",
        "https://shop.com/products/a",
        "Harnais",
        changes=[{"field": "title"}],
        impressions=1000,
        position_current=5.0,
        position_improvement=2.0,
    )
    # position_before=7 (lower CTR), position_after=5 (higher CTR)
    assert impact.clicks_gained > 0
    assert impact.position_before == 7.0
    assert impact.position_after == 5.0


def test_compute_url_impact_revenue_estimate():
    impact = compute_url_impact(
        "product",
        "1",
        "https://shop.com/products/p",
        "T",
        changes=[],
        impressions=1000,
        position_current=3.0,
        position_improvement=2.0,
        conversion_rate=0.05,
        aov=100.0,
    )
    # ctr at pos 3 = 0.095, at pos 5 = 0.049
    expected_clicks_gained = 1000 * (0.095 - 0.049)
    expected_revenue = expected_clicks_gained * 0.05 * 100.0
    assert abs(impact.revenue_estimate - round(expected_revenue, 2)) < 0.01


def test_compute_url_impact_zero_impressions_gives_zero_revenue():
    impact = compute_url_impact(
        "product",
        "1",
        "https://shop.com/p",
        "T",
        changes=[],
        impressions=0,
        position_current=5.0,
    )
    assert impact.clicks_gained == 0.0
    assert impact.revenue_estimate == 0.0


def test_compute_url_impact_always_estimated():
    impact = compute_url_impact(
        "product",
        "1",
        "url",
        "T",
        changes=[],
        impressions=100,
        position_current=5.0,
    )
    assert impact.estimated is True


def test_compute_url_impact_no_improvement_when_already_position_1():
    # position_before = 1 + 2 = 3, position_after = 1
    # ctr at 3 < ctr at 1, so clicks_gained > 0 — this is correct behaviour
    impact = compute_url_impact(
        "product",
        "1",
        "url",
        "T",
        changes=[],
        impressions=500,
        position_current=1.0,
        position_improvement=2.0,
    )
    assert impact.clicks_gained > 0


# ---------------------------------------------------------------------------
# aggregate_impact
# ---------------------------------------------------------------------------


def _make_impact(**kwargs) -> URLImpact:
    defaults = dict(
        resource_type="product",
        resource_id="1",
        url="u",
        title="T",
        impressions=100,
        position_before=5.0,
        position_after=3.0,
        ctr_before=0.049,
        ctr_after=0.095,
        clicks_before=4.9,
        clicks_after=9.5,
        clicks_gained=4.6,
        revenue_estimate=4.6,
    )
    defaults.update(kwargs)
    return URLImpact(**defaults)


def test_aggregate_impact_sums_correctly():
    impacts = [
        _make_impact(resource_id="1", clicks_gained=10.0, revenue_estimate=20.0),
        _make_impact(resource_id="2", clicks_gained=5.0, revenue_estimate=10.0),
    ]
    report = aggregate_impact(impacts, conversion_rate=0.02, aov=50.0)
    assert report["summary"]["total_clicks_gained_estimate"] == 15.0
    assert report["summary"]["total_revenue_estimate"] == 30.0
    assert report["summary"]["urls_changed"] == 2


def test_aggregate_impact_sorted_by_revenue_desc():
    impacts = [
        _make_impact(resource_id="low", revenue_estimate=5.0),
        _make_impact(resource_id="high", revenue_estimate=100.0),
    ]
    report = aggregate_impact(impacts, conversion_rate=0.02, aov=50.0)
    assert report["by_url"][0]["resource_id"] == "high"
    assert report["by_url"][1]["resource_id"] == "low"


def test_aggregate_impact_empty_list():
    report = aggregate_impact([], conversion_rate=0.02, aov=50.0)
    assert report["summary"]["urls_changed"] == 0
    assert report["summary"]["total_clicks_gained_estimate"] == 0.0


def test_aggregate_impact_includes_params():
    report = aggregate_impact([], conversion_rate=0.03, aov=75.0)
    assert report["summary"]["conversion_rate"] == 0.03
    assert report["summary"]["average_order_value"] == 75.0
    assert report["summary"]["estimated"] is True


# ---------------------------------------------------------------------------
# _parse_gsc_csv
# ---------------------------------------------------------------------------


def test_parse_gsc_csv_reads_all_rows():
    csv = "url,clicks,impressions,ctr,position\nhttps://a.com/p1,10,500,0.02,5.0\nhttps://a.com/p2,5,200,0.025,3.0\n"
    gsc = _parse_gsc_csv(csv)
    assert "https://a.com/p1" in gsc
    assert gsc["https://a.com/p1"]["impressions"] == 500
    assert abs(gsc["https://a.com/p1"]["position"] - 5.0) < 1e-9


def test_parse_gsc_csv_strips_trailing_slash():
    csv = "url,clicks,impressions,ctr,position\nhttps://a.com/p1/,10,500,0.02,5.0\n"
    gsc = _parse_gsc_csv(csv)
    assert "https://a.com/p1" in gsc


def test_parse_gsc_csv_empty_returns_empty_dict():
    gsc = _parse_gsc_csv("url,clicks,impressions,ctr,position\n")
    assert gsc == {}


# ---------------------------------------------------------------------------
# build_impact_report
# ---------------------------------------------------------------------------


def _init_db(db_path: Path) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS seo_changes (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                shop          TEXT,
                applied_at    TEXT NOT NULL,
                resource_type TEXT NOT NULL,
                resource_id   TEXT NOT NULL,
                field         TEXT NOT NULL,
                old_value     TEXT,
                new_value     TEXT,
                status        TEXT NOT NULL
            )
        """)


_SNAPSHOT = {
    "shop": {"domain": "www.leoniedelacroix.com"},
    "products": [
        {"id": 123, "title": "Harnais Premium", "handle": "harnais-premium"},
    ],
    "collections": [],
}

_GSC_CSV = (
    "url,clicks,impressions,ctr,position\n"
    "https://www.leoniedelacroix.com/products/harnais-premium,18,500,0.036,6.0\n"
)


def test_build_impact_report_with_changes(tmp_path):
    db = tmp_path / "test.db"
    _init_db(db)
    with sqlite3.connect(db) as conn:
        conn.execute(
            "INSERT INTO seo_changes (shop, applied_at, resource_type, resource_id, field, old_value, new_value, status)"
            " VALUES ('287c4a-bb.myshopify.com', datetime('now'), 'product', '123', 'title', 'Old', 'New', 'applied')"
        )

    report = build_impact_report(
        "287c4a-bb.myshopify.com",
        _SNAPSHOT,
        db_path=db,
        gsc_csv_text=_GSC_CSV,
    )

    assert report["summary"]["urls_changed"] == 1
    assert report["summary"]["urls_with_gsc_data"] == 1
    assert report["summary"]["total_clicks_gained_estimate"] > 0
    assert report["by_url"][0]["title"] == "Harnais Premium"


def test_build_impact_report_isolates_by_shop(tmp_path):
    """A change logged for shop A must NOT appear in shop B's report."""
    db = tmp_path / "iso.db"
    _init_db(db)
    with sqlite3.connect(db) as conn:
        conn.execute(
            "INSERT INTO seo_changes (shop, applied_at, resource_type, resource_id, field, old_value, new_value, status)"
            " VALUES ('shop-a.myshopify.com', datetime('now'), 'product', '123', 'title', 'Old', 'New', 'applied')"
        )

    report_b = build_impact_report(
        "shop-b.myshopify.com",
        _SNAPSHOT,
        db_path=db,
        gsc_csv_text=_GSC_CSV,
    )
    assert report_b["summary"]["urls_changed"] == 0
    assert report_b["by_url"] == []

    report_a = build_impact_report(
        "shop-a.myshopify.com",
        _SNAPSHOT,
        db_path=db,
        gsc_csv_text=_GSC_CSV,
    )
    assert report_a["summary"]["urls_changed"] == 1


def test_build_impact_report_no_changes_returns_empty(tmp_path):
    db = tmp_path / "test.db"
    _init_db(db)

    report = build_impact_report("s.myshopify.com", _SNAPSHOT, db_path=db, gsc_csv_text=_GSC_CSV)
    assert report["summary"]["urls_changed"] == 0
    assert report["by_url"] == []


def test_build_impact_report_meta_fields(tmp_path):
    db = tmp_path / "test.db"
    _init_db(db)

    report = build_impact_report(
        "s.myshopify.com",
        _SNAPSHOT,
        db_path=db,
        gsc_csv_text="",
        conversion_rate=0.03,
        aov=80.0,
    )
    assert report["meta"]["shop"] == "s.myshopify.com"
    assert report["meta"]["gsc_data_available"] is False
    assert report["summary"]["conversion_rate"] == 0.03
    assert report["summary"]["average_order_value"] == 80.0
