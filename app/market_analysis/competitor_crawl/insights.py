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
                "title": item.get("title", ""),
                "feature_summary": {
                    "has_faq_block": bool(item.get("has_faq_block")),
                    "has_product_schema": bool(item.get("has_product_schema")),
                    "has_breadcrumb_schema": bool(item.get("has_breadcrumb_schema")),
                    "word_count": int(item.get("word_count", 0) or 0),
                    "internal_link_count": int(item.get("internal_link_count", 0) or 0),
                },
            }
        )
    return top


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
