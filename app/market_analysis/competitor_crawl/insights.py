"""Build product-level insights from competitor crawl features."""

from __future__ import annotations

from statistics import median
from typing import Any

_BOOST_CAP = 20


def build_competitor_crawl_insights(
    product_result_or_pack: dict,
    competitor_features: list[dict],
    merchant_product_features: dict | None = None,
) -> dict:
    """Compare crawled competitor patterns with merchant page gaps."""
    valid_features = [item for item in competitor_features if isinstance(item, dict)]
    sample_size = len(valid_features)
    if sample_size < 2:
        return {
            "enabled": True,
            "sample_size": sample_size,
            "top_urls": _top_urls(valid_features),
            "dominant_patterns": {},
            "merchant_gaps": [],
            "priority_boost_total": 0,
            "prompt_summary": "Competitor crawl sample too small for reliable structural boosts.",
        }
    merchant = merchant_product_features or {}
    patterns = _dominant_patterns(valid_features)
    gaps = _merchant_gaps(patterns, merchant)
    boost_total = min(_BOOST_CAP, sum(int(gap.get("priority_boost", 0)) for gap in gaps))
    return {
        "enabled": True,
        "sample_size": sample_size,
        "top_urls": _top_urls(valid_features),
        "dominant_patterns": patterns,
        "merchant_gaps": gaps,
        "priority_boost_total": boost_total,
        "prompt_summary": _prompt_summary(patterns, gaps),
    }


def _top_urls(features: list[dict[str, Any]]) -> list[dict[str, Any]]:
    top = []
    for item in sorted(features, key=lambda f: int(f.get("rank", 999) or 999))[:5]:
        top.append(
            {
                "url": item.get("url", ""),
                "domain": item.get("domain", ""),
                "rank": item.get("rank", 0),
                "keyword": item.get("keyword", ""),
                "keyword_intent_type": item.get("keyword_intent_type", ""),
                "title": item.get("title", ""),
                "page_type": item.get("page_type", "unknown"),
                "final_url": item.get("final_url", item.get("url", "")),
                "feature_summary": {
                    "has_faq_block": bool(item.get("has_faq_block")),
                    "has_product_schema": bool(item.get("has_product_schema")),
                    "has_breadcrumb_schema": bool(item.get("has_breadcrumb_schema")),
                    "word_count": int(item.get("word_count", 0) or 0),
                    "internal_link_count": int(item.get("internal_link_count", 0) or 0),
                },
                "seo": _seo_detail(item),
                "structure": _structure_detail(item),
                "geo_aeo": _geo_aeo_detail(item),
                "schema": _schema_detail(item),
                "links": _links_detail(item),
                "images": _images_detail(item),
                "trust": _trust_detail(item),
                "product_depth": _product_depth_detail(item),
                "serp": _serp_detail(item),
            }
        )
    return top


def _keyword_present(text: str, keyword: str) -> bool:
    words = {word for word in keyword.lower().replace("’", "'").split() if len(word) >= 3}
    haystack = text.lower()
    return bool(words) and all(word in haystack for word in words)


def _has_cta(text: str) -> bool:
    lower = text.lower()
    return any(
        marker in lower
        for marker in (
            "découvrir",
            "découvrez",
            "decouvrir",
            "decouvrez",
            "acheter",
            "commander",
            "choisir",
            "profiter",
            "voir",
            "shop",
            "buy",
        )
    )


def _has_commercial_benefit(text: str) -> bool:
    lower = text.lower()
    return any(
        marker in lower
        for marker in (
            "livraison",
            "garantie",
            "qualité",
            "qualite",
            "confort",
            "premium",
            "durable",
            "facile",
            "offert",
            "promo",
        )
    )


def _seo_detail(item: dict[str, Any]) -> dict[str, Any]:
    keyword = str(item.get("keyword", ""))
    title = str(item.get("title", ""))
    meta = str(item.get("meta_description", ""))
    return {
        "title": title,
        "title_length": int(item.get("title_length", 0) or 0),
        "title_keyword_present": _keyword_present(title, keyword),
        "title_promise_detected": _has_commercial_benefit(title),
        "meta_description": meta,
        "meta_description_length": int(item.get("meta_description_length", 0) or 0),
        "meta_keyword_present": _keyword_present(meta, keyword),
        "meta_has_commercial_angle": _has_commercial_benefit(meta),
        "meta_has_cta": _has_cta(meta),
        "canonical_present": bool(item.get("canonical_present")),
    }


def _structure_detail(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "h1_count": int(item.get("h1_count", 0) or 0),
        "h1_text": item.get("h1_text", ""),
        "h2_count": int(item.get("h2_count", 0) or 0),
        "h2_texts": list(item.get("h2_texts", []) or [])[:20],
        "h3_count": int(item.get("h3_count", 0) or 0),
        "h3_texts": list(item.get("h3_texts", []) or [])[:20],
        "word_count": int(item.get("word_count", 0) or 0),
        "paragraph_count": int(item.get("paragraph_count", 0) or 0),
        "has_bullet_lists": bool(item.get("has_bullet_lists")),
        "has_comparison_table": bool(item.get("has_comparison_table")),
        "has_product_specs_table": bool(item.get("has_product_specs_table")),
        "has_pros_cons": bool(item.get("has_pros_cons")),
        "has_buying_guide": bool(item.get("has_buying_guide")),
        "has_how_to_structure": bool(item.get("has_how_to_structure")),
        "has_breadcrumb_block": bool(item.get("has_breadcrumb_block")),
        "breadcrumb_structure": item.get("breadcrumb_structure", ""),
    }


def _geo_aeo_detail(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "has_faq_block": bool(item.get("has_faq_block")),
        "faq_question_count": int(item.get("faq_question_count", 0) or 0),
        "has_short_answer_block": bool(item.get("has_short_answer_block")),
        "short_answer_block_count": int(item.get("short_answer_block_count", 0) or 0),
        "has_definition_block": bool(item.get("has_definition_block")),
        "answerability_score": int(item.get("answerability_score", 0) or 0),
        "ai_readability_score": int(item.get("ai_readability_score", 0) or 0),
    }


def _schema_detail(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "jsonld_count": int(item.get("jsonld_count", 0) or 0),
        "schema_types": list(item.get("schema_types", []) or []),
        "has_product_schema": bool(item.get("has_product_schema")),
        "has_offer_schema": bool(item.get("has_offer_schema")),
        "has_breadcrumb_schema": bool(item.get("has_breadcrumb_schema")),
        "has_faq_schema": bool(item.get("has_faq_schema")),
        "has_article_schema": bool(item.get("has_article_schema")),
        "has_organization_schema": bool(item.get("has_organization_schema")),
        "schema_completeness_score": int(item.get("schema_completeness_score", 0) or 0),
    }


def _links_detail(item: dict[str, Any]) -> dict[str, Any]:
    examples = list(item.get("internal_link_examples", []) or [])[:12]
    return {
        "internal_link_count": int(item.get("internal_link_count", 0) or 0),
        "external_link_count": int(item.get("external_link_count", 0) or 0),
        "internal_link_examples": examples,
        "product_link_count": sum(1 for link in examples if link.get("target_type") == "product"),
        "collection_link_count": sum(
            1 for link in examples if link.get("target_type") == "collection"
        ),
        "blog_link_count": sum(1 for link in examples if link.get("target_type") == "blog"),
    }


def _images_detail(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "image_count": int(item.get("image_count", 0) or 0),
        "image_alt_count": int(item.get("image_alt_count", 0) or 0),
        "images_missing_alt_count": int(item.get("images_missing_alt_count", 0) or 0),
        "descriptive_image_alt_count": int(item.get("descriptive_image_alt_count", 0) or 0),
        "image_alt_examples": list(item.get("image_alt_examples", []) or [])[:8],
    }


def _trust_detail(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "has_reviews_or_social_proof": bool(item.get("has_reviews_or_social_proof")),
        "has_trust_proof": bool(item.get("has_trust_proof")),
        "trust_proof_types": list(item.get("trust_proof_types", []) or []),
    }


def _product_depth_detail(item: dict[str, Any]) -> dict[str, Any]:
    depth = item.get("content_depth") if isinstance(item.get("content_depth"), dict) else {}
    return {
        "materials": bool(depth.get("materials")),
        "dimensions": bool(depth.get("dimensions")),
        "usage": bool(depth.get("usage")),
        "compatibility": bool(depth.get("compatibility")),
        "care": bool(depth.get("care")),
    }


def _serp_detail(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "paa_questions": list(item.get("serp_paa_questions", []) or [])[:10],
        "featured_snippet": item.get("serp_featured_snippet"),
        "featured_snippet_present": bool(item.get("serp_featured_snippet")),
        "serp_feature_targets": list(item.get("serp_feature_targets", []) or []),
    }


def _dominant_patterns(features: list[dict[str, Any]]) -> dict[str, Any]:
    count = len(features)
    word_counts = [int(f.get("word_count", 0) or 0) for f in features]
    internal_links = [int(f.get("internal_link_count", 0) or 0) for f in features]
    faq_counts = [int(f.get("faq_question_count", 0) or 0) for f in features]
    return {
        "has_faq_block_rate": _rate(features, "has_faq_block", count),
        "has_product_schema_rate": _rate(features, "has_product_schema", count),
        "has_faq_schema_rate": _rate(features, "has_faq_schema", count),
        "has_breadcrumb_schema_rate": _rate(features, "has_breadcrumb_schema", count),
        "has_short_answer_block_rate": _rate(features, "has_short_answer_block", count),
        "median_word_count": int(median(word_counts)) if word_counts else 0,
        "median_internal_links": int(median(internal_links)) if internal_links else 0,
        "median_faq_questions": int(median(faq_counts)) if faq_counts else 0,
    }


def _merchant_gaps(patterns: dict[str, Any], merchant: dict[str, Any]) -> list[dict[str, Any]]:
    gaps: list[dict[str, Any]] = []
    if patterns.get("has_faq_block_rate", 0) >= 0.6 and not merchant.get("has_faq_block"):
        gaps.append(
            _gap(
                "missing_faq_block",
                "faq",
                8,
                "Most top competitor pages include a visible FAQ block.",
            )
        )
    if patterns.get("has_product_schema_rate", 0) >= 0.6 and not merchant.get("has_product_schema"):
        gaps.append(
            _gap(
                "missing_product_schema",
                "schema",
                6,
                "Most top competitor pages expose Product schema.",
            )
        )
    if patterns.get("has_breadcrumb_schema_rate", 0) >= 0.6 and not merchant.get(
        "has_breadcrumb_schema"
    ):
        gaps.append(
            _gap(
                "missing_breadcrumb_schema",
                "schema",
                4,
                "Top competitor pages commonly expose Breadcrumb schema.",
            )
        )
    if patterns.get("has_short_answer_block_rate", 0) >= 0.5 and not merchant.get(
        "has_short_answer_block"
    ):
        gaps.append(
            _gap(
                "missing_geo_answer_block",
                "geo_answer",
                5,
                "Competitor pages often include short extractable answer blocks.",
            )
        )
    if (
        int(patterns.get("median_internal_links", 0) or 0) >= 8
        and int(merchant.get("internal_link_count", 0) or 0) < 4
    ):
        gaps.append(
            _gap(
                "weak_internal_linking",
                "internal_linking",
                4,
                "Top competitor pages use stronger internal linking.",
            )
        )
    if (
        int(patterns.get("median_word_count", 0) or 0) >= 500
        and int(merchant.get("word_count", 0) or 0) < 200
    ):
        gaps.append(
            _gap(
                "thin_product_description",
                "product_description",
                5,
                "Top competitor pages have deeper product content.",
            )
        )
    return gaps


def _gap(gap: str, action_type: str, priority_boost: int, reason: str) -> dict[str, Any]:
    return {
        "gap": gap,
        "action_type": action_type,
        "priority_boost": priority_boost,
        "reason": reason,
    }


def _rate(features: list[dict[str, Any]], key: str, count: int) -> float:
    if count <= 0:
        return 0.0
    return round(sum(1 for item in features if item.get(key)) / count, 2)


def _prompt_summary(patterns: dict[str, Any], gaps: list[dict[str, Any]]) -> str:
    bits: list[str] = []
    if patterns.get("has_faq_block_rate", 0) >= 0.6:
        bits.append("FAQ")
    if patterns.get("has_product_schema_rate", 0) >= 0.6:
        bits.append("Product schema")
    if patterns.get("has_breadcrumb_schema_rate", 0) >= 0.6:
        bits.append("Breadcrumb schema")
    if patterns.get("has_short_answer_block_rate", 0) >= 0.5:
        bits.append("short answer blocks")
    if not bits:
        return "No dominant competitor structure pattern detected."
    gap_bits = ", ".join(gap["gap"] for gap in gaps[:3])
    suffix = f" Merchant gaps: {gap_bits}." if gap_bits else ""
    return f"Top competitor pages commonly include {', '.join(bits)}.{suffix}"
