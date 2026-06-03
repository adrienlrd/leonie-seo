"""Risk scoring for SEO/GEO learning decisions."""

from __future__ import annotations

from typing import Any

from app.learning.models import RiskLevel

_SAFE_AUTO_FIELDS = frozenset(
    {
        "meta_title",
        "meta_description",
        "product_description",
        "schema_facts",
    }
)

_MEDIUM_FIELDS = frozenset({"faq", "faq_block", "geo_block", "internal_link"})

_HIGH_FIELDS = frozenset(
    {
        "blog",
        "jsonld",
        "jsonld_faqpage",
        "llms.txt",
        "llms-full.txt",
        "agents.md",
        "alt_text",
        "theme",
    }
)


def assess_action_risk(
    action_type: str,
    *,
    field: str | None = None,
    content_quality_score: int = 0,
    tags: list[dict[str, Any]] | None = None,
) -> RiskLevel:
    """Return a conservative risk level for one proposed action."""
    key = (field or action_type or "").strip().lower()
    if key in _HIGH_FIELDS or action_type in _HIGH_FIELDS:
        return RiskLevel.HIGH
    if key in _MEDIUM_FIELDS or action_type in _MEDIUM_FIELDS:
        return RiskLevel.MEDIUM
    if key == "product_description" and content_quality_score and content_quality_score < 75:
        return RiskLevel.MEDIUM
    if any(tag.get("locked_by_merchant") and tag.get("status") == "negative" for tag in tags or []):
        return RiskLevel.MEDIUM
    if key in _SAFE_AUTO_FIELDS or action_type in _SAFE_AUTO_FIELDS:
        return RiskLevel.LOW
    return RiskLevel.MEDIUM


def is_auto_apply_field_allowed(field: str) -> bool:
    """Return True when the field may be considered for automatic apply."""
    return field in {"meta_title", "meta_description", "product_description", "schema_facts"}
