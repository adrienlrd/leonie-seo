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


def diagnose_cycle_outcome(
    *,
    learning_enabled: bool,
    continuous_result: dict[str, Any] | None,
    cycle_errors: list[dict[str, Any]],
) -> dict[str, Any]:
    """Explain, in plain language, why a cycle produced (or not) proposals.

    Makes the "0 proposals" case understandable instead of silent: covers
    learning disabled, missing market analysis, nothing eligible to optimize,
    and per-candidate generation failures.
    """
    if not learning_enabled:
        return {
            "reason": "learning_disabled",
            "proposals": 0,
            "fr": "L'agent learning est désactivé dans les réglages : aucun cycle d'amélioration "
            "n'a été exécuté. Activez le learning (ou l'agent quotidien) pour générer des "
            "propositions.",
            "en": "The learning agent is disabled in settings: no improvement cycle ran. Enable "
            "learning (or the daily agent) to generate proposals.",
        }

    for error in cycle_errors:
        message = str(error.get("error") or "")
        if error.get("stage") == "continuous_agent" and "market analysis" in message.lower():
            return {
                "reason": "no_market_analysis",
                "proposals": 0,
                "fr": "Aucune analyse de marché n'est disponible. Lancez d'abord une Analyse "
                "marché : l'agent s'appuie dessus pour proposer des optimisations.",
                "en": "No market analysis is available. Run a Market analysis first: the agent "
                "relies on it to propose optimizations.",
            }

    if continuous_result is None:
        return {
            "reason": "agent_not_run",
            "proposals": 0,
            "fr": "L'agent d'amélioration n'a pas pu s'exécuter. Consultez les erreurs du cycle.",
            "en": "The improvement agent could not run. Check the cycle errors.",
        }

    summary = continuous_result.get("summary") or {}
    proposals = int(summary.get("proposals_created") or 0)
    if proposals > 0:
        return {
            "reason": "ok",
            "proposals": proposals,
            "fr": f"{proposals} proposition(s) générée(s).",
            "en": f"{proposals} proposal(s) generated.",
        }
    if int(summary.get("products_seen") or 0) == 0:
        return {
            "reason": "no_products",
            "proposals": 0,
            "fr": "Aucun produit exploitable dans l'analyse de marché. Régénérez l'analyse pour "
            "obtenir des produits avec tags et éléments à améliorer.",
            "en": "No usable products in the market analysis. Re-run the analysis to get products "
            "with tags and improvement elements.",
        }
    if int(summary.get("candidate_actions") or 0) == 0:
        return {
            "reason": "no_candidates",
            "proposals": 0,
            "fr": "Aucune action candidate : tous les éléments éligibles (meta-titre, "
            "meta-description, description) semblent déjà optimisés et aucun tag négatif ne "
            "justifie une réécriture. Relancez une Analyse marché pour détecter de nouvelles "
            "opportunités.",
            "en": "No candidate action: all eligible elements (meta title, meta description, "
            "description) already look optimized and no negative tag warrants a rewrite. Re-run a "
            "Market analysis to surface new opportunities.",
        }
    if continuous_result.get("errors"):
        return {
            "reason": "all_candidates_failed",
            "proposals": 0,
            "fr": "Des candidats existaient mais toutes les générations ont échoué. Consultez les "
            "erreurs détaillées (clé LLM, faits manquants, quotas).",
            "en": "Candidates existed but every generation failed. Check the detailed errors "
            "(LLM key, missing facts, quotas).",
        }
    return {
        "reason": "no_proposals",
        "proposals": 0,
        "fr": "Aucune proposition générée pour ce cycle.",
        "en": "No proposal was generated for this cycle.",
    }


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
    learning_enabled = True
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
        learning_enabled = settings.enabled
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
                auto_publish_scopes=settings.auto_publish_scopes,
            )
            summary = continuous_result.get("summary") or {}
            actions_reprioritized = int(summary.get("candidate_actions") or 0)
            approvals_created = int(summary.get("learning_approvals_created") or 0)
            auto_applied_count = int(summary.get("applied") or 0)
    except Exception as exc:
        status = "completed_with_errors"
        errors.append({"stage": "continuous_agent", "error": str(exc)})

    diagnostics = diagnose_cycle_outcome(
        learning_enabled=learning_enabled,
        continuous_result=continuous_result,
        cycle_errors=errors,
    )

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
        "diagnostics": diagnostics,
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
