"""Learning cycle scheduler and Render Cron entrypoint logic."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.geo.ledger import list_geo_events
from app.learning.control_group import build_control_metrics_for_event
from app.learning.features import features_for_observation
from app.learning.learner import update_weights_from_observation
from app.learning.models import LEARNING_WINDOWS_DAYS, LearningMode, LearningObservation
from app.learning.outcomes import build_observation_from_event, event_age_days, event_applied_at
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
    status_history = (
        event.get("status_history") if isinstance(event.get("status_history"), list) else []
    )
    history_notes = " ".join(str(item.get("note") or "") for item in status_history)
    if (
        "auto_apply" in notes
        or "automatically" in notes.lower()
        or "automatically" in history_notes.lower()
    ):
        return LearningMode.AUTO_APPLY.value
    return LearningMode.SEMI_AUTO.value


def _control_metrics_from_event(event: dict[str, Any]) -> dict[str, Any]:
    for key in ("estimated_impact", "after_snapshot", "before_snapshot"):
        container = event.get(key)
        if not isinstance(container, dict):
            continue
        metrics = container.get("control_metrics")
        if isinstance(metrics, dict) and metrics:
            return metrics
    return {}


def _manual_pollution_flags(event: dict[str, Any]) -> list[str]:
    flags: list[str] = []
    for key in ("estimated_impact", "after_snapshot", "before_snapshot"):
        container = event.get(key)
        if not isinstance(container, dict):
            continue
        raw = container.get("pollution_flags")
        if isinstance(raw, list):
            flags.extend(str(item) for item in raw if item)
    return flags


def _pollution_flags(
    event: dict[str, Any],
    events: list[dict[str, Any]],
    *,
    window_days: int,
) -> list[str]:
    flags = set(_manual_pollution_flags(event))
    if str(event.get("status") or "") == "rolled_back":
        flags.add("rolled_back")
    applied_at = event_applied_at(event)
    if applied_at is None:
        return sorted(flags)

    event_id = event.get("id")
    resource_id = str(event.get("resource_id") or "")
    overlapping = 0
    for other in events:
        if other.get("id") == event_id:
            continue
        if str(other.get("resource_id") or "") != resource_id:
            continue
        other_applied_at = event_applied_at(other)
        if other_applied_at is None:
            continue
        delta_days = (other_applied_at - applied_at).days
        if 0 <= delta_days <= window_days:
            overlapping += 1
    if overlapping:
        flags.add("overlapping_same_resource_actions")
    return sorted(flags)


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
                ledger_event_id=int(event["id"]) if event.get("id") is not None else None,
                db_path=db_path,
            )
            if exists:
                skipped += 1
                continue
            control_metrics = _control_metrics_from_event(event) or build_control_metrics_for_event(
                shop=shop,
                event=event,
                products=products,
                events=events,
                window_days=window_days,
                db_path=db_path,
            )
            payload = build_observation_from_event(
                event,
                window_days=window_days,
                control_metrics=control_metrics,
                pollution_flags=_pollution_flags(event, events, window_days=window_days),
            )
            observation_payload = {key: value for key, value in payload.items() if key != "deltas"}
            observation_id = create_observation(shop=shop, db_path=db_path, **observation_payload)
            product = products.get(payload["resource_id"])
            obs = LearningObservation(
                shop=shop,
                ledger_event_id=payload["ledger_event_id"],
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
                metadata=payload["metadata"],
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
