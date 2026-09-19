"""Tests for the expected-traffic ranking of blog ideas."""

from __future__ import annotations

import json
from pathlib import Path

from app.blog.traffic_score import load_gsc_index, rank_blog_ideas, score_idea


def _product(*keywords: dict) -> dict:
    return {"product_id": "1", "seo_keywords": list(keywords)}


def test_gsc_impressions_win_over_dataforseo_volume() -> None:
    """Real Search Console data is the trusted source when both exist."""
    idea = {"target_keyword": "harnais chien"}
    product = _product({"query": "harnais chien", "search_volume": 10})
    gsc = {"harnais chien": {"impressions": 2800, "clicks": 20, "position": 12.0}}

    score = score_idea(idea, product=product, gsc_index=gsc, window_days=28)

    assert score["traffic_source"] == "gsc"
    assert score["confidence"] == "high"
    assert score["demand_per_day"] == 100.0
    # Position 12 today, so the article aims at the realistic position 8 (CTR 3.5%).
    assert score["assumed_position"] == 8
    assert score["expected_clicks_per_day"] == 3.5


def test_a_query_already_ranking_well_keeps_its_position() -> None:
    idea = {"target_keyword": "harnais chien"}
    gsc = {"harnais chien": {"impressions": 280, "clicks": 5, "position": 3.0}}

    score = score_idea(idea, product={}, gsc_index=gsc, window_days=28)

    assert score["assumed_position"] == 3
    assert score["ctr"] == 0.11


def test_dataforseo_volume_is_used_when_gsc_is_silent() -> None:
    idea = {"target_keyword": "harnais cuir"}
    product = _product({"query": "harnais cuir", "search_volume": 3000})

    score = score_idea(idea, product=product, gsc_index={}, window_days=28)

    assert score["traffic_source"] == "dataforseo"
    assert score["confidence"] == "medium"
    assert score["demand_per_day"] == 100.0


def test_demand_bucket_is_the_last_resort_and_says_so() -> None:
    idea = {"target_keyword": "harnais haute couture"}
    product = _product({"query": "harnais haute couture", "search_volume": None, "demand_score": 50})

    score = score_idea(idea, product=product, gsc_index={}, window_days=28)

    assert score["traffic_source"] == "demand_score"
    assert score["confidence"] == "low"


def test_an_idea_without_any_demand_data_scores_zero() -> None:
    score = score_idea({"target_keyword": "inconnu"}, product={}, gsc_index={})

    assert score["expected_clicks_per_day"] == 0.0
    assert score["confidence"] == "none"


def test_ranking_puts_the_best_expected_traffic_first() -> None:
    ideas = [
        {"title": "A", "target_keyword": "petit", "product_id": "1"},
        {"title": "B", "target_keyword": "gros", "product_id": "1"},
    ]
    product = _product(
        {"query": "petit", "search_volume": 10},
        {"query": "gros", "search_volume": 5000},
    )

    ranked = rank_blog_ideas(ideas, products_by_id={"1": product}, gsc_index={})

    assert [i["title"] for i in ranked] == ["B", "A"]
    assert ranked[0]["traffic_score"]["expected_clicks_per_day"] > 0


def test_ties_keep_the_incoming_angle_order() -> None:
    """With no data anywhere, the angle priority is the sensible fallback."""
    ideas = [{"title": "seasonal", "target_keyword": ""}, {"title": "advantages", "target_keyword": ""}]

    ranked = rank_blog_ideas(ideas, products_by_id={}, gsc_index={})

    assert [i["title"] for i in ranked] == ["seasonal", "advantages"]


def test_load_gsc_index_sums_a_query_across_its_pages(tmp_path: Path) -> None:
    shop_dir = tmp_path / "shop.myshopify.com"
    shop_dir.mkdir()
    (shop_dir / "gsc_20260101T000000.json").write_text(
        json.dumps(
            {
                "days": 28,
                "rows": [
                    {"query": "harnais chien", "url": "/a", "impressions": 100, "clicks": 2, "position": 9},
                    {"query": "harnais chien", "url": "/b", "impressions": 50, "clicks": 1, "position": 14},
                ],
            }
        ),
        encoding="utf-8",
    )

    index, window_days = load_gsc_index("shop.myshopify.com", raw_dir=tmp_path)

    assert window_days == 28
    assert index["harnais chien"]["impressions"] == 150
    assert index["harnais chien"]["clicks"] == 3


def test_load_gsc_index_is_empty_when_nothing_was_imported(tmp_path: Path) -> None:
    index, window_days = load_gsc_index("shop.myshopify.com", raw_dir=tmp_path)

    assert index == {}
    assert window_days == 28
