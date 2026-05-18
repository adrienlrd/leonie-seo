"""Impact confidence scoring for GEO optimization events (task 121).

Scores each optimization event 0-100 based on: time elapsed since application,
impression volume, score delta, GSC change, observed revenue, and context
stability. Never interprets the score as causal proof — it is a readability aid
that helps merchants avoid drawing conclusions too early.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.geo.validation_timeline import _applied_at, _baseline_impressions

_LABEL_THRESHOLDS = [
    (75, "impact_fort"),
    (50, "impact_probable"),
    (25, "signal_faible"),
    (0, "données_insuffisantes"),
]


def _label(score: int) -> str:
    for threshold, name in _LABEL_THRESHOLDS:
        if score >= threshold:
            return name
    return "données_insuffisantes"


def _coerce_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _coerce_int(value: Any) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def _elapsed_score(elapsed_days: int) -> int:
    if elapsed_days >= 90:
        return 40
    if elapsed_days >= 60:
        return 30
    if elapsed_days >= 30:
        return 20
    if elapsed_days >= 7:
        return 10
    return 0


def _volume_score(impressions: int) -> int:
    if impressions >= 2000:
        return 20
    if impressions >= 1000:
        return 15
    if impressions >= 500:
        return 10
    if impressions >= 100:
        return 5
    return 0


def _delta_score(score_before: int | None, score_after: int | None) -> tuple[int, list[str]]:
    if score_before is None or score_after is None:
        return 0, []
    delta = score_after - score_before
    if delta > 0:
        return 15, [f"Score GEO amélioré de {delta} pt(s)"]
    return 0, []


def _gsc_score(
    metrics_before: dict[str, Any] | None,
    metrics_after: dict[str, Any] | None,
) -> tuple[int, list[str]]:
    if not metrics_after:
        return 0, []
    before_gsc = (metrics_before or {}).get("gsc") or {}
    after_gsc = metrics_after.get("gsc") or {}
    imp_before = _coerce_int(before_gsc.get("impressions"))
    imp_after = _coerce_int(after_gsc.get("impressions"))
    if imp_after > imp_before:
        return 10, [f"Impressions GSC : {imp_before} → {imp_after}"]
    return 0, []


def _revenue_score(observed_impact: dict[str, Any] | None) -> tuple[int, list[str]]:
    if not observed_impact:
        return 0, []
    revenue = _coerce_float(observed_impact.get("revenue") or 0)
    if revenue > 0:
        return 10, [f"Revenu organique observé : {revenue:.2f} €"]
    return 0, []


def _stability_score(
    before_snapshot: dict[str, Any] | None,
    after_snapshot: dict[str, Any] | None,
) -> tuple[int, list[str]]:
    """5 pts if stock stable (≥0) and price unchanged across before/after snapshots."""
    before_comm = (before_snapshot or {}).get("commerce") or {}
    after_comm = (after_snapshot or {}).get("commerce") or {}

    inv_before = before_comm.get("inventory_quantity")
    inv_after = after_comm.get("inventory_quantity")
    price_before = str(before_comm.get("price") or "")
    price_after = str(after_comm.get("price") or "")

    oos = False
    for inv in (inv_before, inv_after):
        if inv is not None and _coerce_int(inv) <= 0:
            oos = True

    price_changed = (
        price_before
        and price_after
        and price_before not in ("None", "")
        and price_after not in ("None", "")
        and price_before != price_after
    )

    if not oos and not price_changed:
        return 5, ["Contexte stable (stock et prix)"]

    notes = []
    if oos:
        notes.append("Rupture de stock détectée sur la période")
    if price_changed:
        notes.append(f"Changement de prix : {price_before} → {price_after}")
    return 0, notes


def compute_event_confidence(
    event: dict[str, Any],
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Compute a 0-100 confidence score for one GEO optimization event.

    Args:
        event: Row from ``list_geo_events`` (dict with score_before, score_after,
            metrics_before, metrics_after, observed_impact, status, etc.).
        now: Reference time for elapsed-day calculation (testability).

    Returns:
        Dict with score, label, factors breakdown, and human-readable notes.
    """
    reference = now or datetime.now(UTC)
    if reference.tzinfo is None:
        reference = reference.replace(tzinfo=UTC)

    event_id = event.get("id")

    # Hard stop for rolled-back events
    if str(event.get("status") or "").lower() == "rolled_back":
        return {
            "event_id": event_id,
            "score": 0,
            "label": "données_insuffisantes",
            "factors": {
                "elapsed_days": 0,
                "elapsed_score": 0,
                "volume_score": 0,
                "delta_score": 0,
                "gsc_score": 0,
                "revenue_score": 0,
                "stability_score": 0,
            },
            "notes": ["Optimisation annulée (rolled_back) — score non calculé"],
        }

    applied = _applied_at(event)
    if applied is None:
        return {
            "event_id": event_id,
            "score": 0,
            "label": "données_insuffisantes",
            "factors": {
                "elapsed_days": 0,
                "elapsed_score": 0,
                "volume_score": 0,
                "delta_score": 0,
                "gsc_score": 0,
                "revenue_score": 0,
                "stability_score": 0,
            },
            "notes": ["Date d'application introuvable"],
        }

    elapsed_days = (reference - applied).days
    e_score = _elapsed_score(elapsed_days)

    impressions = _baseline_impressions(event)
    v_score = _volume_score(impressions)

    d_score, d_notes = _delta_score(event.get("score_before"), event.get("score_after"))

    before_metrics = event.get("metrics_before") or {}
    after_metrics = event.get("metrics_after")
    g_score, g_notes = _gsc_score(before_metrics, after_metrics)

    r_score, r_notes = _revenue_score(event.get("observed_impact"))

    before_snap = (event.get("before_snapshot") or {})
    after_snap = (event.get("after_snapshot") or {})
    s_score, s_notes = _stability_score(before_snap, after_snap)

    total = min(100, e_score + v_score + d_score + g_score + r_score + s_score)
    notes: list[str] = []
    if elapsed_days < 7:
        notes.append(f"Seulement {elapsed_days} jour(s) écoulé(s) — trop tôt pour conclure")
    elif elapsed_days < 30:
        notes.append(f"{elapsed_days} jours écoulés — signal directionnel, pas une conclusion")
    notes.extend(d_notes + g_notes + r_notes + s_notes)

    return {
        "event_id": event_id,
        "score": total,
        "label": _label(total),
        "factors": {
            "elapsed_days": elapsed_days,
            "elapsed_score": e_score,
            "volume_score": v_score,
            "delta_score": d_score,
            "gsc_score": g_score,
            "revenue_score": r_score,
            "stability_score": s_score,
        },
        "notes": notes,
    }


def compute_catalog_confidence(
    events: list[dict[str, Any]],
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Compute confidence scores for all events and return scores + summary.

    Args:
        events: List of event dicts from ``list_geo_events``.
        now: Reference time (testability).

    Returns:
        Dict with list of per-event scores and aggregate summary.
    """
    scores = [compute_event_confidence(event, now=now) for event in events]
    by_label: dict[str, int] = {
        "données_insuffisantes": 0,
        "signal_faible": 0,
        "impact_probable": 0,
        "impact_fort": 0,
    }
    total_score = 0
    for entry in scores:
        lbl = entry["label"]
        by_label[lbl] = by_label.get(lbl, 0) + 1
        total_score += entry["score"]

    avg_score = round(total_score / len(scores), 1) if scores else 0.0

    return {
        "scores": scores,
        "summary": {
            "total_events": len(scores),
            "by_label": by_label,
            "avg_score": avg_score,
        },
    }
