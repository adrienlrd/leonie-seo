"""Tests for continuous improvement tags and element status."""

from __future__ import annotations

from pathlib import Path

from app.db import init_db
from app.geo.continuous_improvement import (
    build_improvement_elements,
    enrich_market_analysis_result,
    merge_product_tags,
    set_product_tag,
)

SHOP = "store.myshopify.com"
PRODUCT_ID = "gid://shopify/Product/1"


def _product() -> dict:
    return {
        "product_id": PRODUCT_ID,
        "product_title": "Harnais chien",
        "product_handle": "harnais-chien",
        "target_customer": "Chien sensible",
        "buying_intents": ["choisir un harnais confortable"],
        "seo_keywords": [
            {
                "query": "harnais chien confortable",
                "product_fit_score": 85,
                "data_source": "gsc",
                "reason": "Good product fit.",
            },
            {
                "query": "collier chat",
                "product_fit_score": 20,
                "data_source": "llm_estimated",
                "reason": "Low product fit.",
            },
        ],
        "content_test_pack": {
            "proposed_meta_title": "Harnais chien confortable",
            "proposed_meta_description": "",
            "proposed_product_description": "Un harnais confortable pour chien sensible.",
            "proposed_faq": [],
            "proposed_geo_answer_block": "Ce harnais aide à choisir une taille adaptée.",
            "proposed_blog_title": "",
            "proposed_image_alts": [],
            "facts_missing": ["materials"],
        },
    }


def test_build_improvement_elements_marks_each_surface_when_generated() -> None:
    elements = build_improvement_elements(_product())

    status_by_key = {element["key"]: element["improved"] for element in elements}

    assert status_by_key["meta_title"] is True
    assert status_by_key["meta_description"] is False
    assert status_by_key["product_description"] is True
    assert status_by_key["geo_answer_block"] is True
    assert status_by_key["faq"] is False


def test_merge_product_tags_preserves_merchant_forced_tag_when_analysis_runs(
    tmp_path: Path,
) -> None:
    db = tmp_path / "history.db"
    init_db(db)
    set_product_tag(
        SHOP,
        PRODUCT_ID,
        label="Made in France",
        tag_type="merchant",
        status="forced",
        db_path=db,
    )

    tags = merge_product_tags(SHOP, _product(), persist=True, db_path=db)
    labels = {tag["label"]: tag for tag in tags}

    assert labels["Made in France"]["locked_by_merchant"] is True
    assert labels["Made in France"]["status"] == "forced"
    assert labels["harnais chien confortable"]["status"] == "positive"
    assert labels["collier chat"]["status"] == "negative"


def test_enrich_market_analysis_result_attaches_tags_and_elements(tmp_path: Path) -> None:
    db = tmp_path / "history.db"
    init_db(db)
    result = {"products": [_product()]}

    enriched = enrich_market_analysis_result(SHOP, result, persist_tags=True, db_path=db)

    product = enriched["products"][0]
    assert product["improvement_tags"]
    assert product["improvement_elements"]
    assert any(tag["status"] == "negative" for tag in product["improvement_tags"])
