"""Tests for persisted merchant confirmations used by market analysis."""

from __future__ import annotations

from app.market_analysis import jobs


def test_merchant_facts_are_merged_when_product_is_answered_again(tmp_path, monkeypatch) -> None:
    """A merchant can complete missing proof over several short sessions."""
    monkeypatch.setattr(jobs, "_DATA_DIR", tmp_path)

    jobs.save_merchant_facts(
        "shop.myshopify.com",
        "gid://shopify/Product/1",
        {"warranty": "Garantie 2 ans."},
    )
    saved = jobs.save_merchant_facts(
        "shop.myshopify.com",
        "gid://shopify/Product/1",
        {"care": "Rincer le filtre chaque semaine."},
    )

    assert saved == {
        "warranty": "Garantie 2 ans.",
        "care": "Rincer le filtre chaque semaine.",
    }
    assert jobs.load_merchant_facts("shop.myshopify.com") == {
        "gid://shopify/Product/1": saved,
    }


def test_fact_enriched_result_replaces_persisted_product_analysis(tmp_path, monkeypatch) -> None:
    """The regenerated proposal remains available after leaving the page."""
    monkeypatch.setattr(jobs, "_DATA_DIR", tmp_path)
    initial = {
        "products": [{"product_id": "gid://shopify/Product/1", "seo_keywords": []}],
        "analyzed_product_count": 1,
        "total_opportunity_count": 0,
    }
    jobs.save_latest_result("shop.myshopify.com", initial)

    updated = {
        "product_id": "gid://shopify/Product/1",
        "seo_keywords": [{"query": "fontaine chat"}],
        "geo_questions": [{"question": "Quelle garantie ?"}],
    }

    assert (
        jobs.replace_product_analysis("shop.myshopify.com", updated, "2026-05-27T12:00:00+00:00")
        is True
    )
    assert jobs.load_latest_result("shop.myshopify.com") == {
        "products": [updated],
        "analyzed_at": "2026-05-27T12:00:00+00:00",
        "analyzed_product_count": 1,
        "total_opportunity_count": 2,
    }
