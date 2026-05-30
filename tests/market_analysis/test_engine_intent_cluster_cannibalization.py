"""Integration tests for Chantier B wiring inside run_market_analysis."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from app.market_analysis import engine

_SHOP = "test.myshopify.com"

_PASS2_JSON = json.dumps(
    {
        "proposed_meta_title": "Harnais chien — confort cuir",
        "proposed_meta_description": "Harnais chien réglable en cuir véritable.",
        "proposed_product_title_if_different": "Harnais chien cuir",
        "proposed_product_description": "Harnais chien en cuir, taillé pour les balades.",
        "proposed_faq": [{"q": "Comment choisir un harnais chien ?", "a": "Mesurez le tour."}],
        "proposed_geo_answer_block": "Le harnais chien permet une marche confortable.",
        "proposed_blog_title": "",
        "proposed_blog_outline": [],
        "proposed_blog_intro": "",
        "recommended_content_actions": [],
        "facts_used": ["cuir"],
        "facts_missing": [],
        "claims_used": [{"claim": "harnais en cuir", "fact_keys": ["materials"]}],
        "confidence": "high",
    }
)


def _pass1(query: str) -> str:
    return json.dumps(
        {
            "product_summary": "Harnais pour chien.",
            "target_customer": "Propriétaire de chien.",
            "buying_intents": ["balade"],
            "seo_keywords": [
                {
                    "query": query,
                    "intent_type": "commercial",
                    "demand_score": 60,
                    "competition_score": 40,
                    "product_fit_score": 90,
                    "reason": "produit principal",
                }
            ],
            "geo_questions": [],
        }
    )


class _FakeDataForSEO:
    available = True

    def enrich(self, signals, *, shop):  # noqa: ARG002
        for sig in signals:
            sig["source"] = "dataforseo"
            sig["search_volume"] = 800
            sig["difficulty_score"] = 30
            sig["difficulty_source"] = "dataforseo"
        return signals

    def fetch_serp_intelligence(self, keywords):
        return {
            kw.strip().lower(): {
                "paa": [],
                "top_competitors": [
                    {"domain": "zooplus.fr", "title": "Acheter harnais chien", "rank": 1},
                    {"domain": "amazon.fr", "title": "Harnais chien prix bas", "rank": 2},
                    {"domain": "wanimo.com", "title": "Livraison harnais chien", "rank": 3},
                ],
                "featured_snippet": None,
            }
            for kw in keywords
        }

    def fetch_serp_competitors(self, keywords):  # noqa: ARG002
        return []

    def fetch_keyword_ideas(self, seeds, *, limit=15):  # noqa: ARG002
        return []

    def fetch_domain_competitors(self, domain, *, limit=20):  # noqa: ARG002
        return []


def _product(pid: str, title: str, handle: str) -> dict:
    return {
        "id": f"gid://shopify/Product/{pid}",
        "title": title,
        "handle": handle,
        "status": "ACTIVE",
        "body_html": f"<p>{title}</p>",
        "seo": {"title": title, "description": ""},
        "variants": [{"price": "29.90", "inventory_quantity": 5}],
    }


def _router(*texts):
    from app.llm.provider import CompletionResult  # noqa: PLC0415

    router = MagicMock()
    router.complete.side_effect = [
        CompletionResult(text=t, provider="openai", model="gpt-4o-mini") for t in texts
    ]
    return router


def _run(products, router):
    budget = {
        "over_budget": False,
        "budget_usd": 20.0,
        "spent_usd": 0.0,
        "remaining_usd": 20.0,
        "usage_pct": 0.0,
        "alert": None,
    }
    with (
        patch.object(engine, "get_router", return_value=router),
        patch.object(engine, "check_budget", return_value=budget),
        patch.object(engine, "_fetch_trends_once", return_value=[]),
        patch.object(engine, "fetch_suggestions_bulk", return_value=[]),
        patch.object(engine, "DataForSEOProvider", return_value=_FakeDataForSEO()),
    ):
        return engine.run_market_analysis(products, _SHOP, {}, [])


def test_keyword_intent_is_reclassified_from_serp_features():
    products = [_product("1", "Harnais chien cuir", "harnais-chien-cuir")]
    router = _router(_pass1("harnais chien cuir"), _PASS2_JSON)
    result = _run(products, router)

    keywords = result["products"][0]["seo_keywords"]
    assert keywords, "expected at least one keyword in product result"
    primary = keywords[0]
    # E-commerce SERP domains (zooplus/amazon/wanimo) → transactional via classifier.
    assert primary["intent_type"] == "transactional"
    assert primary["intent_type_source"] == "serp_classified"


def test_keyword_clusters_appear_in_product_result():
    products = [_product("1", "Harnais chien cuir", "harnais-chien-cuir")]
    router = _router(_pass1("harnais chien cuir"), _PASS2_JSON)
    result = _run(products, router)

    clusters = result["products"][0]["keyword_clusters"]
    assert isinstance(clusters, list)
    assert clusters, "expected at least one cluster"
    assert "cluster_id" in clusters[0]
    assert "head_keyword" in clusters[0]


def test_cannibalization_alert_emitted_at_job_level_when_two_products_share_primary():
    products = [
        _product("1", "Harnais chien cuir A", "harnais-a"),
        _product("2", "Harnais chien cuir B", "harnais-b"),
    ]
    # Both Pass 1 LLM responses pick the same primary keyword.
    router = _router(
        _pass1("harnais chien"),
        _pass1("harnais chien"),
        _PASS2_JSON,
        _PASS2_JSON,
    )
    result = _run(products, router)

    alerts = result["cannibalization_alerts"]
    assert isinstance(alerts, list)
    assert len(alerts) >= 1
    alert = alerts[0]
    assert alert["cluster_head"]
    assert len(alert["product_ids"]) == 2
    assert alert["winner_suggested"] in alert["product_ids"]
