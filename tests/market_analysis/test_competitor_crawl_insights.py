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
            "keyword_intent_type": "commercial",
            "title": "A",
            "title_length": 48,
            "meta_description": "Découvrez une fontaine chat avec livraison rapide.",
            "meta_description_length": 52,
            "page_type": "product",
            "has_faq_block": True,
            "has_product_schema": True,
            "has_faq_schema": True,
            "has_breadcrumb_schema": True,
            "has_short_answer_block": True,
            "word_count": 900,
            "internal_link_count": 14,
            "external_link_count": 2,
            "internal_link_examples": [
                {"href": "/collections/chats", "anchor": "Chats", "target_type": "collection"}
            ],
            "image_count": 4,
            "image_alt_count": 3,
            "descriptive_image_alt_count": 2,
            "has_trust_proof": True,
            "trust_proof_types": ["reviews", "guarantee"],
            "content_depth": {"materials": True, "dimensions": True, "care": True},
            "faq_question_count": 6,
            "serp_paa_questions": ["Comment choisir une fontaine chat ?"],
            "serp_feature_targets": ["paa"],
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


def _rich_features() -> list[dict]:
    base = _features()
    base[0].update({
        "title": "Fontaine à eau pour chat — silencieuse",
        "h2_texts": ["Pourquoi une fontaine ?", "Comment l'entretenir", "Pourquoi une fontaine ?"],
        "serp_featured_snippet": "Une fontaine à eau encourage le chat à boire davantage.",
    })
    base[1].update({
        "title": "Meilleure fontaine chat 2024",
        "meta_description": "Comparatif des fontaines pour chat: débit, silence, entretien.",
        "h2_texts": ["Comment l'entretenir", "Quel débit choisir"],
    })
    return base


def test_prompt_surfaces_actionable_competitor_detail() -> None:
    insights = build_competitor_crawl_insights({}, _rich_features(), {})
    prompt = format_competitor_crawl_for_prompt(insights)

    # Titles and metas surfaced for meta_title / meta_description inspiration
    assert "TITRES SEO CONCURRENTS" in prompt
    assert "Fontaine à eau pour chat — silencieuse" in prompt
    assert "META DESCRIPTIONS CONCURRENTES" in prompt
    assert "Découvrez une fontaine chat avec livraison rapide." in prompt
    # H2 subtopics surfaced for blog outline, deduplicated
    assert "SOUS-THÈMES / H2 CONCURRENTS" in prompt
    assert prompt.count("Pourquoi une fontaine ?") == 1
    assert "Comment l'entretenir" in prompt
    # Featured snippet surfaced for geo answer block
    assert "EXTRAIT REPRIS PAR GOOGLE" in prompt
    assert "encourage le chat à boire" in prompt
    # Target length guidance + guardrails preserved
    assert "vise cette longueur pour proposed_product_description" in prompt
    assert "Do not copy competitor text" in prompt


def test_prompt_caps_titles_and_h2() -> None:
    features = []
    for i in range(6):
        features.append({
            "url": f"https://x{i}.fr/p",
            "domain": f"x{i}.fr",
            "rank": i + 1,
            "keyword": "fontaine chat",
            "title": f"Titre concurrent {i}",
            "h2_texts": [f"H2 numero {j}" for j in range(i * 3, i * 3 + 3)],
            "word_count": 800,
        })
    insights = build_competitor_crawl_insights({}, features, {})
    prompt = format_competitor_crawl_for_prompt(insights)

    assert prompt.count("Titre concurrent ") <= 3
    h2_count = sum(1 for line in prompt.splitlines() if line.startswith("- H2 numero "))
    assert h2_count <= 8


def test_prompt_empty_when_no_sample() -> None:
    assert format_competitor_crawl_for_prompt({"sample_size": 0}) == ""


def test_top_urls_expose_detailed_crawl_sections() -> None:
    insights = build_competitor_crawl_insights({}, _features(), {})
    top = insights["top_urls"][0]

    assert top["page_type"] == "product"
    assert top["keyword_intent_type"] == "commercial"
    assert top["seo"]["meta_has_cta"] is True
    assert top["links"]["collection_link_count"] == 1
    assert top["images"]["descriptive_image_alt_count"] == 2
    assert top["trust"]["has_trust_proof"] is True
    assert top["product_depth"]["materials"] is True
    assert top["serp"]["paa_questions"] == ["Comment choisir une fontaine chat ?"]


def test_does_not_create_boost_when_sample_is_too_small() -> None:
    insights = build_competitor_crawl_insights({}, [_features()[0]], {})

    assert insights["sample_size"] == 1
    assert insights["merchant_gaps"] == []
    assert insights["priority_boost_total"] == 0
