"""Tests for product-market signals feeding business profile analysis."""

from __future__ import annotations

import json
from types import SimpleNamespace

from app.business_profile import analyzer


def _profile_payload() -> dict:
    return {
        "niche_summary": "Accessoires premium pour chats.",
        "brand_name": "Léonie",
        "brand_voice": "Expert et rassurant.",
        "target_personas": [
            {
                "name": "Propriétaire exigeant",
                "description": "Cherche des produits fiables.",
                "main_need": "Faire le bon choix",
                "buying_trigger": "Comparer avant achat",
            }
        ],
        "content_style": {
            "tone": "expert",
            "typical_article_length": "1200 mots",
            "h2_structure": ["Choisir", "Entretenir"],
            "vocabulary_to_use": ["hydratation"],
            "vocabulary_to_avoid": ["miracle"],
            "hook_patterns": ["Comment choisir"],
        },
        "key_themes": ["hydratation féline"],
        "seasonal_patterns": [{"period": "été", "theme": "hydratation", "intensity": "high"}],
        "competitor_domains": ["serp.example"],
        "competitor_insights": ["Les concurrents parlent de silence."],
        "content_gaps": ["Guide comparatif fontaines"],
        "internal_link_priorities": ["fontaine-chat"],
    }


def test_business_profile_prompt_uses_latest_product_analysis_signals(monkeypatch):
    market_result = {
        "competitor_signals": [{"domain": "market.example"}],
        "products": [
            {
                "product_title": "Fontaine à chat",
                "product_handle": "fontaine-chat",
                "opportunity_score": 82,
                "seo_keywords": [
                    {"query": "fontaine chat silencieuse", "target_role": "primary"},
                    {"query": "nettoyer fontaine chat", "target_role": "secondary"},
                ],
                "geo_questions": [{"question": "Comment nettoyer une fontaine à chat ?"}],
                "content_test_pack": {
                    "facts_missing": ["matériau exact"],
                    "content_quality": {"issues": ["missing_recommended_faq"]},
                },
            }
        ],
    }

    captured: dict[str, str] = {}

    class Router:
        def complete(self, prompt, **kwargs):  # noqa: ANN001, ARG002
            captured["prompt"] = prompt
            return SimpleNamespace(text=json.dumps(_profile_payload()))

    monkeypatch.setattr(
        analyzer,
        "_fetch_serp_data",
        lambda seeds: {"competitor_domains": [], "paa_questions": [], "blog_results": []},
    )
    monkeypatch.setattr("app.market_analysis.jobs.load_latest_result", lambda shop: market_result)
    monkeypatch.setattr("app.llm.get_router", lambda shop: Router())

    profile = analyzer.analyze_business_profile(
        shop="shop.myshopify.com",
        snapshot={"products": [{"title": "Fontaine", "tags": ["chat"]}]},
        gsc_query_rows=[],
    )

    prompt = captured["prompt"]
    assert "Signaux observés dans l'analyse produits précédente" in prompt
    assert "fontaine chat silencieuse" in prompt
    assert "Comment nettoyer une fontaine à chat ?" in prompt
    assert "matériau exact" in prompt
    assert "market_analysis_product_signals" in profile["sources_used"]
    assert "market_analysis_competitors" in profile["sources_used"]
    assert profile["competitor_domains"] == ["serp.example"]
