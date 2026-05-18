"""Tests for the GEO progress curve aggregator (task 120)."""

from __future__ import annotations

from datetime import UTC, datetime

from app.geo.progress_curve import build_progress_curve


def _snapshot(
    *,
    created_at: str,
    resource_id: str = "p1",
    readiness_score: int = 60,
    seo_score: int = 50,
    impressions: int = 200,
    clicks: int = 10,
    ctr: float = 0.05,
    position: float = 12.0,
    inventory_quantity: int | None = 5,
    price: str | None = "49.90",
) -> dict:
    return {
        "id": 1,
        "shop": "shop.myshopify.com",
        "created_at": created_at,
        "resource_type": "product",
        "resource_id": resource_id,
        "resource_title": "Harnais",
        "readiness_score": readiness_score,
        "seo_score": seo_score,
        "snapshot": {
            "commerce": {"inventory_quantity": inventory_quantity, "price": price},
        },
        "metrics": {
            "gsc": {
                "impressions": impressions,
                "clicks": clicks,
                "ctr": ctr,
                "position": position,
            }
        },
    }


def _event(
    *,
    created_at: str,
    estimated: float = 100.0,
    observed: float | None = None,
    status: str = "applied",
    measurement_status: str = "baseline_captured",
) -> dict:
    payload: dict = {
        "id": 7,
        "created_at": created_at,
        "resource_type": "product",
        "resource_id": "p1",
        "resource_title": "Harnais",
        "status": status,
        "measurement_status": measurement_status,
        "estimated_impact": {"revenue_estimate": estimated},
        "observed_impact": {"revenue": observed} if observed is not None else None,
    }
    return payload


def test_build_progress_curve_returns_empty_series_when_no_data() -> None:
    result = build_progress_curve(
        shop="shop.myshopify.com",
        snapshots=[],
        events=[],
        ga4_daily=None,
        gsc_available=False,
        ga4_connected=False,
        window_days=90,
        now=datetime(2026, 5, 19, tzinfo=UTC),
    )

    assert result["shop"] == "shop.myshopify.com"
    assert result["window_days"] == 90
    assert result["series"]["geo_score"] == []
    assert result["series"]["sessions"] == []
    assert result["flags"]["incomplete_tracking"] is True
    assert result["flags"]["low_volume"] is True
    assert result["totals"] == {
        "snapshots_in_window": 0,
        "events_in_window": 0,
        "total_impressions": 0,
    }


def test_build_progress_curve_orders_snapshot_scores_ascending_by_day() -> None:
    snapshots = [
        _snapshot(created_at="2026-04-05T10:00:00+00:00", readiness_score=55),
        _snapshot(created_at="2026-04-20T10:00:00+00:00", readiness_score=70),
        _snapshot(created_at="2026-05-10T10:00:00+00:00", readiness_score=82),
    ]

    result = build_progress_curve(
        shop="shop.myshopify.com",
        snapshots=snapshots,
        events=[],
        ga4_daily={},
        gsc_available=True,
        ga4_connected=True,
        window_days=90,
        now=datetime(2026, 5, 19, tzinfo=UTC),
    )

    dates = [point["date"] for point in result["series"]["geo_score"]]
    values = [point["value"] for point in result["series"]["geo_score"]]
    assert dates == ["2026-04-05", "2026-04-20", "2026-05-10"]
    assert values == [55, 70, 82]


def test_build_progress_curve_drops_snapshots_outside_window() -> None:
    snapshots = [
        _snapshot(created_at="2025-12-01T10:00:00+00:00", readiness_score=40),
        _snapshot(created_at="2026-05-10T10:00:00+00:00", readiness_score=80),
    ]

    result = build_progress_curve(
        shop="shop.myshopify.com",
        snapshots=snapshots,
        events=[],
        ga4_daily={},
        gsc_available=True,
        ga4_connected=True,
        window_days=30,
        now=datetime(2026, 5, 19, tzinfo=UTC),
    )

    assert len(result["series"]["geo_score"]) == 1
    assert result["series"]["geo_score"][0]["date"] == "2026-05-10"
    assert result["totals"]["snapshots_in_window"] == 1


def test_build_progress_curve_keeps_latest_snapshot_per_day() -> None:
    snapshots = [
        _snapshot(created_at="2026-05-10T08:00:00+00:00", readiness_score=60),
        _snapshot(created_at="2026-05-10T22:00:00+00:00", readiness_score=75),
    ]

    result = build_progress_curve(
        shop="shop.myshopify.com",
        snapshots=snapshots,
        events=[],
        ga4_daily={},
        gsc_available=True,
        ga4_connected=True,
        window_days=90,
        now=datetime(2026, 5, 19, tzinfo=UTC),
    )

    assert result["series"]["geo_score"] == [{"date": "2026-05-10", "value": 75}]


def test_build_progress_curve_emits_gsc_series_from_snapshot_metrics() -> None:
    snapshots = [
        _snapshot(
            created_at="2026-05-10T10:00:00+00:00",
            impressions=1500,
            clicks=120,
            ctr=0.08,
            position=8.5,
        ),
    ]

    result = build_progress_curve(
        shop="shop.myshopify.com",
        snapshots=snapshots,
        events=[],
        ga4_daily={},
        gsc_available=True,
        ga4_connected=True,
        window_days=90,
        now=datetime(2026, 5, 19, tzinfo=UTC),
    )

    assert result["series"]["impressions"] == [{"date": "2026-05-10", "value": 1500}]
    assert result["series"]["clicks"] == [{"date": "2026-05-10", "value": 120}]
    assert result["series"]["ctr"] == [{"date": "2026-05-10", "value": 0.08}]
    assert result["series"]["position"] == [{"date": "2026-05-10", "value": 8.5}]
    assert result["flags"]["low_volume"] is False


def test_build_progress_curve_emits_ga4_series_when_connected() -> None:
    ga4_daily = {
        "2026-05-12": {"sessions": 50, "conversions": 2, "revenue": 99.5},
        "2026-05-13": {"sessions": 70, "conversions": 3, "revenue": 150.0},
    }

    result = build_progress_curve(
        shop="shop.myshopify.com",
        snapshots=[],
        events=[],
        ga4_daily=ga4_daily,
        gsc_available=True,
        ga4_connected=True,
        window_days=30,
        now=datetime(2026, 5, 19, tzinfo=UTC),
    )

    assert result["series"]["sessions"] == [
        {"date": "2026-05-12", "value": 50},
        {"date": "2026-05-13", "value": 70},
    ]
    assert result["series"]["conversions"] == [
        {"date": "2026-05-12", "value": 2},
        {"date": "2026-05-13", "value": 3},
    ]
    assert result["series"]["revenue"] == [
        {"date": "2026-05-12", "value": 99.5},
        {"date": "2026-05-13", "value": 150.0},
    ]
    assert result["flags"]["incomplete_tracking"] is False


def test_build_progress_curve_flags_incomplete_tracking_when_ga4_missing() -> None:
    result = build_progress_curve(
        shop="shop.myshopify.com",
        snapshots=[_snapshot(created_at="2026-05-10T10:00:00+00:00", impressions=1500)],
        events=[],
        ga4_daily=None,
        gsc_available=True,
        ga4_connected=False,
        window_days=90,
        now=datetime(2026, 5, 19, tzinfo=UTC),
    )

    assert result["flags"]["incomplete_tracking"] is True
    assert result["series"]["sessions"] == []


def test_build_progress_curve_aggregates_event_impact_per_day() -> None:
    events = [
        _event(created_at="2026-05-10T08:00:00+00:00", estimated=100.0, observed=80.0),
        _event(created_at="2026-05-10T20:00:00+00:00", estimated=50.0, observed=None),
        _event(created_at="2026-05-11T10:00:00+00:00", estimated=200.0, observed=180.0),
    ]

    result = build_progress_curve(
        shop="shop.myshopify.com",
        snapshots=[],
        events=events,
        ga4_daily={},
        gsc_available=True,
        ga4_connected=True,
        window_days=90,
        now=datetime(2026, 5, 19, tzinfo=UTC),
    )

    impact = result["series"]["impact_estimated_vs_observed"]
    assert impact == [
        {"date": "2026-05-10", "estimated": 150.0, "observed": 80.0},
        {"date": "2026-05-11", "estimated": 200.0, "observed": 180.0},
    ]
    assert len(result["optimizations_in_validation"]) == 3
    assert result["optimizations_in_validation"][0]["measurement_status"] == "baseline_captured"


def test_build_progress_curve_detects_out_of_stock_and_price_changes() -> None:
    snapshots = [
        _snapshot(
            created_at="2026-04-10T10:00:00+00:00",
            resource_id="p1",
            inventory_quantity=12,
            price="49.90",
        ),
        _snapshot(
            created_at="2026-05-01T10:00:00+00:00",
            resource_id="p1",
            inventory_quantity=0,
            price="54.90",
        ),
        _snapshot(
            created_at="2026-05-05T10:00:00+00:00",
            resource_id="p2",
            inventory_quantity=5,
            price="29.90",
        ),
    ]

    result = build_progress_curve(
        shop="shop.myshopify.com",
        snapshots=snapshots,
        events=[],
        ga4_daily={},
        gsc_available=True,
        ga4_connected=True,
        window_days=90,
        now=datetime(2026, 5, 19, tzinfo=UTC),
    )

    assert result["flags"]["out_of_stock_pages"] == 1
    assert result["flags"]["price_changed_pages"] == 1
