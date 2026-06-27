"""Deleted blog articles must drop off the analysis overview."""

from __future__ import annotations

from unittest.mock import patch

from app.geo.analysis_overview import build_analysis_overview


def _blog_event(resource_id: str) -> dict:
    return {
        "id": 1,
        "resource_id": resource_id,
        "resource_type": "blog_post",
        "resource_title": "Mon article",
        "action_type": "blog_publish",
        "applied_at": "2026-06-01T10:00:00+00:00",
        "before_snapshot": {"path": "/blogs/blog/mon-article"},
        "after_snapshot": {"field": "blog_post", "value": "Mon article"},
        "metrics_before": {},
        "metrics_after": {},
    }


def _patches(events: list[dict], drafts: list[dict]):
    return (
        patch("app.geo.analysis_overview.list_geo_events", side_effect=[
            {"events": list(events)}, {"events": []},
        ]),
        patch("app.geo.analysis_overview._find_gsc_file", return_value=None),
        patch("app.blog.store.list_drafts", return_value=drafts),
    )


def test_deleted_blog_is_hidden() -> None:
    p1, p2, p3 = _patches([_blog_event("gid://shopify/Article/1")], drafts=[])
    with p1, p2, p3:
        result = build_analysis_overview("shop.myshopify.com")
    assert result["products"] == []
    assert result["summary"]["total_products"] == 0


def test_existing_blog_is_kept() -> None:
    drafts = [{"id": "d1", "shopify_article_id": "gid://shopify/Article/1"}]
    p1, p2, p3 = _patches([_blog_event("gid://shopify/Article/1")], drafts=drafts)
    with p1, p2, p3:
        result = build_analysis_overview("shop.myshopify.com")
    assert len(result["products"]) == 1
    assert result["products"][0]["resource_id"] == "gid://shopify/Article/1"
