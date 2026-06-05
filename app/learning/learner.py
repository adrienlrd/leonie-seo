"""Confidence-weighted moving-average learner."""

from __future__ import annotations

from pathlib import Path

from app.learning.models import LearningObservation
from app.learning.store import get_weight, upsert_weight


def _updated_confidence(sample_size: int, observation_confidence: int) -> int:
    base = min(80, sample_size * 8)
    return max(0, min(100, round(base + observation_confidence * 0.2)))


def update_weights_from_observation(
    observation: LearningObservation,
    *,
    db_path: Path | None = None,
) -> int:
    """Update merchant and anonymized global weights for one observation."""
    if observation.metadata.get("learnable") is False:
        return 0
    if observation.confidence_score < 35:
        return 0
    normalized_outcome = observation.outcome_score / 100.0
    confidence_factor = observation.confidence_score / 100.0
    updated = 0
    for feature_key, feature_value in observation.features:
        for scope, weight_shop in (("merchant", observation.shop), ("global", None)):
            existing = get_weight(
                scope=scope,
                shop=weight_shop,
                feature_key=feature_key,
                feature_value=feature_value,
                db_path=db_path,
            )
            old_weight = existing.weight if existing else 0.0
            sample_size = (existing.sample_size if existing else 0) + 1
            new_weight = old_weight * 0.85 + normalized_outcome * 0.15 * confidence_factor
            confidence = _updated_confidence(sample_size, observation.confidence_score)
            upsert_weight(
                scope=scope,
                shop=weight_shop,
                feature_key=feature_key,
                feature_value=feature_value,
                weight=max(-1.0, min(1.0, new_weight)),
                sample_size=sample_size,
                confidence=confidence,
                db_path=db_path,
            )
            updated += 1
    return updated
