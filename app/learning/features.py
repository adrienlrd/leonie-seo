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


def _clean_feature(value: Any, *, fallback: str = "unknown", max_len: int = 80) -> str:
    text = str(value or "").strip().lower()
    return text[:max_len] if text else fallback


def _optimization_attribution(metadata: dict[str, Any]) -> dict[str, Any]:
    value = metadata.get("optimization_attribution")
    return value if isinstance(value, dict) else {}


def _append_list_features(
    features: list[tuple[str, str]],
    *,
    feature_key: str,
    values: Any,
    limit: int = 5,
) -> None:
    if not isinstance(values, list):
        return
    seen: set[str] = set()
    for value in values:
        clean = _clean_feature(value)
        if clean == "unknown" or clean in seen:
            continue
        seen.add(clean)
        features.append((feature_key, clean))
        if len(seen) >= limit:
            break


def _append_competitor_gap_features(
    features: list[tuple[str, str]],
    gaps: Any,
    *,
    limit: int = 5,
) -> None:
    if not isinstance(gaps, list):
        return
    count = 0
    for gap in gaps:
        if not isinstance(gap, dict):
            continue
        action_type = _clean_feature(gap.get("action_type"))
        if action_type != "unknown":
            features.append(("competitor_gap_action", action_type))
            count += 1
        if count >= limit:
            break


def _experiment_features(metadata: dict[str, Any]) -> list[tuple[str, str]]:
    attribution = _optimization_attribution(metadata)
    target_keyword = _clean_feature(
        metadata.get("target_keyword") or attribution.get("target_keyword"),
        fallback="",
    )
    features: list[tuple[str, str]] = [
        ("field", _clean_feature(metadata.get("field") or attribution.get("field"))),
        ("target_keyword_present", "yes" if target_keyword else "no"),
        (
            "target_keyword_source",
            _clean_feature(
                metadata.get("keyword_source") or attribution.get("keyword_source"),
            ),
        ),
    ]
    verdict = _clean_feature(metadata.get("experiment_verdict"), fallback="")
    if verdict:
        features.append(("experiment_verdict", verdict))
    if metadata.get("queries_targeted_count"):
        features.append(("queries_targeted", "present"))
    if metadata.get("facts_used_count"):
        features.append(("facts_used", "present"))
    _append_list_features(
        features,
        feature_key="reinforce_tag",
        values=attribution.get("reinforce_tags"),
    )
    _append_list_features(features, feature_key="avoid_tag", values=attribution.get("avoid_tags"))
    _append_list_features(
        features,
        feature_key="forced_tag",
        values=attribution.get("forced_tags"),
    )
    _append_list_features(
        features,
        feature_key="pending_question",
        values=attribution.get("pending_question_keys"),
    )
    _append_competitor_gap_features(features, attribution.get("competitor_gaps"))
    return features


def features_for_observation(
    observation: LearningObservation,
    *,
    product: dict[str, Any] | None = None,
    risk_level: str = "low",
    application_mode: str = "semi_auto",
) -> list[tuple[str, str]]:
    """Build stable feature pairs used by the learner."""
    features = [
        ("action_type", observation.action_type),
        ("surface", observation.surface or "product_page"),
        ("keyword_source", observation.keyword_source or "unknown"),
        ("product_category", product_category(product)),
        ("confidence_bucket", confidence_bucket(observation.confidence_score)),
        ("risk_level", risk_level),
        ("application_mode", application_mode),
    ]
    features.extend(_experiment_features(observation.metadata))
    return features


def features_for_candidate(candidate: CandidateAction) -> list[tuple[str, str]]:
    """Build feature pairs used to score one candidate action."""
    metadata = dict(candidate.metadata or {})
    attribution = _optimization_attribution(metadata)
    if attribution and "keyword_source" not in metadata:
        metadata["keyword_source"] = attribution.get("keyword_source") or candidate.keyword_source
    if "field" not in metadata:
        metadata["field"] = candidate.field
    return [
        ("action_type", candidate.action_type),
        ("surface", candidate.surface),
        ("keyword_source", candidate.keyword_source),
        ("confidence_bucket", confidence_bucket(candidate.confidence_score)),
        ("content_quality_score_bucket", quality_bucket(candidate.content_quality_score)),
        ("risk_level", candidate.risk_level.value),
    ] + _experiment_features(metadata)
