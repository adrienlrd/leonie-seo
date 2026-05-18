"""Tests for GEO collection suggestions."""

from __future__ import annotations

from app.geo.collections import build_collection_suggestions, parse_gsc_query_page_csv


def test_parse_gsc_query_page_csv_returns_normalized_rows_when_valid() -> None:
    rows = parse_gsc_query_page_csv(
        "query,page,clicks,impressions,ctr,position\n"
        "meilleur harnais chien,/products/harnais-chien,10,500,0.02,8\n"
    )

    assert rows == [
        {
            "query": "meilleur harnais chien",
            "page": "/products/harnais-chien",
            "clicks": 10,
            "impressions": 500,
            "ctr": 0.02,
            "position": 8.0,
        }
    ]


def test_build_collection_suggestions_returns_dry_run_preview_when_cluster_has_products() -> None:
    products = [
        {
            "id": "1",
            "title": "Harnais chien nylon",
            "handle": "harnais-chien-nylon",
            "product_type": "Harnais chien",
            "tags": ["chien", "nylon"],
        },
        {
            "id": "2",
            "title": "Harnais chien cuir",
            "handle": "harnais-chien-cuir",
            "product_type": "Harnais chien",
            "tags": ["chien", "cuir"],
        },
    ]
    query_rows = [
        {
            "query": "meilleur harnais chien",
            "page": "/collections/harnais-chien",
            "clicks": 5,
            "impressions": 400,
            "ctr": 0.01,
            "position": 9,
        }
    ]

    data = build_collection_suggestions(products, [], query_rows, min_products=2)

    assert data["total"] == 1
    suggestion = data["suggestions"][0]
    assert suggestion["dry_run"] is True
    assert suggestion["suggested_title"] == "Meilleur harnais chien"
    assert suggestion["product_count"] == 2
    assert suggestion["estimated_impressions"] == 400
    assert suggestion["preview"]["faq_questions"]


def test_build_collection_suggestions_warns_when_handle_already_exists() -> None:
    products = [
        {"id": "1", "title": "Bol chat céramique", "handle": "bol-chat-ceramique", "product_type": "Bol chat"},
        {"id": "2", "title": "Bol chat inox", "handle": "bol-chat-inox", "product_type": "Bol chat"},
    ]
    collections = [{"handle": "meilleur-bol-chat"}]
    query_rows = [{"query": "meilleur bol chat", "impressions": 200, "clicks": 4}]

    data = build_collection_suggestions(products, collections, query_rows, min_products=2)

    assert data["suggestions"][0]["handle"] == "meilleur-bol-chat"
    assert "A collection with this handle already exists." in data["suggestions"][0]["warnings"]
