"""Tests for competitor crawl insight aggregation."""

from __future__ import annotations

from app.market_analysis.competitor_crawl.insights import build_competitor_crawl_insights
from app.market_analysis.competitor_crawl.prompt import format_competitor_crawl_for_prompt


def _features() -> list[dict]:
    return [
        {
            "url": "https://a.fr/p",
            "domain": "a.fr",
            "rank": 1,
            "keyword": "fontaine chat",
            "title": "A",
            "has_faq_block": True,
            "has_product_schema": True,
            "has_faq_schema": True,
            "has_breadcrumb_schema": True,
            "has_short_answer_block": True,
            "word_count": 900,
            "internal_link_count": 14,
            "faq_question_count": 6,
        },
        {
            "url": "https://b.fr/p",
            "domain": "b.fr",
            "rank": 2,
            "keyword": "fontaine chat",
            "title": "B",
            "has_faq_block": True,
            "has_product_schema": True,
            "has_faq_schema": False,
            "has_breadcrumb_schema": True,
            "has_short_answer_block": True,
            "word_count": 800,
            "internal_link_count": 10,
            "faq_question_count": 4,
        },
        {
            "url": "https://c.fr/p",
            "domain": "c.fr",
            "rank": 3,
            "keyword": "fontaine chat",
            "title": "C",
            "has_faq_block": False,
            "has_product_schema": False,
            "has_faq_schema": False,
            "has_breadcrumb_schema": True,
            "has_short_answer_block": False,
            "word_count": 850,
            "internal_link_count": 12,
            "faq_question_count": 0,
        },
    ]


def test_calculates_dominant_patterns_when_sample_is_sufficient() -> None:
    insights = build_competitor_crawl_insights({}, _features(), {})

    patterns = insights["dominant_patterns"]
    assert patterns["has_faq_block_rate"] == 0.67
    assert patterns["has_product_schema_rate"] == 0.67
    assert patterns["has_breadcrumb_schema_rate"] == 1.0
    assert patterns["median_word_count"] == 850
    assert patterns["median_internal_links"] == 12
    assert patterns["median_faq_questions"] == 4


def test_calculates_merchant_gaps_when_merchant_lacks_dominant_patterns() -> None:
    insights = build_competitor_crawl_insights(
        {},
        _features(),
        {
            "has_faq_block": False,
            "has_product_schema": False,
            "has_breadcrumb_schema": False,
            "has_short_answer_block": False,
            "internal_link_count": 1,
            "word_count": 80,
        },
    )

    gap_keys = {gap["gap"] for gap in insights["merchant_gaps"]}
    assert "missing_faq_block" in gap_keys
    assert "missing_product_schema" in gap_keys
    assert "missing_geo_answer_block" in gap_keys
    assert insights["priority_boost_total"] <= 20


def test_produces_prompt_summary_without_competitor_text_when_insights_exist() -> None:
    insights = build_competitor_crawl_insights({}, _features(), {})
    prompt = format_competitor_crawl_for_prompt(insights)

    assert "COMPETITOR CRAWL INSIGHTS" in prompt
    assert "Do not copy competitor text" in prompt
    assert "Fontaine A" not in insights["prompt_summary"]


def test_does_not_create_boost_when_sample_is_too_small() -> None:
    insights = build_competitor_crawl_insights({}, [_features()[0]], {})

    assert insights["sample_size"] == 1
    assert insights["merchant_gaps"] == []
    assert insights["priority_boost_total"] == 0
