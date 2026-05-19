"""Tests for the GEO FAQ & Buying Guide generator (task 126)."""

from __future__ import annotations

from app.geo.faq_generator import (
    generate_catalog_content,
    generate_collection_faq,
    generate_product_content,
)


def _product(
    *,
    pid: str = "gid://shopify/Product/1",
    title: str = "Harnais nylon chien",
    product_type: str = "Harnais",
    description: str = "Harnais ergonomique en nylon. Compatible chiens 10-40 kg. Garantie 2 ans.",
    price: str = "39.90",
    status: str = "ACTIVE",
) -> dict:
    return {
        "id": pid,
        "title": title,
        "handle": title.lower().replace(" ", "-"),
        "product_type": product_type,
        "descriptionHtml": description,
        "status": status,
        "variants": {"edges": [{"node": {"price": price}}]},
        "tags": [],
    }


def _collection(*, cid: str = "col-1", title: str = "Harnais chien", description: str = "") -> dict:
    return {
        "id": cid,
        "title": title,
        "handle": title.lower().replace(" ", "-"),
        "body_html": description,
    }


# ---- Product content tests -------------------------------------------------


def test_generate_product_content_returns_required_fields() -> None:
    product = _product()
    result = generate_product_content(product, gsc_queries=[])

    assert result["content_type"] == "product_faq"
    assert result["resource_type"] == "product"
    assert result["resource_title"] == "Harnais nylon chien"
    assert isinstance(result["faq_items"], list)
    assert isinstance(result["buying_guide"], dict)
    assert isinstance(result["answer_block"], str)
    assert isinstance(result["faq_jsonld"], dict)
    assert isinstance(result["quality_score"], int)
    assert result["status"] in ("draft", "needs_review")


def test_faq_items_generated_from_confirmed_facts() -> None:
    product = _product(description="Harnais en nylon. Garantie 2 ans.")
    result = generate_product_content(product)

    # Should have at least product type or description-derived question
    assert len(result["faq_items"]) >= 1


def test_gsc_queries_are_matched_to_product_title() -> None:
    product = _product(title="Harnais nylon chien")
    queries = [
        "harnais pour chien grande race",
        "collier anti-traction chat",
        "meilleur harnais chien nylon",
    ]
    result = generate_product_content(product, gsc_queries=queries)

    assert result["source_queries"]  # at least one matched
    assert any("harnais" in q.lower() for q in result["source_queries"])


def test_irrelevant_queries_not_matched() -> None:
    product = _product(title="Harnais nylon chien")
    queries = ["collier cuir chat persan", "cage transport perroquet"]
    result = generate_product_content(product, gsc_queries=queries)

    assert result["source_queries"] == []


def test_faq_jsonld_has_correct_schema_type() -> None:
    product = _product()
    result = generate_product_content(product)
    jsonld = result["faq_jsonld"]

    assert jsonld["@type"] == "FAQPage"
    assert "@context" in jsonld
    assert isinstance(jsonld["mainEntity"], list)


def test_status_is_needs_review_when_many_missing_facts() -> None:
    # Product with minimal info → many missing facts
    product = {
        "id": "p1",
        "title": "Produit mystère",
        "product_type": "",
        "descriptionHtml": "",
        "status": "ACTIVE",
        "variants": {"edges": []},
        "tags": [],
        "handle": "produit-mystere",
    }
    result = generate_product_content(product)

    assert result["status"] == "needs_review"


def test_quality_score_is_higher_with_rich_product() -> None:
    rich = _product(description="Harnais en nylon certifié ISO. Pour chiens 10-40 kg. Garantie 2 ans. Livraison offerte.")
    poor = {"id": "p2", "title": "X", "product_type": "", "descriptionHtml": "", "variants": {"edges": []}, "tags": [], "handle": "x", "status": "ACTIVE"}

    rich_result = generate_product_content(rich, gsc_queries=["harnais chien nylon"])
    poor_result = generate_product_content(poor)

    assert rich_result["quality_score"] > poor_result["quality_score"]


def test_answer_block_contains_product_title() -> None:
    product = _product(title="Harnais nylon chien")
    result = generate_product_content(product)

    assert "Harnais nylon chien" in result["answer_block"]


def test_buying_guide_sections_present_when_facts_available() -> None:
    product = _product(description="Compatible chiens 10-40 kg. Garantie 2 ans. Entretien facile à la machine.")
    result = generate_product_content(product)

    assert "sections" in result["buying_guide"]


def test_stable_id_is_deterministic() -> None:
    product = _product(pid="gid://shopify/Product/42")
    r1 = generate_product_content(product)
    r2 = generate_product_content(product)

    assert r1["id"] == r2["id"]


# ---- Collection FAQ tests --------------------------------------------------


def test_generate_collection_faq_returns_required_fields() -> None:
    collection = _collection(title="Harnais chien", description="Tous nos harnais pour chien.")
    products = [_product(title="Harnais nylon"), _product(title="Harnais cuir", pid="p2")]
    result = generate_collection_faq(collection, products)

    assert result["content_type"] == "collection_faq"
    assert result["resource_type"] == "collection"
    assert len(result["faq_items"]) >= 1
    assert "Harnais chien" in result["answer_block"]


def test_collection_faq_includes_product_titles() -> None:
    collection = _collection(title="Accessoires chien")
    products = [_product(title="Harnais nylon"), _product(title="Collier cuir", pid="p2")]
    result = generate_collection_faq(collection, products)

    combined = " ".join(item["answer"] for item in result["faq_items"])
    assert "Harnais nylon" in combined or "Collier cuir" in combined


# ---- Catalog content tests -------------------------------------------------


def test_generate_catalog_content_returns_summary() -> None:
    products = [_product(), _product(pid="p2", title="Collier cuir chat")]
    result = generate_catalog_content(products, top=2)

    assert result["summary"]["total"] == 2
    assert "by_status" in result["summary"]
    assert "by_quality" in result["summary"]
    assert 0 <= result["summary"]["avg_quality_score"] <= 100


def test_generate_catalog_content_with_collections() -> None:
    products = [_product()]
    collections = [_collection(title="Harnais")]
    result = generate_catalog_content(products, collections=collections, top=1)

    assert result["summary"]["total"] == 2  # 1 product + 1 collection
    types = [item["content_type"] for item in result["content_items"]]
    assert "product_faq" in types
    assert "collection_faq" in types
