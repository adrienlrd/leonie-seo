"""Tests for the Priority Engine — build_priority_actions pipeline."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from app.priorities.engine import (
    _pre_score,
    build_priority_actions,
)


def _make_product(handle: str = "prod-1", title: str = "Product 1", status: str = "ACTIVE") -> dict:
    return {
        "id": f"gid://shopify/Product/100{handle}",
        "handle": handle,
        "title": title,
        "status": status,
        "variants": [{"price": "29.99", "inventoryQuantity": 10}],
    }


def _make_opportunity(handle: str = "prod-1", score: int = 75, confidence: str = "high") -> dict:
    return {
        "product_id": f"gid://shopify/Product/100{handle}",
        "handle": handle,
        "title": f"Product {handle}",
        "opportunity_score": score,
        "tier": "high" if score >= 70 else "medium" if score >= 40 else "low",
        "primary_reason": "Test reason",
        "signals": [
            {"type": "gsc_signal", "weight": 0.30, "value": 0.8, "evidence": {"impressions": 500, "zone": "quick_win"}},
        ],
        "matched_queries": ["query one"],
        "matched_intents": ["transactional"],
        "recommended_actions": [],
        "niche_alerts": [],
        "confidence": confidence,
    }


def _make_prio(handle: str = "prod-1", action_type: str = "improve_seo_copy") -> dict:
    return {
        "handle": handle,
        "action_type": action_type,
        "action_label": "Améliorer le contenu SEO",
        "readiness_score": 60,
        "impressions": 500,
        "revenue_estimate": 120.0,
        "clicks_gain_estimate": 10.0,
        "position": 14.0,
        "confidence": "high",
    }


# ── _pre_score ────────────────────────────────────────────────────────────────


def test_pre_score_returns_float_between_0_and_1():
    opp = _make_opportunity(score=80, confidence="high")
    prio = _make_prio(action_type="improve_seo_copy")
    risk = {"guard_status": "safe", "risk_score": 0, "reasons": []}
    score = _pre_score(opp, prio, risk, None)
    assert 0.0 <= score <= 1.0


def test_pre_score_high_risk_lowers_score():
    opp = _make_opportunity(score=80, confidence="high")
    prio = _make_prio(action_type="improve_seo_copy")
    risk_safe = {"guard_status": "safe", "risk_score": 0, "reasons": []}
    risk_high = {"guard_status": "review_required", "risk_score": 80, "reasons": ["high_impressions"]}
    score_safe = _pre_score(opp, prio, risk_safe, None)
    score_high = _pre_score(opp, prio, risk_high, None)
    assert score_safe > score_high


def test_pre_score_niche_boost_increases_score():
    opp = _make_opportunity(handle="prod-1", score=60, confidence="medium")
    prio = _make_prio(action_type="improve_seo_copy")
    risk = {"guard_status": "safe", "risk_score": 0, "reasons": []}

    niche = {
        "status": "validated_by_merchant",
        "priority_products": [{"product_id": "gid://shopify/Product/100prod-1"}],
        "shop_summary": {"primary_niche": "petfood"},
        "conversational_intents": [],
    }
    score_no_niche = _pre_score(opp, prio, risk, None)
    score_with_niche = _pre_score(opp, prio, risk, niche)
    assert score_with_niche > score_no_niche


def test_pre_score_high_effort_action_lowers_score():
    opp = _make_opportunity(score=70, confidence="high")
    prio_low = _make_prio(action_type="improve_seo_copy")
    prio_high = _make_prio(action_type="enrich_product_facts")
    risk = {"guard_status": "safe", "risk_score": 0, "reasons": []}
    score_low = _pre_score(opp, prio_low, risk, None)
    score_high_effort = _pre_score(opp, prio_high, risk, None)
    assert score_low > score_high_effort


# ── build_priority_actions ────────────────────────────────────────────────────


def _stub_find_opps(products, shop_domain, gsc_page_rows, gsc_query_rows, **kwargs):
    opps = [_make_opportunity(handle=f"prod-{i}", score=90 - i * 5) for i in range(1, 8)]
    return {
        "opportunities": opps,
        "total_products_scanned": len(opps),
        "scope": {"active": len(opps)},
        "summary": {"by_tier": {"high": 3, "medium": 4, "low": 0}, "by_intent": {}, "average_score": 70},
    }


def _stub_prio(products, shop_domain, gsc_page_rows, *, top, scope):
    rows = [_make_prio(handle=f"prod-{i}") for i in range(1, 8)]
    return {"rows": rows}


def _stub_risk_safe(product, shop_domain, gsc_page_rows):
    return {"guard_status": "safe", "risk_score": 0, "reasons": []}


def _stub_risk_protected(product, shop_domain, gsc_page_rows):
    return {"guard_status": "protected", "risk_score": 100, "reasons": ["top_revenue"]}


def _stub_scope(products, scope):
    return [p for p in products if p.get("status") == "ACTIVE"]


@pytest.fixture()
def products():
    return [_make_product(handle=f"prod-{i}", status="ACTIVE") for i in range(1, 8)]


def test_build_priority_actions_returns_at_most_3(products):
    with (
        patch("app.priorities.engine.find_opportunities_for_catalog", side_effect=_stub_find_opps),
        patch("app.priorities.engine.prioritize_catalog", side_effect=_stub_prio),
        patch("app.priorities.engine.assess_product_risk", side_effect=_stub_risk_safe),
        patch("app.priorities.engine.filter_products_by_scope", side_effect=_stub_scope),
    ):
        result = build_priority_actions(products, "shop.myshopify.com", "shop", {}, [], plan="free")
    assert len(result["actions"]) <= 3
    assert result["shop"] == "shop"
    assert "generated_at" in result


def test_build_priority_actions_plan_free_no_llm(products):
    with (
        patch("app.priorities.engine.find_opportunities_for_catalog", side_effect=_stub_find_opps),
        patch("app.priorities.engine.prioritize_catalog", side_effect=_stub_prio),
        patch("app.priorities.engine.assess_product_risk", side_effect=_stub_risk_safe),
        patch("app.priorities.engine.filter_products_by_scope", side_effect=_stub_scope),
    ):
        result = build_priority_actions(products, "shop.myshopify.com", "shop", {}, [], plan="free")
    assert result["llm_used"] is False
    assert result["fallback_reason"] == "plan_free"


def test_build_priority_actions_protected_products_excluded(products):
    with (
        patch("app.priorities.engine.find_opportunities_for_catalog", side_effect=_stub_find_opps),
        patch("app.priorities.engine.prioritize_catalog", side_effect=_stub_prio),
        patch("app.priorities.engine.assess_product_risk", side_effect=_stub_risk_protected),
        patch("app.priorities.engine.filter_products_by_scope", side_effect=_stub_scope),
    ):
        result = build_priority_actions(products, "shop.myshopify.com", "shop", {}, [], plan="free")
    assert result["actions"] == []
    assert result["sparse_signal"] is True
    assert result["fallback_reason"] == "all_protected"


def test_build_priority_actions_sparse_signal_when_fewer_than_3(products):
    short_products = [_make_product(handle="prod-1", status="ACTIVE"), _make_product(handle="prod-2", status="ACTIVE")]

    def _stub_find_opps_short(products, shop_domain, gsc_page_rows, gsc_query_rows, **kwargs):
        return {
            "opportunities": [_make_opportunity(handle=f"prod-{i}") for i in range(1, 3)],
            "total_products_scanned": 2,
            "scope": {"active": 2},
            "summary": {"by_tier": {"high": 2, "medium": 0, "low": 0}, "by_intent": {}, "average_score": 75},
        }

    def _stub_prio_short(products, shop_domain, gsc_page_rows, *, top, scope):
        return {"rows": [_make_prio(handle=f"prod-{i}") for i in range(1, 3)]}

    with (
        patch("app.priorities.engine.find_opportunities_for_catalog", side_effect=_stub_find_opps_short),
        patch("app.priorities.engine.prioritize_catalog", side_effect=_stub_prio_short),
        patch("app.priorities.engine.assess_product_risk", side_effect=_stub_risk_safe),
        patch("app.priorities.engine.filter_products_by_scope", side_effect=_stub_scope),
    ):
        result = build_priority_actions(short_products, "shop.myshopify.com", "shop", {}, [], plan="free")
    assert result["sparse_signal"] is True


def test_build_priority_actions_actions_sorted_by_rank(products):
    with (
        patch("app.priorities.engine.find_opportunities_for_catalog", side_effect=_stub_find_opps),
        patch("app.priorities.engine.prioritize_catalog", side_effect=_stub_prio),
        patch("app.priorities.engine.assess_product_risk", side_effect=_stub_risk_safe),
        patch("app.priorities.engine.filter_products_by_scope", side_effect=_stub_scope),
    ):
        result = build_priority_actions(products, "shop.myshopify.com", "shop", {}, [], plan="free")
    ranks = [a["rank"] for a in result["actions"]]
    assert ranks == sorted(ranks)


def test_build_priority_actions_no_opportunities_returns_sparse(products):
    def _stub_empty(*args, **kwargs):
        return {"opportunities": [], "total_products_scanned": 0, "scope": {}, "summary": {}}

    with (
        patch("app.priorities.engine.find_opportunities_for_catalog", side_effect=_stub_empty),
        patch("app.priorities.engine.filter_products_by_scope", side_effect=_stub_scope),
    ):
        result = build_priority_actions(products, "shop.myshopify.com", "shop", {}, [], plan="free")
    assert result["sparse_signal"] is True
    assert result["actions"] == []
    assert result["fallback_reason"] == "no_opportunities"


def test_build_priority_actions_llm_mock_pro_plan(products):
    selections = [
        {"action_id": "prod-1-improve_seo_copy-1", "why_now": "Cette page est au seuil de la première page."},
        {"action_id": "prod-2-improve_seo_copy-2", "why_now": "CTR faible malgré bonne position."},
        {"action_id": "prod-3-improve_seo_copy-3", "why_now": "Score readiness insuffisant."},
    ]

    def _stub_try_llm(shop, candidates, niche_hypothesis, llm_router, *, db_path=None):
        return selections

    class FakeLLMRouter:
        pass

    with (
        patch("app.priorities.engine.find_opportunities_for_catalog", side_effect=_stub_find_opps),
        patch("app.priorities.engine.prioritize_catalog", side_effect=_stub_prio),
        patch("app.priorities.engine.assess_product_risk", side_effect=_stub_risk_safe),
        patch("app.priorities.engine.filter_products_by_scope", side_effect=_stub_scope),
        patch("app.priorities.engine.check_budget", return_value={"over_budget": False}),
        patch("app.priorities.engine._try_llm_arbitrage", side_effect=_stub_try_llm),
    ):
        result = build_priority_actions(
            products,
            "shop.myshopify.com",
            "shop",
            {},
            [],
            plan="pro",
            llm_router=FakeLLMRouter(),
        )
    assert result["llm_used"] is True
    assert result["fallback_reason"] is None


def test_build_priority_actions_budget_exceeded_falls_back(products):
    with (
        patch("app.priorities.engine.find_opportunities_for_catalog", side_effect=_stub_find_opps),
        patch("app.priorities.engine.prioritize_catalog", side_effect=_stub_prio),
        patch("app.priorities.engine.assess_product_risk", side_effect=_stub_risk_safe),
        patch("app.priorities.engine.filter_products_by_scope", side_effect=_stub_scope),
        patch("app.priorities.engine.check_budget", return_value={"over_budget": True}),
    ):
        result = build_priority_actions(
            products, "shop.myshopify.com", "shop", {}, [], plan="pro", llm_router=object()
        )
    assert result["llm_used"] is False
    assert result["fallback_reason"] == "budget_exceeded"
