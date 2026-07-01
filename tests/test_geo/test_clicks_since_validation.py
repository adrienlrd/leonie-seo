"""Clicks-since-validation: GA4 primary path, date/path filtering, GSC fallback."""

from __future__ import annotations

from unittest.mock import patch

from app.geo import clicks_since_validation as mod


def _event(rid: str, path: str, date: str) -> dict:
    return {
        "id": 1,
        "resource_id": rid,
        "resource_type": "product",
        "resource_title": "Harnais",
        "before_snapshot": {"path": path},
        "created_at": f"{date}T10:00:00+00:00",
    }


def _ledger(events: list[dict]):
    return patch.object(
        mod,
        "list_geo_events",
        side_effect=[{"events": list(events)}, {"events": []}],
    )


def _no_cache(tmp_path):
    return patch.object(mod, "_cache_path", return_value=tmp_path / "clicks.json")


def test_ga4_sums_google_and_ai_since_validation(tmp_path) -> None:
    events = [_event("gid://Product/1", "/products/harnais", "2026-06-01")]
    organic = {"/products/harnais": {"2026-05-01": 100, "2026-06-01": 5, "2026-06-03": 3}}
    ai = {"/products/harnais": {"2026-06-02": 2}}

    with _ledger(events), _no_cache(tmp_path), \
        patch.object(mod, "_build_ga4_client", return_value=object()), \
        patch.object(mod, "get_organic_by_page_daily", return_value=organic), \
        patch.object(mod, "get_ai_referrals_by_page_daily", return_value=ai):
        result = mod.compute_clicks_since_validation("shop.myshopify.com")

    entry = result["resources"]["gid://Product/1"]
    assert result["ga4_ready"] is True
    assert entry["google"] == 8  # 100 (before 06-01) excluded
    assert entry["ai"] == 2
    assert entry["total"] == 10
    assert entry["since"] == "2026-06-01"
    assert entry["source"] == "ga4"


def test_latest_validation_date_wins(tmp_path) -> None:
    events = [
        _event("gid://Product/1", "/products/harnais", "2026-06-01"),
        _event("gid://Product/1", "/products/harnais", "2026-06-10"),
    ]
    organic = {"/products/harnais": {"2026-06-05": 7, "2026-06-11": 4}}

    with _ledger(events), _no_cache(tmp_path), \
        patch.object(mod, "_build_ga4_client", return_value=object()), \
        patch.object(mod, "get_organic_by_page_daily", return_value=organic), \
        patch.object(mod, "get_ai_referrals_by_page_daily", return_value={}):
        result = mod.compute_clicks_since_validation("shop.myshopify.com")

    entry = result["resources"]["gid://Product/1"]
    assert entry["since"] == "2026-06-10"
    assert entry["google"] == 4  # 06-05 predates the latest validation


def test_path_matching_ignores_query_and_trailing_slash(tmp_path) -> None:
    events = [_event("gid://Product/1", "/products/harnais/", "2026-06-01")]
    organic = {"/products/harnais?variant=42": {"2026-06-02": 9}}

    with _ledger(events), _no_cache(tmp_path), \
        patch.object(mod, "_build_ga4_client", return_value=object()), \
        patch.object(mod, "get_organic_by_page_daily", return_value=organic), \
        patch.object(mod, "get_ai_referrals_by_page_daily", return_value={}):
        result = mod.compute_clicks_since_validation("shop.myshopify.com")

    assert result["resources"]["gid://Product/1"]["google"] == 9


def test_gsc_fallback_when_ga4_absent(tmp_path) -> None:
    events = [_event("gid://Product/1", "/products/harnais", "2026-06-01")]
    gsc_rows = {"https://shop.myshopify.com/products/harnais": {"clicks": 12}}

    with _ledger(events), _no_cache(tmp_path), \
        patch.object(mod, "_build_ga4_client", return_value=None), \
        patch.object(mod, "_gsc_clicks_by_url", return_value=gsc_rows):
        result = mod.compute_clicks_since_validation("shop.myshopify.com")

    entry = result["resources"]["gid://Product/1"]
    assert result["ga4_ready"] is False
    assert entry["google"] == 12
    assert entry["ai"] is None
    assert entry["source"] == "gsc"


def test_empty_when_no_validated_resources(tmp_path) -> None:
    with _ledger([]), _no_cache(tmp_path), \
        patch.object(mod, "_build_ga4_client", return_value=object()):
        result = mod.compute_clicks_since_validation("shop.myshopify.com")
    assert result["resources"] == {}
