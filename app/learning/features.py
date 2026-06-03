"""Feature extraction for learning observations and candidate actions."""

from __future__ import annotations

from typing import Any

from app.learning.models import CandidateAction, LearningObservation


def confidence_bucket(score: int) -> str:
    """Return a compact confidence bucket for weight updates."""
    if score >= 80:
        return "high"
    if score >= 50:
        return "medium"
    return "low"


def quality_bucket(score: int) -> str:
    """Return a compact content quality bucket."""
    if score >= 85:
        return "excellent"
    if score >= 70:
        return "good"
    if score >= 45:
        return "mixed"
    return "weak"


def product_category(product: dict[str, Any] | None) -> str:
    """Extract the least-sensitive product category signal available."""
    if not product:
        return "unknown"
    for key in ("product_type", "category", "merchant_label", "target_customer"):
        value = str(product.get(key) or "").strip().lower()
        if value:
            return value[:80]
    return "unknown"


def keyword_source_from_product(product: dict[str, Any] | None) -> str:
    """Extract the strongest keyword source from a market-analysis product."""
    for keyword in (product or {}).get("seo_keywords") or []:
        if not isinstance(keyword, dict):
            continue
        source = str(keyword.get("data_source") or keyword.get("source") or "").strip()
        if source:
            return source
    return "unknown"


def features_for_observation(
    observation: LearningObservation,
    *,
    product: dict[str, Any] | None = None,
    risk_level: str = "low",
    application_mode: str = "semi_auto",
) -> list[tuple[str, str]]:
    """Build stable feature pairs used by the learner."""
    return [
        ("action_type", observation.action_type),
        ("surface", observation.surface or "product_page"),
        ("keyword_source", observation.keyword_source or "unknown"),
        ("product_category", product_category(product)),
        ("confidence_bucket", confidence_bucket(observation.confidence_score)),
        ("risk_level", risk_level),
        ("application_mode", application_mode),
    ]


def features_for_candidate(candidate: CandidateAction) -> list[tuple[str, str]]:
    """Build feature pairs used to score one candidate action."""
    return [
        ("action_type", candidate.action_type),
        ("surface", candidate.surface),
        ("keyword_source", candidate.keyword_source),
        ("confidence_bucket", confidence_bucket(candidate.confidence_score)),
        ("content_quality_score_bucket", quality_bucket(candidate.content_quality_score)),
        ("risk_level", candidate.risk_level.value),
    ]
