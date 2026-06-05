"""Tests for the canonical product optimization context."""

from __future__ import annotations

from app.product_optimization.context import (
    build_product_optimization_context,
    content_action_feedback_from_context,
)


def _product() -> dict:
    return {
        "product_id": "gid://shopify/Product/1",
        "product_title": "Harnais chien",
        "product_handle": "harnais-chien",
        "product_url": "/products/harnais-chien",
        "opportunity_score": 72,
        "seo_keywords": [
            {
                "query": "harnais chien confortable",
                "target_role": "primary",
                "data_source": "gsc",
            }
        ],
        "improvement_tags": [
            {
                "label": "harnais chien confortable",
                "tag_type": "keyword",
                "status": "positive",
                "score": 90,
                "source": "market_analysis",
                "locked_by_merchant": False,
            },
            {
                "label": "collier chat",
                "tag_type": "keyword",
                "status": "negative",
                "score": 0,
                "source": "merchant",
                "locked_by_merchant": True,
            },
            {
                "label": "materials",
                "tag_type": "risk",
                "status": "negative",
                "score": 0,
                "source": "market_analysis",
                "locked_by_merchant": False,
            },
        ],
        "improvement_elements": [
            {"key": "meta_title", "label": "Meta title", "improved": True},
            {"key": "faq", "label": "FAQ", "improved": False},
        ],
        "competitor_crawl_insights": {
            "enabled": True,
            "sample_size": 3,
            "priority_boost_total": 8,
            "merchant_gaps": [
                {
                    "gap": "missing_faq_block",
                    "action_type": "faq",
                    "priority_boost": 8,
                    "reason": "Top competitors use FAQs.",
                }
            ],
            "top_urls": [
                {
                    "seo": {"title": "Harnais confortable chien", "meta_description": "Guide."},
                    "structure": {"h2_texts": ["Comment choisir un harnais ?"]},
                    "serp": {"paa_questions": ["Quel harnais pour chien sensible ?"]},
                }
            ],
        },
        "content_test_pack": {
            "merchant_questions": [
                {
                    "key": "materials",
                    "question": "Quels matériaux peut-on confirmer ?",
                    "unlocks_surfaces": ["faq", "geo_answer"],
                }
            ],
            "facts_missing": ["materials"],
            "content_quality": {"score": 70},
            "surface_plan": {"faq": {"generate": True, "reason": "primary_target_available"}},
        },
    }


def test_context_separates_tags_competitors_questions_and_generation_contract() -> None:
    context = build_product_optimization_context("shop.myshopify.com", _product())

    assert context["version"]
    assert context["keywords"]["primary"]["query"] == "harnais chien confortable"
    assert context["tags"]["guidance"]["reinforce"] == ["harnais chien confortable"]
    assert "collier chat" in context["tags"]["guidance"]["avoid"]
    assert context["tags"]["guidance"]["auto_apply_allowed_by_tags"] is False
    assert context["questions"]["pending"][0]["key"] == "materials"
    assert context["competitors"]["structural_actions"][0]["gap"] == "missing_faq_block"
    assert context["generation_contract"]["market_analysis_role"] == "diagnostic_and_brief"
    assert context["generation_contract"]["final_generation_role"] == "content_actions"


def test_content_action_feedback_renders_compact_generation_guidance() -> None:
    context = build_product_optimization_context("shop.myshopify.com", _product())

    feedback = content_action_feedback_from_context(context)

    assert "Reinforce validated tags: harnais chien confortable" in feedback
    assert "Avoid negative or retired tags: collier chat" in feedback
    assert "missing_faq_block" in feedback
    assert "pending fact keys: materials" in feedback
