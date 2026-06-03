"""Learning cycle scheduler and Render Cron entrypoint logic."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.geo.ledger import list_geo_events
from app.learning.features import features_for_observation
from app.learning.learner import update_weights_from_observation
from app.learning.models import LEARNING_WINDOWS_DAYS, LearningMode, LearningObservation
from app.learning.outcomes import build_observation_from_event, event_age_days
from app.learning.store import (
    create_observation,
    get_settings,
    list_observations,
    observation_exists,
    record_run,
)
from app.market_analysis.jobs import load_latest_result
from app.oauth.token_store import get_token, list_tokens


def _product_by_id(shop: str) -> dict[str, dict[str, Any]]:
    latest = load_latest_result(shop) or {}
    return {
        str(product.get("product_id") or ""): product
        for product in latest.get("products") or []
        if isinstance(product, dict)
    }


def _event_mode(event: dict[str, Any]) -> str:
    notes = str(event.get("notes") or "")
    if "auto_apply" in notes:
        return LearningMode.AUTO_APPLY.value
    return LearningMode.SEMI_AUTO.value


def _eligible_events(events: list[dict[str, Any]], *, now: datetime) -> list[dict[str, Any]]:
    eligible = []
    for event in events:
        if str(event.get("resource_id") or "") == "":
            continue
        if str(event.get("status") or "") not in {"applied", "measured", "rolled_back", "planned"}:
            continue
        if not (
            event.get("metrics_after")
            or event.get("observed_impact")
            or event.get("score_after") is not None
        ):
            continue
        age = event_age_days(event, now=now)
        if age is None or age < min(LEARNING_WINDOWS_DAYS):
            continue
        eligible.append(event)
    return eligible


def create_due_observations(
    shop: str,
    *,
    now: datetime | None = None,
    db_path: Path | None = None,
) -> tuple[list[LearningObservation], int]:
    """Create observations for mature ledger events and return typed entries."""
    current = now or datetime.now(UTC)
    events = list_geo_events(shop, limit=500, db_path=db_path)["events"]
    products = _product_by_id(shop)
    created: list[LearningObservation] = []
    skipped = 0
    for event in _eligible_events(events, now=current):
        age = event_age_days(event, now=current) or 0
        for window_days in LEARNING_WINDOWS_DAYS:
            if age < window_days:
                continue
            window_label = f"J+{window_days}"
            exists = observation_exists(
                shop=shop,
                resource_id=str(event.get("resource_id") or ""),
                action_type=str(event.get("action_type") or ""),
                window_label=window_label,
                db_path=db_path,
            )
            if exists:
                skipped += 1
                continue
            payload = build_observation_from_event(event, window_days=window_days)
            observation_id = create_observation(shop=shop, db_path=db_path, **payload)
            product = products.get(payload["resource_id"])
            obs = LearningObservation(
                shop=shop,
                resource_type=payload["resource_type"],
                resource_id=payload["resource_id"],
                action_type=payload["action_type"],
                surface=payload["surface"],
                keyword_source=payload["keyword_source"],
                before_metrics=payload["before_metrics"],
                after_metrics=payload["after_metrics"],
                control_metrics=payload["control_metrics"],
                window_days=payload["window_days"],
                window_label=payload["window_label"],
                is_primary_window=payload["is_primary_window"],
                outcome_score=payload["outcome_score"],
                confidence_score=payload["confidence_score"],
                features=[],
            )
            obs = LearningObservation(
                **{
                    **obs.__dict__,
                    "features": features_for_observation(
                        obs,
                        product=product,
                        risk_level="low",
                        application_mode=_event_mode(event),
                    ),
                }
            )
            created.append(obs)
            if observation_id <= 0:
                skipped += 1
    return created, skipped


def run_learning_cycle(
    shop: str,
    *,
    access_token: str | None = None,
    plan: str = "free",
    confirm_live_write: bool = False,
    max_actions: int = 5,
    db_path: Path | None = None,
) -> dict[str, Any]:
    """Run one complete learning cycle for a shop.

    Learning errors are reported in the run but do not raise by default.
    """
    observations_created = 0
    weights_updated = 0
    actions_reprioritized = 0
    approvals_created = 0
    auto_applied_count = 0
    errors: list[dict[str, Any]] = []
    continuous_result: dict[str, Any] | None = None
    status = "completed"
    try:
        observations, _skipped = create_due_observations(shop, db_path=db_path)
        observations_created = len(observations)
        for observation in observations:
            weights_updated += update_weights_from_observation(observation, db_path=db_path)
    except Exception as exc:
        status = "completed_with_errors"
        errors.append({"stage": "observations", "error": str(exc)})

    try:
        settings = get_settings(shop, db_path=db_path)
        token = access_token
        if token is None:
            record = get_token(shop, db_path=db_path)
            token = str(record.get("access_token") or "") if record else None
        if settings.enabled:
            from app.geo.continuous_agent import run_continuous_improvement_agent

            continuous_result = run_continuous_improvement_agent(
                shop,
                access_token=token,
                plan=plan,
                auto_apply=settings.mode == LearningMode.AUTO_APPLY,
                confirm_live_write=confirm_live_write,
                max_actions=max_actions,
                db_path=db_path,
            )
            summary = continuous_result.get("summary") or {}
            actions_reprioritized = int(summary.get("candidate_actions") or 0)
            approvals_created = int(summary.get("learning_approvals_created") or 0)
            auto_applied_count = int(summary.get("applied") or 0)
    except Exception as exc:
        status = "completed_with_errors"
        errors.append({"stage": "continuous_agent", "error": str(exc)})

    run_id = record_run(
        shop=shop,
        status=status,
        observations_created=observations_created,
        weights_updated=weights_updated,
        actions_reprioritized=actions_reprioritized,
        approvals_created=approvals_created,
        auto_applied_count=auto_applied_count,
        errors=errors,
        db_path=db_path,
    )
    return {
        "run_id": run_id,
        "shop": shop,
        "status": status,
        "observations_created": observations_created,
        "weights_updated": weights_updated,
        "actions_reprioritized": actions_reprioritized,
        "approvals_created": approvals_created,
        "auto_applied_count": auto_applied_count,
        "errors": errors,
        "continuous_agent": continuous_result,
    }


def run_all_installed_shops(*, db_path: Path | None = None) -> dict[str, Any]:
    """Run learning for every installed shop known to the backend."""
    runs = []
    for token_row in list_tokens(db_path=db_path):
        shop = str(token_row.get("shop") or "")
        if not shop:
            continue
        runs.append(run_learning_cycle(shop, db_path=db_path))
    return {"shops_seen": len(runs), "runs": runs}


def status_snapshot(shop: str, *, db_path: Path | None = None) -> dict[str, Any]:
    """Return a compact learning status for the UI."""
    from app.learning.store import list_decisions, list_pending_approvals, list_runs, list_weights

    settings = get_settings(shop, db_path=db_path)
    observations = list_observations(shop, limit=500, db_path=db_path)
    weights = list_weights(shop, limit=50, db_path=db_path)
    decisions = list_decisions(shop, limit=20, db_path=db_path)
    approvals = list_pending_approvals(shop, include_closed=False, limit=100, db_path=db_path)
    runs = list_runs(shop, limit=5, db_path=db_path)
    return {
        "settings": settings.__dict__ | {"mode": settings.mode.value},
        "last_run": runs[0] if runs else None,
        "observation_count": len(observations),
        "pending_approval_count": len(approvals),
        "weights_up": [w for w in weights if float(w.get("weight") or 0) > 0][:8],
        "weights_down": [w for w in weights if float(w.get("weight") or 0) < 0][:8],
        "top_actions": [
            w
            for w in weights
            if w.get("feature_key") == "action_type" and float(w.get("weight") or 0) > 0
        ][:8],
        "recent_decisions": decisions,
        "recent_runs": runs,
    }
