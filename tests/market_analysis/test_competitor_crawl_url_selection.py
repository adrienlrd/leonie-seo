"""Tests for competitor SERP URL selection."""

from __future__ import annotations

from app.market_analysis.competitor_crawl.url_selection import (
    select_competitor_urls_for_product,
)


def test_selects_top_serp_urls_when_valid_competitors_exist() -> None:
    targets = select_competitor_urls_for_product(
        [{"query": "fontaine chat", "target_rank": 1}],
        {
            "fontaine chat": {
                "top_competitors": [
                    {
                        "domain": "competitor-one.fr",
                        "url": "https://competitor-one.fr/products/a",
                        "rank": 1,
                        "title": "A",
                    },
                    {
                        "domain": "competitor-two.fr",
                        "url": "https://competitor-two.fr/a",
                        "rank": 3,
                        "title": "B",
                    },
                ]
            }
        },
        "merchant.myshopify.com",
        3,
    )

    assert [target.domain for target in targets] == ["competitor-one.fr", "competitor-two.fr"]
    assert targets[0].keyword == "fontaine chat"
    assert targets[0].rank == 1


def test_ignores_merchant_domain_when_serp_contains_same_shop() -> None:
    targets = select_competitor_urls_for_product(
        [{"query": "fontaine chat", "target_rank": 1}],
        {
            "fontaine chat": {
                "top_competitors": [
                    {
                        "domain": "merchant.myshopify.com",
                        "url": "https://merchant.myshopify.com/products/a",
                        "rank": 1,
                    },
                    {
                        "domain": "competitor.fr",
                        "url": "https://competitor.fr/products/a",
                        "rank": 2,
                    },
                ]
            }
        },
        "merchant.myshopify.com",
        3,
    )

    assert len(targets) == 1
    assert targets[0].domain == "competitor.fr"


def test_ignores_cart_checkout_account_and_search_when_urls_are_sensitive() -> None:
    targets = select_competitor_urls_for_product(
        [{"query": "fontaine chat", "target_rank": 1}],
        {
            "fontaine chat": {
                "top_competitors": [
                    {"domain": "a.fr", "url": "https://a.fr/cart", "rank": 1},
                    {"domain": "b.fr", "url": "https://b.fr/checkout", "rank": 2},
                    {"domain": "c.fr", "url": "https://c.fr/account/login", "rank": 3},
                    {"domain": "d.fr", "url": "https://d.fr/search?q=x", "rank": 4},
                    {"domain": "e.fr", "url": "https://e.fr/products/a", "rank": 5},
                ]
            }
        },
        "merchant.myshopify.com",
        5,
    )

    assert [target.domain for target in targets] == ["e.fr"]


def test_deduplicates_canonicalized_urls_when_tracking_params_differ() -> None:
    targets = select_competitor_urls_for_product(
        [{"query": "fontaine chat", "target_rank": 1}],
        {
            "fontaine chat": {
                "top_competitors": [
                    {"domain": "a.fr", "url": "https://a.fr/p?utm_source=x", "rank": 1},
                    {"domain": "a.fr", "url": "https://a.fr/p", "rank": 2},
                    {"domain": "b.fr", "url": "https://b.fr/p", "rank": 3},
                ]
            }
        },
        "merchant.myshopify.com",
        5,
    )

    assert [target.url for target in targets] == ["https://a.fr/p", "https://b.fr/p"]


def test_respects_max_urls_when_many_competitors_exist() -> None:
    targets = select_competitor_urls_for_product(
        [{"query": "fontaine chat", "target_rank": 1}],
        {
            "fontaine chat": {
                "top_competitors": [
                    {"domain": f"c{i}.fr", "url": f"https://c{i}.fr/p", "rank": i}
                    for i in range(1, 8)
                ]
            }
        },
        "merchant.myshopify.com",
        3,
    )

    assert len(targets) == 3
    assert [target.rank for target in targets] == [1, 2, 3]
