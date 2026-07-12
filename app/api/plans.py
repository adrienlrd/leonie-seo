"""Plan definitions and feature resolution for Free/Pro/Agency pricing tiers."""

from __future__ import annotations

from dataclasses import asdict, dataclass

from app.billing.self_hosted_license import LicenseError, require_valid_license


@dataclass(frozen=True)
class PlanFeatures:
    """Feature flags and limits for a pricing plan."""

    max_shops: int | None  # None = unlimited
    can_apply: bool  # push meta/alt changes to Shopify
    can_report: bool  # generate Markdown reports
    can_hreflang: bool  # hreflang generation
    can_alerts: bool  # email alert pipeline


_PLANS: dict[str, PlanFeatures] = {
    # Free can apply manually; automation and reporting are the paid features.
    "free": PlanFeatures(
        max_shops=1,
        can_apply=True,
        can_report=False,
        can_hreflang=False,
        can_alerts=False,
    ),
    "pro": PlanFeatures(
        max_shops=1,
        can_apply=True,
        can_report=True,
        can_hreflang=True,
        can_alerts=True,
    ),
    "agency": PlanFeatures(
        max_shops=None,
        can_apply=True,
        can_report=True,
        can_hreflang=True,
        can_alerts=True,
    ),
}

_VALID_PLANS = frozenset(_PLANS)


def get_features(plan: str) -> PlanFeatures:
    """Return the feature set for a plan name. Falls back to free for unknowns."""
    return _PLANS.get(plan, _PLANS["free"])


def get_active_plan() -> str:
    """Resolve the active plan from LEONIE_API_KEY in the environment.

    Returns:
        "free"   — key present but plan is free, or key is invalid/expired.
        "pro"    — no key configured (personal/owner use), or key with plan=pro.
        "agency" — key with plan=agency.
    """
    try:
        payload = require_valid_license()
    except LicenseError:
        return "free"

    if payload is None:
        # No key configured → personal use, full Pro access.
        return "pro"

    plan = payload.get("plan", "pro")
    return plan if plan in _VALID_PLANS else "pro"


def plan_summary(plan: str) -> dict:
    """Serialisable dict of plan name + feature flags — for API responses."""
    features = get_features(plan)
    return {"plan": plan, **asdict(features)}
