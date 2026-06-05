"""Canonical per-product optimization context.

The context is a compact hand-off object between market analysis, content
generation, competitor intelligence and learning. It keeps facts, hypotheses,
tags and competitor patterns separated so downstream generators can use the
right signal for the right purpose.
"""

from __future__ import annotations

from typing import Any

CONTEXT_VERSION = "2026-06-05.v1"

_SURFACE_TO_CONTENT_TYPE: dict[str, str] = {
    "meta_title": "meta_title",
    "meta_description": "meta_description",
    "product_description": "product_description",
    "faq": "faq_block",
    "geo_answer_block": "answer_block",
    "blog": "buying_guide",
    "image_alts": "alt_text",
    "jsonld": "jsonld_faqpage",
    "internal_links": "internal_link",
}


def _coerce_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _coerce_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _clean_text(value: Any, *, limit: int | None = None) -> str:
    text = str(value or "").strip()
    return text[:limit] if limit and len(text) > limit else text


def _unique_texts(values: list[Any], *, limit: int = 12) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        text = _clean_text(value)
        key = text.lower()
        if not text or key in seen:
            continue
        seen.add(key)
        out.append(text)
        if len(out) >= limit:
            break
    return out


def build_tag_guidance(tags: list[dict[str, Any]]) -> dict[str, Any]:
    """Turn improvement tags into generation and automation guidance."""
    reinforce: list[str] = []
    avoid: list[str] = []
    forced: list[str] = []
    risks: list[dict[str, Any]] = []
    locked: list[dict[str, Any]] = []
    keyword_targets: list[str] = []

    for tag in tags:
        label = _clean_text(tag.get("label"), limit=120)
        if not label:
            continue
        status = _clean_text(tag.get("status"))
        tag_type = _clean_text(tag.get("tag_type"))
        is_locked = bool(tag.get("locked_by_merchant"))

        if status in {"positive", "forced"}:
            reinforce.append(label)
        if status == "forced":
            forced.append(label)
        if status == "negative":
            avoid.append(label)
        if tag_type == "keyword" and status in {"positive", "forced"}:
            keyword_targets.append(label)
        if tag_type == "risk" or status == "negative":
            risks.append(
                {
                    "label": label,
                    "tag_type": tag_type or "risk",
                    "status": status or "negative",
                    "locked_by_merchant": is_locked,
                    "reason": _clean_text(tag.get("reason"), limit=240),
                }
            )
        if is_locked:
            locked.append(
                {
                    "label": label,
                    "tag_type": tag_type,
                    "status": status,
                    "reason": _clean_text(tag.get("reason"), limit=240),
                }
            )

    auto_apply_blockers = [
        risk["label"] for risk in risks if risk["locked_by_merchant"] or risk["tag_type"] == "risk"
    ]
    return {
        "reinforce": _unique_texts(reinforce, limit=12),
        "avoid": _unique_texts(avoid, limit=12),
        "forced": _unique_texts(forced, limit=8),
        "keyword_targets": _unique_texts(keyword_targets, limit=8),
        "risks": risks[:12],
        "locked": locked[:12],
        "auto_apply_blockers": _unique_texts(auto_apply_blockers, limit=8),
        "auto_apply_allowed_by_tags": not auto_apply_blockers,
    }


def build_competitor_guidance(insights: dict[str, Any]) -> dict[str, Any]:
    """Convert competitor crawl insights into non-copying structural guidance."""
    gaps = [gap for gap in _coerce_list(insights.get("merchant_gaps")) if isinstance(gap, dict)]
    patterns = _coerce_dict(insights.get("dominant_patterns"))
    top_urls = [item for item in _coerce_list(insights.get("top_urls")) if isinstance(item, dict)]

    structural_actions: list[dict[str, Any]] = []
    for gap in gaps[:8]:
        action_type = _clean_text(gap.get("action_type") or gap.get("gap"))
        structural_actions.append(
            {
                "gap": _clean_text(gap.get("gap")),
                "action_type": action_type,
                "recommended_surface": action_type,
                "priority_boost": int(gap.get("priority_boost") or 0),
                "reason": _clean_text(gap.get("reason"), limit=280),
            }
        )

    recurring_h2: list[str] = []
    sample_titles: list[str] = []
    sample_meta_descriptions: list[str] = []
    paa_questions: list[str] = []
    featured_snippets: list[str] = []
    for item in top_urls:
        seo = _coerce_dict(item.get("seo"))
        structure = _coerce_dict(item.get("structure"))
        serp = _coerce_dict(item.get("serp"))
        if seo.get("title"):
            sample_titles.append(_clean_text(seo.get("title"), limit=180))
        if seo.get("meta_description"):
            sample_meta_descriptions.append(_clean_text(seo.get("meta_description"), limit=260))
        recurring_h2.extend(_coerce_list(structure.get("h2_texts"))[:6])
        paa_questions.extend(_coerce_list(serp.get("paa_questions"))[:6])
        if serp.get("featured_snippet"):
            featured_snippets.append(_clean_text(serp.get("featured_snippet"), limit=320))

    return {
        "enabled": bool(insights.get("enabled")),
        "sample_size": int(insights.get("sample_size") or 0),
        "priority_boost_total": int(insights.get("priority_boost_total") or 0),
        "prompt_summary": _clean_text(insights.get("prompt_summary"), limit=500),
        "dominant_patterns": patterns,
        "structural_actions": structural_actions,
        "non_copy_instruction": (
            "Use competitor data only as structural inspiration; never reuse wording, "
            "claims, proprietary examples or brand-specific promises."
        ),
        "evidence": {
            "sample_titles": _unique_texts(sample_titles, limit=5),
            "sample_meta_descriptions": _unique_texts(sample_meta_descriptions, limit=5),
            "recurring_h2_topics": _unique_texts(recurring_h2, limit=12),
            "paa_questions": _unique_texts(paa_questions, limit=12),
            "featured_snippets": _unique_texts(featured_snippets, limit=3),
        },
    }


def build_surface_matrix(product: dict[str, Any]) -> list[dict[str, Any]]:
    """Return one readiness row per optimizable product surface."""
    pack = _coerce_dict(product.get("content_test_pack"))
    elements = [
        item for item in _coerce_list(product.get("improvement_elements")) if isinstance(item, dict)
    ]
    surface_plan = _coerce_dict(pack.get("surface_plan"))
    surface_statuses = _coerce_dict(pack.get("surface_statuses"))
    questions = [
        item for item in _coerce_list(pack.get("merchant_questions")) if isinstance(item, dict)
    ]

    rows: list[dict[str, Any]] = []
    for element in elements:
        key = _clean_text(element.get("key"))
        if not key:
            continue
        blockers = [
            _clean_text(question.get("key") or question.get("field_key"))
            for question in questions
            if key in _coerce_list(question.get("unlocks_surfaces"))
        ]
        plan = _coerce_dict(surface_plan.get(key))
        rows.append(
            {
                "surface": key,
                "content_type": _SURFACE_TO_CONTENT_TYPE.get(key, key),
                "label": _clean_text(element.get("label")) or key,
                "improved": bool(element.get("improved")),
                "status": _clean_text(element.get("status")) or "unknown",
                "generation_allowed": bool(plan.get("generate", True)),
                "generation_reason": _clean_text(plan.get("reason"), limit=240),
                "quality_status": surface_statuses.get(key),
                "blocking_question_keys": [value for value in blockers if value],
            }
        )
    return rows


def build_question_pipeline(product: dict[str, Any]) -> dict[str, Any]:
    """Normalize merchant questions as data-improvement tasks."""
    pack = _coerce_dict(product.get("content_test_pack"))
    questions = [
        item
        for item in (
            _coerce_list(product.get("merchant_questions"))
            or _coerce_list(pack.get("merchant_questions"))
            or _coerce_list(pack.get("pending_questions"))
        )
        if isinstance(item, dict)
    ]
    confirmed_facts = [
        item for item in _coerce_list(pack.get("confirmed_facts")) if isinstance(item, dict)
    ]
    answered_keys = {
        _clean_text(item.get("key") or item.get("label"))
        for item in confirmed_facts
        if _clean_text(item.get("source")) == "merchant_confirmation"
    }

    normalized: list[dict[str, Any]] = []
    for question in questions[:8]:
        key = _clean_text(question.get("key") or question.get("field_key"))
        status = "answered" if key in answered_keys else "pending"
        normalized.append(
            {
                "key": key,
                "field_key": _clean_text(question.get("field_key") or key),
                "status": status,
                "question": _clean_text(question.get("question"), limit=300),
                "target_keyword": _clean_text(question.get("target_keyword"), limit=120),
                "unlocks_surfaces": _coerce_list(question.get("unlocks_surfaces"))[:6],
                "why_it_matters": _clean_text(question.get("why_it_matters"), limit=300),
            }
        )

    return {
        "pending": [item for item in normalized if item["status"] == "pending"],
        "answered": [item for item in normalized if item["status"] == "answered"],
        "confirmed_fact_keys": sorted(key for key in answered_keys if key),
    }


def build_product_optimization_context(
    shop: str,
    product: dict[str, Any],
    *,
    business_profile: dict[str, Any] | None = None,
    niche_hypothesis: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the canonical per-product context consumed downstream."""
    pack = _coerce_dict(product.get("content_test_pack"))
    tags = [
        item for item in _coerce_list(product.get("improvement_tags")) if isinstance(item, dict)
    ]
    insights = _coerce_dict(
        product.get("competitor_crawl_insights") or pack.get("competitor_crawl_insights")
    )
    keywords = [
        item for item in _coerce_list(product.get("seo_keywords")) if isinstance(item, dict)
    ]
    content_quality = _coerce_dict(pack.get("content_quality"))

    tag_guidance = build_tag_guidance(tags)
    competitor_guidance = build_competitor_guidance(insights)

    primary_keyword = next(
        (keyword for keyword in keywords if _clean_text(keyword.get("target_role")) == "primary"),
        keywords[0] if keywords else {},
    )
    secondary_keywords = [
        keyword for keyword in keywords if _clean_text(keyword.get("target_role")) == "secondary"
    ]

    profile_context = _coerce_dict(product.get("business_profile_context"))
    if not profile_context and business_profile:
        profile_context = {
            "brand_name": _clean_text(business_profile.get("brand_name")),
            "field_names": sorted(str(k) for k, v in business_profile.items() if v),
        }

    return {
        "version": CONTEXT_VERSION,
        "shop": shop,
        "resource": {
            "type": "product",
            "id": _clean_text(product.get("product_id")),
            "handle": _clean_text(product.get("product_handle")),
            "title": _clean_text(product.get("product_title")),
            "url": _clean_text(product.get("product_url")),
        },
        "profile": {
            "business_profile_status": _clean_text(product.get("business_profile_context_status")),
            "business_profile_hash": _clean_text(product.get("business_profile_context_hash")),
            "business_profile_context": profile_context,
            "niche_status": _clean_text((niche_hypothesis or {}).get("status")),
            "primary_niche": _clean_text(
                (niche_hypothesis or {}).get("primary_niche")
                or _coerce_dict((niche_hypothesis or {}).get("shop_summary")).get("primary_niche")
                or product.get("target_customer")
            ),
        },
        "keywords": {
            "primary": primary_keyword,
            "secondary": secondary_keywords[:5],
            "supporting": [
                keyword
                for keyword in keywords
                if _clean_text(keyword.get("target_role")) == "supporting"
            ][:8],
            "locked_or_forced": tag_guidance["keyword_targets"],
        },
        "facts": {
            "confirmed": _coerce_list(pack.get("confirmed_facts"))[:20],
            "missing": _coerce_list(pack.get("facts_missing"))[:12],
            "conflicts": _coerce_list(product.get("fact_conflicts"))[:12],
        },
        "questions": build_question_pipeline(product),
        "tags": {
            "all": tags,
            "guidance": tag_guidance,
        },
        "surfaces": build_surface_matrix(product),
        "competitors": competitor_guidance,
        "generation_contract": {
            "market_analysis_role": "diagnostic_and_brief",
            "final_generation_role": "content_actions",
            "recommended_content_types": [
                row["content_type"]
                for row in build_surface_matrix(product)
                if not row["improved"] and row["generation_allowed"]
            ][:8],
            "quality_score": int(content_quality.get("score") or 0),
            "publish_ready": bool(product.get("publish_ready")),
            "auto_apply_allowed": bool(product.get("auto_apply_allowed"))
            and tag_guidance["auto_apply_allowed_by_tags"],
            "auto_apply_blockers": tag_guidance["auto_apply_blockers"],
        },
        "attribution": {
            "opportunity_score": int(product.get("opportunity_score") or 0),
            "keyword_source": _clean_text(primary_keyword.get("data_source") or "unknown"),
            "competitor_pattern_boost": int(product.get("competitor_pattern_boost") or 0),
            "active_tag_labels": tag_guidance["reinforce"],
            "negative_tag_labels": tag_guidance["avoid"],
        },
        "sources_used": _coerce_list(product.get("sources_used")),
    }


def content_action_feedback_from_context(context: dict[str, Any]) -> str:
    """Render compact context feedback for prompt variables."""
    tags = _coerce_dict(_coerce_dict(context.get("tags")).get("guidance"))
    competitors = _coerce_dict(context.get("competitors"))
    questions = _coerce_dict(context.get("questions"))

    bits: list[str] = []
    reinforce = ", ".join(_coerce_list(tags.get("reinforce"))[:6])
    avoid = ", ".join(_coerce_list(tags.get("avoid"))[:6])
    forced = ", ".join(_coerce_list(tags.get("forced"))[:4])
    if reinforce:
        bits.append(f"Reinforce validated tags: {reinforce}.")
    if forced:
        bits.append(f"Merchant-forced tags must be respected: {forced}.")
    if avoid:
        bits.append(f"Avoid negative or retired tags: {avoid}.")
    structural_actions = [
        item
        for item in _coerce_list(competitors.get("structural_actions"))
        if isinstance(item, dict)
    ]
    if structural_actions:
        action_labels = ", ".join(
            _clean_text(item.get("gap") or item.get("action_type"))
            for item in structural_actions[:4]
            if _clean_text(item.get("gap") or item.get("action_type"))
        )
        if action_labels:
            bits.append(
                f"Competitor-derived structural gaps to address without copying: {action_labels}."
            )
    pending_questions = [
        item for item in _coerce_list(questions.get("pending")) if isinstance(item, dict)
    ]
    if pending_questions:
        keys = ", ".join(_clean_text(item.get("key")) for item in pending_questions[:4])
        bits.append(f"Do not make unsupported claims for pending fact keys: {keys}.")
    bits.append(
        "Market analysis is diagnostic; create final publishable copy through Content Actions."
    )
    return " ".join(bit for bit in bits if bit).strip()
