"""Learning policy for ranking and routing SEO/GEO actions."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.learning.explain import explain_candidate, explain_decision
from app.learning.features import features_for_candidate
from app.learning.models import (
    CandidateAction,
    LearningMode,
    MerchantDecision,
    MerchantLearningSettings,
    PolicyDecision,
    RiskLevel,
)
from app.learning.risk import is_auto_apply_field_allowed
from app.learning.store import (
    create_pending_approval,
    get_settings,
    get_weight,
    record_decision,
)


def _risk_penalty(risk_level: RiskLevel) -> float:
    if risk_level == RiskLevel.HIGH:
        return 25.0
    if risk_level == RiskLevel.MEDIUM:
        return 12.0
    return 2.0


def _freshness_penalty(candidate: CandidateAction) -> float:
    generated_at = candidate.metadata.get("generated_at")
    if not generated_at:
        return 0.0
    try:
        parsed = datetime.fromisoformat(str(generated_at).replace("Z", "+00:00"))
    except ValueError:
        return 0.0
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    age_days = (datetime.now(UTC) - parsed.astimezone(UTC)).days
    if age_days <= 14:
        return 0.0
    return min(15.0, (age_days - 14) / 3)


def _average_weight(
    *,
    shop: str,
    features: list[tuple[str, str]],
    scope: str,
    db_path: Path | None = None,
) -> float:
    values: list[float] = []
    for feature_key, feature_value in features:
        weight = get_weight(
            scope=scope,
            shop=shop if scope == "merchant" else None,
            feature_key=feature_key,
            feature_value=feature_value,
            db_path=db_path,
        )
        if weight is not None:
            values.append(weight.weight)
    return sum(values) / len(values) if values else 0.0


def is_auto_apply_eligible(
    candidate: CandidateAction,
    settings: MerchantLearningSettings,
    *,
    plan: str,
    writer_supported: bool,
    confirm_live_write: bool,
) -> bool:
    """Return True when all automatic apply safeguards are satisfied."""
    return (
        settings.enabled
        and settings.mode == LearningMode.AUTO_APPLY
        and plan in {"pro", "agency"}
        and candidate.confidence_score >= settings.min_confidence_to_auto_apply
        and candidate.risk_level == RiskLevel.LOW
        and is_auto_apply_field_allowed(candidate.field)
        and writer_supported
        and confirm_live_write
        and not any(
            tag.get("locked_by_merchant") and tag.get("status") == "negative"
            for tag in candidate.tags
        )
    )


def score_candidate(
    candidate: CandidateAction,
    *,
    settings: MerchantLearningSettings,
    db_path: Path | None = None,
) -> PolicyDecision:
    """Score one candidate and decide whether approval is required."""
    features = features_for_candidate(candidate)
    merchant_weight = _average_weight(
        shop=candidate.shop, features=features, scope="merchant", db_path=db_path
    )
    global_weight = _average_weight(
        shop=candidate.shop, features=features, scope="global", db_path=db_path
    )
    risk_penalty = _risk_penalty(candidate.risk_level)
    freshness_penalty = _freshness_penalty(candidate)
    learning_score = (merchant_weight * 70.0) + (global_weight * 30.0)
    final_score = (
        candidate.current_score * 0.60
        + candidate.potential_score * 0.25
        + learning_score
        + candidate.confidence_score * 0.10
        - risk_penalty
        - freshness_penalty
    )
    final_score = max(0.0, min(100.0, final_score))
    approval_required = (
        settings.mode == LearningMode.SEMI_AUTO
        or candidate.risk_level != RiskLevel.LOW
        or candidate.confidence_score < settings.min_confidence_to_auto_apply
    )
    explanation = explain_candidate(
        candidate,
        merchant_weight=merchant_weight,
        global_weight=global_weight,
        risk_penalty=risk_penalty,
        freshness_penalty=freshness_penalty,
        final_score=final_score,
    )
    return PolicyDecision(
        candidate=candidate,
        previous_score=candidate.current_score,
        learning_score=learning_score,
        final_score=final_score,
        mode=settings.mode,
        approval_required=approval_required,
        risk_level=candidate.risk_level,
        merchant_decision=MerchantDecision.PENDING,
        explanation=explanation,
        auto_apply_eligible=False,
    )


def rank_candidates(
    shop: str,
    candidates: list[CandidateAction],
    *,
    plan: str = "free",
    writer_supported_by_field: dict[str, bool] | None = None,
    confirm_live_write: bool = False,
    max_auto_actions: int | None = None,
    mode_override: LearningMode | None = None,
    db_path: Path | None = None,
) -> list[PolicyDecision]:
    """Rank candidates and persist decisions plus required approvals."""
    settings = get_settings(shop, db_path=db_path)
    if mode_override is not None:
        settings = MerchantLearningSettings(
            shop=settings.shop,
            enabled=settings.enabled,
            mode=mode_override,
            allow_bulk_approval=settings.allow_bulk_approval,
            max_auto_actions_per_cycle=settings.max_auto_actions_per_cycle,
            min_confidence_to_auto_apply=settings.min_confidence_to_auto_apply,
            min_confidence_to_suggest=settings.min_confidence_to_suggest,
            require_approval_for_medium_risk=settings.require_approval_for_medium_risk,
        )
    writer_supported = writer_supported_by_field or {}
    decisions: list[PolicyDecision] = []
    auto_remaining = (
        settings.max_auto_actions_per_cycle
        if max_auto_actions is None
        else min(settings.max_auto_actions_per_cycle, max_auto_actions)
    )
    for candidate in candidates:
        decision = score_candidate(candidate, settings=settings, db_path=db_path)
        eligible = is_auto_apply_eligible(
            candidate,
            settings,
            plan=plan,
            writer_supported=writer_supported.get(candidate.field, False),
            confirm_live_write=confirm_live_write,
        )
        if eligible and auto_remaining > 0:
            auto_remaining -= 1
            decision = PolicyDecision(
                candidate=decision.candidate,
                previous_score=decision.previous_score,
                learning_score=decision.learning_score,
                final_score=decision.final_score,
                mode=decision.mode,
                approval_required=False,
                risk_level=decision.risk_level,
                merchant_decision=MerchantDecision.AUTO_APPLIED,
                explanation=decision.explanation,
                auto_apply_eligible=True,
            )
        elif candidate.confidence_score >= settings.min_confidence_to_suggest:
            create_pending_approval(
                shop=shop,
                resource_type=candidate.resource_type,
                resource_id=candidate.resource_id,
                action_type=candidate.action_type,
                field=candidate.field,
                old_value=candidate.old_value,
                proposed_value=candidate.proposed_value,
                confidence_score=candidate.confidence_score,
                risk_level=candidate.risk_level.value,
                expected_impact=decision.explanation.get("expected_impact", {}),
                explanation={
                    **explain_decision(decision),
                    "product_title": candidate.resource_title,
                    "content_action_id": candidate.metadata.get("action_id"),
                    "content_type": candidate.metadata.get("content_type", candidate.action_type),
                },
                db_path=db_path,
            )

        record_decision(
            shop=shop,
            resource_id=candidate.resource_id,
            action_type=candidate.action_type,
            previous_score=decision.previous_score,
            learning_score=decision.learning_score,
            final_score=decision.final_score,
            mode=decision.mode.value,
            approval_required=decision.approval_required,
            risk_level=decision.risk_level.value,
            merchant_decision=decision.merchant_decision.value,
            explanation=explain_decision(decision),
            db_path=db_path,
        )
        decisions.append(decision)
    decisions.sort(key=lambda item: item.final_score, reverse=True)
    return decisions


def learning_boost_for_action(
    *,
    shop: str,
    action_type: str,
    surface: str = "product_page",
    keyword_source: str = "unknown",
    db_path: Path | None = None,
) -> dict[str, Any]:
    """Return a small transparent boost/penalty for legacy scoring engines."""
    candidate = CandidateAction(
        shop=shop,
        resource_type="product",
        resource_id="",
        resource_title="",
        action_type=action_type,
        field=action_type,
        surface=surface,
        current_score=50,
        potential_score=50,
        confidence_score=50,
        risk_level=RiskLevel.LOW,
        keyword_source=keyword_source,
    )
    features = features_for_candidate(candidate)
    merchant_weight = _average_weight(
        shop=shop, features=features, scope="merchant", db_path=db_path
    )
    global_weight = _average_weight(shop=shop, features=features, scope="global", db_path=db_path)
    boost = (merchant_weight * 10.0) + (global_weight * 4.0)
    return {
        "learning_boost": round(boost, 2),
        "merchant_weight": round(merchant_weight, 4),
        "global_weight": round(global_weight, 4),
        "reason": (
            "Learning boost from merchant outcomes and anonymized aggregate outcomes."
            if boost
            else "No mature learning signal yet."
        ),
    }


def enrich_market_products(
    shop: str,
    products: list[dict[str, Any]],
    *,
    db_path: Path | None = None,
) -> list[dict[str, Any]]:
    """Attach learning signals to market-analysis product results."""
    for product in products:
        pack = (
            product.get("content_test_pack")
            if isinstance(product.get("content_test_pack"), dict)
            else {}
        )
        action_type = "meta_title"
        if pack.get("proposed_meta_description"):
            action_type = "meta_description"
        if pack.get("proposed_product_description"):
            action_type = "product_description"
        signal = learning_boost_for_action(
            shop=shop,
            action_type=action_type,
            keyword_source=str(
                (product.get("seo_keywords") or [{}])[0].get("data_source") or "unknown"
            )
            if product.get("seo_keywords")
            else "unknown",
            db_path=db_path,
        )
        base_score = float(product.get("opportunity_score") or 0)
        product["learning_signals"] = signal
        product["learning_score"] = round(
            max(0.0, min(100.0, base_score + signal["learning_boost"])), 2
        )
        product["learning_recommendation_reason"] = signal["reason"]
    return products
