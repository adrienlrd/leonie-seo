"""Integration tests for competitor crawl inside market analysis."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from app.market_analysis import engine
from app.market_analysis.competitor_crawl.models import (
    CompetitorCrawlResult,
    CompetitorCrawlTarget,
)

_SHOP = "merchant.myshopify.com"

_PASS1_JSON = json.dumps(
    {
        "product_summary": "Fontaine à eau pour chat.",
        "target_customer": "Propriétaires de chats.",
        "buying_intents": ["hydratation"],
        "seo_keywords": [
            {
                "query": "fontaine chat",
                "intent_type": "commercial",
                "demand_score": 80,
                "competition_score": 35,
                "product_fit_score": 95,
                "reason": "produit principal",
            },
            {
                "query": "fontaine eau chat",
                "intent_type": "commercial",
                "demand_score": 70,
                "competition_score": 40,
                "product_fit_score": 90,
                "reason": "variante produit",
            },
            {
                "query": "fontaine chat maison",
                "intent_type": "commercial",
                "demand_score": 60,
                "competition_score": 45,
                "product_fit_score": 85,
                "reason": "usage maison",
            },
        ],
        "geo_questions": [
            {
                "question": "Comment choisir ?",
                "answer_angle": "critères",
                "content_block_type": "faq",
                "confidence": "high",
            }
        ],
    }
)

_PASS2_JSON = json.dumps(
    {
        "proposed_meta_title": "Fontaine chat avec eau filtrée",
        "proposed_meta_description": "Fontaine chat pratique pour garder un point d'eau à la maison.",
        "proposed_image_alts": [],
        "proposed_product_title_if_different": "Fontaine chat",
        "proposed_product_description": "Cette fontaine chat organise un point d'eau dédié à la maison avec un usage simple et vérifiable pour le quotidien.",
        "proposed_faq": [
            {
                "q": "Comment choisir une fontaine chat ?",
                "a": "Vérifiez les faits produit confirmés.",
            }
        ],
        "proposed_geo_answer_block": "Une fontaine chat est un point d'eau dédié pour la maison.",
        "proposed_geo_definition_block": "Une fontaine chat est un accessoire d'hydratation pour la maison.",
        "proposed_geo_quick_facts": ["Point d'eau dédié", "Usage maison", "Faits à confirmer"],
        "proposed_geo_comparison_table": [],
        "proposed_blog_title": "",
        "proposed_blog_outline": [],
        "proposed_blog_intro": "",
        "proposed_blog_ideas": [],
        "recommended_content_actions": ["Ajouter une FAQ"],
        "facts_used": ["description"],
        "facts_missing": [],
        "claims_used": [{"claim": "Point d'eau dédié", "fact_keys": ["description"]}],
        "confidence": "high",
    }
)


class _FakeDataForSEO:
    available = True

    def enrich(self, signals, *, shop):  # noqa: ARG002
        for signal in signals:
            signal["source"] = "dataforseo"
            signal["search_volume"] = 1200
            signal["difficulty_score"] = 35
        return signals

    def fetch_keyword_ideas(self, seeds, *, limit=15):  # noqa: ARG002
        return []

    def fetch_serp_intelligence(self, keywords):
        return {
            keywords[0].lower(): {
                "paa": ["Comment choisir une fontaine chat ?"],
                "top_competitors": [
                    {
                        "domain": "competitor-a.fr",
                        "url": "https://competitor-a.fr/products/fontaine",
                        "title": "Fontaine A",
                        "rank": 1,
                    },
                    {
                        "domain": "competitor-b.fr",
                        "url": "https://competitor-b.fr/products/fontaine",
                        "title": "Fontaine B",
                        "rank": 2,
                    },
                ],
                "featured_snippet": None,
            }
        }

    def fetch_serp_competitors(self, keywords):  # noqa: ARG002
        return []

    def fetch_domain_competitors(self, domain, *, limit=20):  # noqa: ARG002
        return []


class _DisabledDataForSEO(_FakeDataForSEO):
    available = False


def _product() -> dict:
    return {
        "id": "gid://shopify/Product/1",
        "title": "Fontaine chat",
        "handle": "fontaine-chat",
        "status": "ACTIVE",
        "body_html": "<p>Fontaine chat pour organiser un point d'eau à la maison.</p>",
        "seo": {"title": "Fontaine chat", "description": "Fontaine chat maison."},
        "variants": [{"price": "29.90", "inventory_quantity": 10}],
    }


def _router() -> MagicMock:
    from app.llm.provider import CompletionResult  # noqa: PLC0415

    router = MagicMock()
    router.complete.side_effect = [
        CompletionResult(text=_PASS1_JSON, provider="openai", model="gpt-4o-mini"),
        CompletionResult(text=_PASS2_JSON, provider="openai", model="gpt-4o-mini"),
    ]
    return router


def _run(router: MagicMock, *, dataforseo, fetch_side_effect=None) -> dict:
    budget = {
        "over_budget": False,
        "budget_usd": 20.0,
        "spent_usd": 0.0,
        "remaining_usd": 20.0,
        "usage_pct": 0.0,
        "alert": None,
    }
    fetch_mock = MagicMock(side_effect=fetch_side_effect) if fetch_side_effect else MagicMock()
    if not fetch_side_effect:
        fetch_mock.side_effect = lambda targets, config: _crawl_results(targets)
    with (
        patch.object(engine, "get_router", return_value=router),
        patch.object(engine, "check_budget", return_value=budget),
        patch.object(engine, "_fetch_trends_once", return_value=[]),
        patch.object(engine, "fetch_suggestions_bulk", return_value=[]),
        patch.object(engine, "DataForSEOProvider", return_value=dataforseo),
        patch.object(engine, "fetch_competitor_targets", fetch_mock),
        patch.object(engine, "record_competitor_crawl_run", return_value=None),
    ):
        result = engine.run_market_analysis([_product()], _SHOP, {}, [])
    result["_fetch_mock"] = fetch_mock
    return result


def _crawl_results(targets: list[CompetitorCrawlTarget]) -> list[CompetitorCrawlResult]:
    results: list[CompetitorCrawlResult] = []
    for target in targets:
        results.append(
            CompetitorCrawlResult(
                target=target,
                allowed_by_robots=True,
                status_code=200,
                final_url=target.url,
                features={
                    "url": target.url,
                    "title": target.title,
                    "has_faq_block": True,
                    "has_product_schema": True,
                    "has_faq_schema": target.rank == 1,
                    "has_breadcrumb_schema": True,
                    "has_short_answer_block": True,
                    "word_count": 900 if target.rank == 1 else 800,
                    "internal_link_count": 14 if target.rank == 1 else 10,
                    "faq_question_count": 6 if target.rank == 1 else 4,
                },
                html_hash=f"hash-{target.rank}",
            )
        )
    return results


def test_does_not_crawl_when_env_disabled(monkeypatch) -> None:
    monkeypatch.setenv("COMPETITOR_CRAWL_ENABLED", "false")
    router = _router()

    result = _run(router, dataforseo=_FakeDataForSEO())

    assert result["_fetch_mock"].call_count == 0
    assert "competitor_crawl" not in result["sources_used"]
    assert result["products"][0]["competitor_crawl_insights"]["enabled"] is False


def test_adds_insights_when_env_enabled_and_fetcher_returns_features(monkeypatch) -> None:
    monkeypatch.setenv("COMPETITOR_CRAWL_ENABLED", "true")
    monkeypatch.setenv("COMPETITOR_CRAWL_THROTTLE_SECONDS", "0")
    router = _router()

    result = _run(router, dataforseo=_FakeDataForSEO())

    product = result["products"][0]
    assert result["_fetch_mock"].call_count == 1
    assert "competitor_crawl" in result["sources_used"]
    assert product["competitor_crawl_insights"]["sample_size"] == 2
    assert product["competitor_pattern_boost"] > 0
    assert product["competitor_pattern_gaps"]


def test_continues_analysis_when_fetcher_fails(monkeypatch) -> None:
    monkeypatch.setenv("COMPETITOR_CRAWL_ENABLED", "true")
    router = _router()

    result = _run(
        router,
        dataforseo=_FakeDataForSEO(),
        fetch_side_effect=RuntimeError("network unavailable"),
    )

    assert result["products"][0]["content_test_pack"]["proposed_meta_title"]
    assert "competitor_crawl" not in result["sources_used"]


def test_continues_analysis_when_robots_blocks_all_targets(monkeypatch) -> None:
    monkeypatch.setenv("COMPETITOR_CRAWL_ENABLED", "true")
    router = _router()

    def blocked(targets, config):  # noqa: ARG001
        return [
            CompetitorCrawlResult(
                target=target,
                allowed_by_robots=False,
                error="blocked_by_robots",
            )
            for target in targets
        ]

    result = _run(router, dataforseo=_FakeDataForSEO(), fetch_side_effect=blocked)

    assert result["products"][0]["content_test_pack"]["proposed_meta_title"]
    assert result["products"][0]["competitor_crawl_insights"]["sample_size"] == 0
    assert "competitor_crawl" not in result["sources_used"]


def test_pass2_receives_competitor_crawl_summary_when_insights_exist(monkeypatch) -> None:
    monkeypatch.setenv("COMPETITOR_CRAWL_ENABLED", "true")
    router = _router()

    _run(router, dataforseo=_FakeDataForSEO())

    pass2_prompt = router.complete.call_args_list[1].args[0]
    assert "COMPETITOR CRAWL INSIGHTS" in pass2_prompt
    assert "Do not copy competitor text" in pass2_prompt
    assert "Do not infer unverified product facts" in pass2_prompt
