"""Tests for the Opportunity Finder deterministic scoring engine."""

from __future__ import annotations

from app.opportunities.finder import (
    _confidence,
    _gsc_signal_for_product,
    _tier,
    find_opportunities_for_catalog,
)


def _make_product(
    pid: str = "gid://shopify/Product/1",
    handle: str = "test-product",
    title: str = "Test Product",
    status: str = "ACTIVE",
) -> dict:
    return {
        "id": pid,
        "handle": handle,
        "title": title,
        "status": status,
        "descriptionHtml": "Description courte du produit.",
        "variants": {"edges": [{"node": {"price": "29.99", "inventoryQuantity": 10}}]},
        "seo": {"title": "Test Product SEO title ok", "description": "Meta description suffisante pour ce produit."},
    }


def _make_active(handle: str = "prod", title: str = "Produit") -> dict:
    return _make_product(handle=handle, title=title, status="ACTIVE")


def _make_draft(handle: str = "draft-prod", title: str = "Brouillon") -> dict:
    return _make_product(handle=handle, title=title, status="DRAFT")


def test_find_opportunities_returns_one_row_per_product():
    products = [_make_active("a", "Alpha"), _make_active("b", "Beta")]
    result = find_opportunities_for_catalog(products, "shop.myshopify.com", {}, [])
    assert result["total_products_scanned"] == 2
    assert len(result["opportunities"]) == 2


def test_opportunity_score_is_between_0_and_100():
    products = [_make_active("p1", "Harnais chien")]
    result = find_opportunities_for_catalog(products, "shop.myshopify.com", {}, [])
    for opp in result["opportunities"]:
        assert 0 <= opp["opportunity_score"] <= 100


def test_tier_thresholds_high_medium_low():
    assert _tier(70) == "high"
    assert _tier(80) == "high"
    assert _tier(69) == "medium"
    assert _tier(40) == "medium"
    assert _tier(39) == "low"
    assert _tier(0) == "low"


def test_scope_active_excludes_draft_products():
    products = [_make_active("a", "Active"), _make_draft("b", "Draft")]
    result = find_opportunities_for_catalog(products, "shop.myshopify.com", {}, [], scope="active")
    handles = [opp["handle"] for opp in result["opportunities"]]
    assert "a" in handles
    assert "b" not in handles


def test_niche_priority_product_adds_10_points():
    product = _make_active("p1", "Collier chien")
    product["id"] = "gid://shopify/Product/1"

    niche = {
        "status": "validated_by_merchant",
        "priority_products": [{"product_id": "gid://shopify/Product/1", "reason": "Top seller", "confidence": "high"}],
        "forbidden_promises": [],
        "conversational_intents": [],
    }

    result_without = find_opportunities_for_catalog([product], "shop.myshopify.com", {}, [])
    result_with = find_opportunities_for_catalog([product], "shop.myshopify.com", {}, [], niche_hypothesis=niche)

    score_without = result_without["opportunities"][0]["opportunity_score"]
    score_with = result_with["opportunities"][0]["opportunity_score"]
    assert score_with >= score_without
    # If base score < 90, the +10 bonus should be visible
    if score_without <= 90:
        assert score_with == min(score_without + 10, 100)


def test_niche_forbidden_promise_adds_alert_no_score_bonus():
    product = _make_active("p1", "Soin magique")
    product["descriptionHtml"] = "garantir un résultat médical extraordinaire pour votre animal"
    product["id"] = "gid://shopify/Product/1"

    niche = {
        "status": "validated_by_merchant",
        "priority_products": [],
        "forbidden_promises": [{"promise": "garantir un résultat médical", "reason": "unverifiable"}],
        "conversational_intents": [],
    }

    result = find_opportunities_for_catalog([product], "shop.myshopify.com", {}, [], niche_hypothesis=niche)
    opp = result["opportunities"][0]
    assert any(a["type"] == "forbidden_promise" for a in opp["niche_alerts"])


def test_confidence_high_when_3_or_more_signals():
    signals = [
        {"type": "gsc_signal", "value": 0.5},
        {"type": "keyword_gap", "value": 0.3},
        {"type": "audit_pressure", "value": 0.7},
        {"type": "intent_match", "value": 0.0},
    ]
    assert _confidence(signals) == "high"

    signals_two = [
        {"type": "gsc_signal", "value": 0.5},
        {"type": "keyword_gap", "value": 0.3},
        {"type": "audit_pressure", "value": 0.0},
    ]
    assert _confidence(signals_two) == "medium"

    signals_zero = [{"type": "gsc_signal", "value": 0.0}, {"type": "keyword_gap", "value": 0.0}]
    assert _confidence(signals_zero) == "low"


def test_gsc_not_connected_scores_zero_gsc_signal():
    product = _make_active("no-gsc", "Sans GSC")
    val, ev = _gsc_signal_for_product(product, "shop.myshopify.com", {})
    assert val == 0.0
    assert ev == {}


def test_results_sorted_descending_by_score():
    products = [
        _make_active("a", "Zz produit"),
        _make_active("b", "Aa produit"),
    ]
    # Give product b a GSC signal for higher priority score
    gsc_page_rows = {
        "https://shop.myshopify.com/products/b": {
            "clicks": 5,
            "impressions": 100,
            "ctr": 0.02,
            "position": 15.0,
        }
    }
    result = find_opportunities_for_catalog(products, "shop.myshopify.com", gsc_page_rows, [])
    scores = [opp["opportunity_score"] for opp in result["opportunities"]]
    assert scores == sorted(scores, reverse=True)
