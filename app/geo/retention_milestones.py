"""Retention milestone tracker for GEO optimization validation (task 123).

Explains to the merchant why the app must remain active during the validation
window. Shows J+14 / J+28 / J+60 progress across all applied events.
No dark patterns: milestones are only surfaced when real optimizations exist.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from app.geo.validation_timeline import _applied_at

_MILESTONE_DAYS = [14, 28, 60]

_MILESTONE_MESSAGES = {
    14: {
        "fr": "Signal intermédiaire. Utile pour orienter, mais la confiance reste plafonnée.",
        "en": "Intermediate signal. Useful for direction, but confidence remains capped.",
    },
    28: {
        "fr": "Fenêtre principale de validation. Le moteur apprend surtout à partir de ce jalon.",
        "en": "Primary validation window. The engine mainly learns from this milestone.",
    },
    60: {
        "fr": "Historique long terme. Sert à confirmer ou nuancer les décisions déjà prises.",
        "en": "Long-term history. Used to confirm or nuance decisions already made.",
    },
}

_RETENTION_MESSAGE = {
    "fr": (
        "Vos optimisations GEO sont appliquées. Les moteurs de recherche et les IA "
        "ont besoin de temps pour recrawler et réévaluer vos pages. Gardez l'app active "
        "pour mesurer les résultats, éviter les pertes et recevoir les prochaines actions prioritaires."
    ),
    "en": (
        "Your GEO optimizations are applied. Search engines and AI models need time to "
        "recrawl and re-evaluate your pages. Keep the app active to measure results, "
        "avoid regressions, and receive your next priority actions."
    ),
}


def _days_label(days: int) -> str:
    return f"J+{days}"


def build_retention_milestones(
    events: list[dict[str, Any]],
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Compute retention milestone state from all applied GEO events.

    Args:
        events: List of event dicts from ``list_geo_events``.
        now: Reference time for elapsed-day calculation (testability).

    Returns:
        Dict with milestones list, active event count, retention message and
        next upcoming milestone date.
    """
    reference = now or datetime.now(UTC)
    if reference.tzinfo is None:
        reference = reference.replace(tzinfo=UTC)

    applied_dates: list[datetime] = []
    for event in events:
        applied = _applied_at(event)
        if applied is not None:
            applied_dates.append(applied)

    if not applied_dates:
        return {
            "has_active_events": False,
            "active_event_count": 0,
            "milestones": [],
            "next_milestone": None,
            "retention_message_fr": _RETENTION_MESSAGE["fr"],
            "retention_message_en": _RETENTION_MESSAGE["en"],
        }

    # Use the earliest applied date to track the overall validation age
    earliest = min(applied_dates)
    elapsed_days = (reference - earliest).days

    milestones = []
    next_milestone: dict[str, Any] | None = None

    for days in _MILESTONE_DAYS:
        due_date = earliest + timedelta(days=days)
        elapsed_at_due = days
        reached = elapsed_days >= elapsed_at_due
        # count how many events have reached this window
        events_reached = sum(1 for d in applied_dates if (reference - d).days >= days)

        status = "completed" if reached else ("active" if elapsed_days >= days - 7 else "upcoming")
        # active = within 7 days of the milestone date
        if not reached and (due_date - reference).days <= 7:
            status = "active"
        elif reached:
            status = "completed"
        else:
            status = "upcoming"

        entry: dict[str, Any] = {
            "label": _days_label(days),
            "days": days,
            "due_date": due_date.date().isoformat(),
            "status": status,
            "events_reached": events_reached,
            "total_events": len(applied_dates),
            "message_fr": _MILESTONE_MESSAGES[days]["fr"],
            "message_en": _MILESTONE_MESSAGES[days]["en"],
        }
        milestones.append(entry)

        if next_milestone is None and not reached:
            next_milestone = {
                "label": _days_label(days),
                "due_date": due_date.date().isoformat(),
                "days_remaining": max(0, (due_date.date() - reference.date()).days),
            }

    return {
        "has_active_events": True,
        "active_event_count": len(applied_dates),
        "earliest_applied_at": earliest.date().isoformat(),
        "elapsed_days": elapsed_days,
        "milestones": milestones,
        "next_milestone": next_milestone,
        "retention_message_fr": _RETENTION_MESSAGE["fr"],
        "retention_message_en": _RETENTION_MESSAGE["en"],
    }
