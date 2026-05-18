"""Tests for fact-grounded GEO answer blocks."""

from __future__ import annotations

from app.geo.answers import build_catalog_answer_blocks, build_product_answer_blocks


def test_build_product_answer_blocks_uses_confirmed_facts_when_available() -> None:
    product = {
        "id": "gid://shopify/Product/1",
        "title": "Harnais chien nylon",
        "handle": "harnais-chien",
        "description": "Harnais en nylon réglable, lavable, fabriqué en France. Garantie 30 jours.",
        "product_type": "Harnais chien",
        "variants": {"edges": [{"node": {"price": "49.90"}}]},
    }

    data = build_product_answer_blocks(product)

    assert data["dry_run"] is True
    assert data["answer_block_count"] > 0
    assert data["answer_blocks"][0]["confidence"] == "confirmed"
    assert data["jsonld"]["@type"] == "FAQPage"
    answers = " ".join(block["answer"] for block in data["answer_blocks"])
    assert "nylon" in answers
    assert data["review_prompts"]


def test_build_product_answer_blocks_keeps_missing_sensitive_facts_as_review_prompts() -> None:
    product = {
        "id": "gid://shopify/Product/2",
        "title": "Bol chat",
        "handle": "bol-chat",
        "description": "Bol chat design.",
    }

    data = build_product_answer_blocks(product)

    assert data["answer_block_count"] >= 1
    prompt_keys = {prompt["key"] for prompt in data["review_prompts"]}
    assert "materials" in prompt_keys
    assert "origins" in prompt_keys


def test_build_catalog_answer_blocks_sorts_products_with_more_answers_first() -> None:
    products = [
        {
            "id": "1",
            "title": "Bol chat",
            "handle": "bol-chat",
            "description": "Bol chat design.",
        },
        {
            "id": "2",
            "title": "Harnais chien nylon",
            "handle": "harnais-chien",
            "description": "Harnais en nylon réglable, fabriqué en France.",
            "product_type": "Harnais chien",
            "variants": {"edges": [{"node": {"price": "49.90"}}]},
        },
    ]

    data = build_catalog_answer_blocks(products)

    assert data["total"] == 2
    assert data["summary"]["dry_run"] is True
    assert data["products"][0]["title"] == "Harnais chien nylon"
