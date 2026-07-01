"""Product image + SEO meta are attached to overview entries from the snapshot."""

from __future__ import annotations

from unittest.mock import patch

from app.geo.analysis_overview import build_analysis_overview


def _product_event(resource_id: str) -> dict:
    return {
        "id": 1,
        "resource_id": resource_id,
        "resource_type": "product",
        "resource_title": "Harnais",
        "action_type": "meta_title",
        "applied_at": "2026-06-01T10:00:00+00:00",
        "before_snapshot": {"path": "/products/harnais", "content": {}},
        "after_snapshot": {"field": "meta_title", "value": "Nouveau titre"},
        "metrics_before": {},
        "metrics_after": {},
    }


def _snapshot(gid: str) -> dict:
    return {
        "products": [
            {
                "id": gid,
                "seo": {"title": "Harnais chien | Léonie", "description": "Confort et sécurité."},
                "images": {"edges": [{"node": {"url": "https://cdn/harnais.jpg"}}]},
            }
        ]
    }


def test_product_entry_carries_image_and_meta() -> None:
    gid = "gid://shopify/Product/1"
    with patch(
        "app.geo.analysis_overview.list_geo_events",
        side_effect=[{"events": [_product_event(gid)]}, {"events": []}],
    ), patch("app.geo.analysis_overview._find_gsc_file", return_value=None), patch(
        "app.api.snapshot_store.load_latest_snapshot_from_db", return_value=_snapshot(gid)
    ):
        result = build_analysis_overview("shop.myshopify.com")

    entry = result["products"][0]
    assert entry["image_url"] == "https://cdn/harnais.jpg"
    assert entry["meta_title"] == "Harnais chien | Léonie"
    assert entry["meta_description"] == "Confort et sécurité."


def test_missing_snapshot_leaves_meta_null() -> None:
    gid = "gid://shopify/Product/1"
    with patch(
        "app.geo.analysis_overview.list_geo_events",
        side_effect=[{"events": [_product_event(gid)]}, {"events": []}],
    ), patch("app.geo.analysis_overview._find_gsc_file", return_value=None), patch(
        "app.api.snapshot_store.load_latest_snapshot_from_db", return_value=None
    ):
        result = build_analysis_overview("shop.myshopify.com")

    entry = result["products"][0]
    assert entry["image_url"] is None
    assert entry["meta_title"] is None
    assert entry["meta_description"] is None
