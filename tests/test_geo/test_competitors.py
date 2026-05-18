"""Tests for light GEO competitor monitoring."""

from __future__ import annotations

from app.geo.competitors import build_competitor_monitor


def test_build_competitor_monitor_returns_queries_and_competitor_checklists() -> None:
    products = [
        {
            "id": "1",
            "title": "Harnais chien nylon",
            "handle": "harnais-chien",
            "description": "Harnais en nylon réglable, lavable, fabriqué en France. Garantie 30 jours.",
        }
    ]
    query_rows = [
        {
            "query": "meilleur harnais chien",
            "page": "/products/harnais-chien",
            "clicks": 10,
            "impressions": 800,
            "position": 8,
        }
    ]

    data = build_competitor_monitor(products, query_rows, competitors="miacara.com,example.com")

    assert data["summary"]["dry_run"] is True
    assert data["summary"]["competitor_domains"] == 2
    assert data["queries"][0]["query"] == "meilleur harnais chien"
    assert data["queries"][0]["competitors"][0]["domain"] == "miacara.com"
    assert data["queries"][0]["recommended_action"]["action_type"] in {
        "add_answer_blocks",
        "enrich_product_facts",
        "strengthen_internal_links",
    }


def test_build_competitor_monitor_uses_catalog_fallback_without_gsc() -> None:
    products = [
        {
            "id": "1",
            "title": "Bol chat céramique",
            "handle": "bol-chat",
            "description": "Bol chat céramique stable pour repas quotidiens.",
        }
    ]

    data = build_competitor_monitor(products, competitors="")

    assert data["total"] == 1
    assert data["summary"]["gsc_query_rows"] == 0
    assert data["queries"][0]["competitors"] == []
    assert data["queries"][0]["copy_policy"]
