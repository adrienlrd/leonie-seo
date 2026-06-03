"""Human-readable explanations for learning decisions."""

from __future__ import annotations

from app.learning.models import CandidateAction, PolicyDecision


def explain_candidate(
    candidate: CandidateAction,
    *,
    merchant_weight: float,
    global_weight: float,
    risk_penalty: float,
    freshness_penalty: float,
    final_score: float,
) -> dict:
    """Return compact evidence for UI and audit logs."""
    return {
        "reason": (
            f"Action scored from current opportunity {candidate.current_score:.0f}, "
            f"learned merchant weight {merchant_weight:+.2f}, "
            f"global anonymized weight {global_weight:+.2f}, "
            f"risk penalty {risk_penalty:.1f}."
        ),
        "score_factors": {
            "current_score": round(candidate.current_score, 2),
            "potential_score": round(candidate.potential_score, 2),
            "merchant_weight": round(merchant_weight, 4),
            "global_weight": round(global_weight, 4),
            "confidence_score": candidate.confidence_score,
            "risk_penalty": round(risk_penalty, 2),
            "freshness_penalty": round(freshness_penalty, 2),
            "final_score": round(final_score, 2),
        },
        "expected_impact": {
            "summary": "Expected uplift is based on observed outcomes for similar actions.",
            "score_delta_estimate": round((final_score - candidate.current_score) / 5, 1),
        },
    }


def explain_decision(decision: PolicyDecision) -> dict:
    """Return a serializable explanation for a stored policy decision."""
    return {
        **decision.explanation,
        "approval_required": decision.approval_required,
        "risk_level": decision.risk_level.value,
        "mode": decision.mode.value,
        "auto_apply_eligible": decision.auto_apply_eligible,
    }
