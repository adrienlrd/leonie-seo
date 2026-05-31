"""Tests for AI crawlability and llms.txt preview."""

from __future__ import annotations

from app.geo.crawlability import build_ai_crawlability_advisor


def test_build_ai_crawlability_advisor_includes_ready_products_and_policies() -> None:
    snapshot = {
        "shop": {"domain": "example.com"},
        "products": [
            {
                "id": "1",
                "title": "Harnais chien nylon",
                "handle": "harnais-chien",
                "description": "Harnais en nylon réglable, lavable, fabriqué en France avec garantie 30 jours.",
                "variants": {"edges": [{"node": {"price": "49.90"}}]},
            }
        ],
        "collections": [{"id": "10", "title": "Harnais chien", "handle": "harnais-chien"}],
    }

    data = build_ai_crawlability_advisor("shop.myshopify.com", snapshot)

    assert data["domain"] == "example.com"
    assert data["summary"]["dry_run"] is True
    assert data["summary"]["included_pages"] >= 3
    assert "/products/harnais-chien" in data["llms_txt"]
    assert "does not guarantee ranking" in data["llms_txt"]
    assert "robots.default_groups" in data["robots_txt_liquid"]
    assert "User-agent: GPTBot" in data["robots_txt_liquid"]
    assert data["robots_install_steps"][0].startswith("Online Store")


def test_build_ai_crawlability_advisor_excludes_thin_products() -> None:
    snapshot = {
        "products": [
            {
                "id": "1",
                "title": "Bol chat",
                "handle": "bol-chat",
                "description": "Bol chat design.",
            }
        ],
        "collections": [],
    }

    data = build_ai_crawlability_advisor("shop.myshopify.com", snapshot)

    assert data["summary"]["excluded_or_review_pages"] == 1
    assert data["excluded_pages"][0]["path"] == "/products/bol-chat"
    assert data["warnings"]
