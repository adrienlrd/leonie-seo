"""Tests for on-demand blog idea suggestions."""

from __future__ import annotations

from datetime import datetime

from app.blog.idea_generator import build_blog_idea_suggestions


def _products() -> list[dict]:
    return [
        {
            "product_id": "gid://shopify/Product/1",
            "product_title": "La Fontaine Smart",
            "product_summary": "Fontaine à eau sans fil pour chat, hydratation fraîche.",
            "seo_keywords": [{"query": "fontaine à eau pour chat"}],
            "trend_rising": ["fontaine chat silencieuse"],
        },
        {
            "product_id": "gid://shopify/Product/2",
            "product_title": "Le Pull Léonie",
            "product_summary": "Pull chaud pour chien frileux en hiver.",
            "seo_keywords": [{"query": "pull pour chien"}],
        },
    ]


def test_seasonal_idea_in_summer_targets_fountain() -> None:
    ideas = build_blog_idea_suggestions(products=_products(), now=datetime(2026, 7, 15))
    seasonal = [i for i in ideas if i["angle"] == "seasonal"]
    assert seasonal
    assert any("fontaine" in i["title"].lower() for i in seasonal)
    assert all(i["outline"] for i in seasonal)


def test_competitor_idea_skips_marketplaces() -> None:
    signals = [
        {"domain": "www.amazon.fr", "matched_keyword": "fontaine à eau pour chat"},
        {"domain": "griffedamour.com", "matched_keyword": "fontaine à eau pour chat"},
    ]
    ideas = build_blog_idea_suggestions(products=_products(), competitor_signals=signals, now=datetime(2026, 7, 1))
    competitor = [i for i in ideas if i["angle"] == "competitor"]
    titles = " ".join(i["title"] for i in competitor).lower()
    assert "griffedamour" in titles or "griffedamour".title().lower() in titles
    assert "amazon" not in titles


def test_advantage_idea_per_product() -> None:
    ideas = build_blog_idea_suggestions(products=_products(), now=datetime(2026, 3, 1))
    advantages = [i for i in ideas if i["angle"] == "advantages"]
    assert len(advantages) == 2
    assert all(i["product_id"] for i in advantages)


def test_trend_idea_from_rising_query() -> None:
    ideas = build_blog_idea_suggestions(products=_products(), now=datetime(2026, 3, 1))
    trend = [i for i in ideas if i["angle"] == "trend"]
    assert any("silencieuse" in i["target_keyword"] for i in trend)


def test_empty_without_products() -> None:
    assert build_blog_idea_suggestions(products=[]) == []
