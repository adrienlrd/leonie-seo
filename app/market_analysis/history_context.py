"""Optimization history context for the market analysis engine (Task 6).

Surfaces past applied optimizations (per product, from the GEO impact ledger)
and shop-level "what worked / what regressed" learning signals, so the
analysis prompts can avoid re-proposing values already measured positive and
revise or drop changes that regressed.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.geo.confidence import compute_event_confidence
from app.geo.impact_report import build_event_report
from app.geo.ledger import list_geo_events
from app.learning.store import list_weights

_DEFAULT_MAX_EVENTS = 5
_DEFAULT_MAX_WEIGHTS = 3


def _event_history_entry(event: dict[str, Any]) -> dict[str, Any]:
    """Build one history entry from a `list_geo_events` row.

    Events recorded by `record_applied_change` carry `before_snapshot.content[field]`
    and `after_snapshot.value`, so old/new text is shown. Events applied via the
    continuous-improvement agent / approval flow only carry `after_snapshot.field`
    (no old/new text) — those entries still surface field/verdict/confidence so the
    LLM knows that field was already changed and measured.
    """
    confidence = compute_event_confidence(event)
    report = build_event_report(event, confidence)
    after_snapshot = event.get("after_snapshot") or {}
    before_snapshot = event.get("before_snapshot") or {}
    field = after_snapshot.get("field")
    old_value = (before_snapshot.get("content") or {}).get(field) if field else None
    return {
        "field": field,
        "old_value": old_value,
        "new_value": after_snapshot.get("value"),
        "applied_at": report["applied_at"],
        "verdict": report["verdict"],
        "confidence": report["confidence"]["score"],
    }


def _shop_summary(shop: str, *, db_path: Path | None) -> str:
    """Return a short FR summary of which action types worked or regressed shop-wide."""
    weights = list_weights(shop, db_path=db_path)
    action_weights = [
        w
        for w in weights
        if w.get("feature_key") == "action_type" and int(w.get("sample_size") or 0) > 0
    ]
    if not action_weights:
        return ""

    positives = sorted(
        (w for w in action_weights if float(w.get("weight") or 0) > 0),
        key=lambda w: float(w.get("weight") or 0),
        reverse=True,
    )[:_DEFAULT_MAX_WEIGHTS]
    negatives = sorted(
        (w for w in action_weights if float(w.get("weight") or 0) < 0),
        key=lambda w: float(w.get("weight") or 0),
    )[:_DEFAULT_MAX_WEIGHTS]

    parts: list[str] = []
    if positives:
        parts.append(
            "Actions ayant historiquement bien fonctionné sur cette boutique : "
            + ", ".join(str(w["feature_value"]) for w in positives)
            + "."
        )
    if negatives:
        parts.append(
            "Actions ayant historiquement régressé sur cette boutique : "
            + ", ".join(str(w["feature_value"]) for w in negatives)
            + "."
        )
    return " ".join(parts)


def build_optimization_history(
    shop: str,
    product_id: str,
    *,
    db_path: Path | None = None,
    max_events: int = _DEFAULT_MAX_EVENTS,
) -> dict[str, Any]:
    """Build a compact optimization-history context for one product.

    Returns a dict with:
      - ``events``: up to ``max_events`` most recent applied optimizations for
        this product, each ``{field, old_value, new_value, applied_at, verdict, confidence}``.
      - ``older_count``: number of additional applied events beyond ``max_events``.
      - ``shop_summary``: short FR text on which action types worked/regressed shop-wide.
    """
    data = list_geo_events(shop, limit=500, status="applied", db_path=db_path)
    product_events = [e for e in data["events"] if e.get("resource_id") == product_id]
    recent = product_events[:max_events]
    older_count = max(0, len(product_events) - len(recent))

    return {
        "events": [_event_history_entry(event) for event in recent],
        "older_count": older_count,
        "shop_summary": _shop_summary(shop, db_path=db_path),
    }


def format_optimization_history(history: dict[str, Any]) -> str:
    """Render ``build_optimization_history``'s output as a prompt block.

    Returns an empty string when there is nothing to show (no past applied
    optimizations and no shop-level summary), so callers can omit the section
    entirely for products/shops with no history.
    """
    events = history.get("events") or []
    older_count = int(history.get("older_count") or 0)
    shop_summary = str(history.get("shop_summary") or "")

    if not events and not shop_summary:
        return ""

    lines = ["\n=== HISTORIQUE D'OPTIMISATION (changements déjà appliqués) ==="]
    for event in events:
        field = event.get("field") or "?"
        old_value = event.get("old_value")
        new_value = event.get("new_value")
        applied_at = (event.get("applied_at") or "")[:10]
        verdict = event.get("verdict") or "inconclusif"
        confidence = event.get("confidence", 0)
        if old_value is not None or new_value is not None:
            value_text = ""
            if old_value is not None:
                value_text += f'"{old_value}" → '
            if new_value is not None:
                value_text += f'"{new_value}"'
            line = f"  - [{applied_at}] {field}: {value_text}"
        else:
            line = f"  - [{applied_at}] {field}"
        line += f" — verdict: {verdict} (confiance {confidence}/100)"
        lines.append(line)
    if older_count:
        lines.append(f"  - … et {older_count} changement(s) appliqué(s) plus ancien(s).")
    if shop_summary:
        lines.append(f"  {shop_summary}")
    lines.append(
        "RÈGLE HISTORIQUE : ne re-propose PAS une valeur déjà mesurée 'positif_probable' ou "
        "'neutre' pour le même champ — garde-la ou affine-la légèrement. Pour un changement "
        "marqué 'négatif_possible', révise ou annule cette proposition (reviens vers une "
        "formulation proche de l'ancienne valeur ou propose une approche différente). "
        "Réfère-toi explicitement à ces changements passés si pertinent."
    )
    return "\n".join(lines)
