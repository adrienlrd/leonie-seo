"""Typed models for the SEO/GEO learning engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class LearningMode(StrEnum):
    SEMI_AUTO = "semi_auto"
    AUTO_APPLY = "auto_apply"


class RiskLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class MerchantDecision(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EDITED = "edited"
    AUTO_APPLIED = "auto_applied"


class ApprovalStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EDITED = "edited"
    APPLIED = "applied"
    FAILED = "failed"


class LearningVerdict(StrEnum):
    POSITIVE_HIGH_CONFIDENCE = "positive_high_confidence"
    POSITIVE_LOW_CONFIDENCE = "positive_low_confidence"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"
    INCONCLUSIVE = "inconclusive"
    POLLUTED_WINDOW = "polluted_window"


PRIMARY_WINDOW_DAYS = 28
LEARNING_WINDOWS_DAYS = (14, 28, 60)
PRIMARY_WINDOW_LABEL = "J+28"


@dataclass(frozen=True)
class MerchantLearningSettings:
    shop: str
    enabled: bool = True
    mode: LearningMode = LearningMode.SEMI_AUTO
    allow_bulk_approval: bool = True
    max_auto_actions_per_cycle: int = 3
    min_confidence_to_auto_apply: int = 80
    min_confidence_to_suggest: int = 45
    require_approval_for_medium_risk: bool = True


@dataclass(frozen=True)
class LearningObservation:
    shop: str
    resource_type: str
    resource_id: str
    action_type: str
    surface: str
    keyword_source: str
    before_metrics: dict[str, Any]
    after_metrics: dict[str, Any]
    control_metrics: dict[str, Any]
    window_days: int
    window_label: str
    is_primary_window: bool
    outcome_score: float
    confidence_score: int
    ledger_event_id: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    features: list[tuple[str, str]] = field(default_factory=list)


@dataclass(frozen=True)
class LearningWeight:
    scope: str
    shop: str | None
    feature_key: str
    feature_value: str
    weight: float
    sample_size: int
    confidence: int


@dataclass(frozen=True)
class CandidateAction:
    shop: str
    resource_type: str
    resource_id: str
    resource_title: str
    action_type: str
    field: str
    surface: str
    current_score: float
    potential_score: float
    confidence_score: int
    risk_level: RiskLevel
    keyword_source: str = "unknown"
    content_quality_score: int = 0
    old_value: str = ""
    proposed_value: str = ""
    tags: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PolicyDecision:
    candidate: CandidateAction
    previous_score: float
    learning_score: float
    final_score: float
    mode: LearningMode
    approval_required: bool
    risk_level: RiskLevel
    merchant_decision: MerchantDecision
    explanation: dict[str, Any]
    auto_apply_eligible: bool
