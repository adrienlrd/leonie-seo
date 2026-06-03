"""Observed outcome calculations for SEO/GEO optimizations."""

from __future__ import annotations

import math
from datetime import UTC, datetime
from typing import Any

from app.learning.models import PRIMARY_WINDOW_DAYS


def _num(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _metric(metrics: dict[str, Any], key: str) -> float:
    if key in metrics:
        return _num(metrics.get(key))
    gsc = metrics.get("gsc") if isinstance(metrics.get("gsc"), dict) else {}
    ga4 = metrics.get("ga4") if isinstance(metrics.get("ga4"), dict) else {}
    if key in gsc:
        return _num(gsc.get(key))
    if key in ga4:
        return _num(ga4.get(key))
    return 0.0


def _relative_delta(before: float, after: float) -> float:
    if before <= 0:
        return min(after / 50.0, 1.0) if after > 0 else 0.0
    return max(-1.0, min(1.0, (after - before) / max(before, 1.0)))


def _has(metrics: dict[str, Any], group: str) -> bool:
    return isinstance(metrics.get(group), dict) and bool(metrics[group])


def _trend_signals(deltas: dict[str, float]) -> list[float]:
    signals = [
        deltas["impressions"],
        deltas["clicks"],
        deltas["ctr"] * 2,
        deltas["position"],
        deltas["conversions"],
        deltas["revenue"],
        deltas["score"],
    ]
    return [signal for signal in signals if abs(signal) > 0.01]


def calculate_outcome(
    *,
    before_metrics: dict[str, Any],
    after_metrics: dict[str, Any],
    control_metrics: dict[str, Any] | None = None,
    score_before: int | None = None,
    score_after: int | None = None,
) -> dict[str, Any]:
    """Return deltas and an outcome score between -100 and +100."""
    imp_b = _metric(before_metrics, "impressions")
    imp_a = _metric(after_metrics, "impressions")
    clk_b = _metric(before_metrics, "clicks")
    clk_a = _metric(after_metrics, "clicks")
    ctr_b = _metric(before_metrics, "ctr")
    ctr_a = _metric(after_metrics, "ctr")
    pos_b = _metric(before_metrics, "position")
    pos_a = _metric(after_metrics, "position")
    conv_b = _metric(before_metrics, "conversions")
    conv_a = _metric(after_metrics, "conversions")
    rev_b = _metric(before_metrics, "revenue")
    rev_a = _metric(after_metrics, "revenue")

    deltas = {
        "impressions": _relative_delta(imp_b, imp_a),
        "clicks": _relative_delta(clk_b, clk_a),
        "ctr": max(-1.0, min(1.0, ctr_a - ctr_b)),
        "position": max(-1.0, min(1.0, (pos_b - pos_a) / 10.0)) if pos_b or pos_a else 0.0,
        "conversions": _relative_delta(conv_b, conv_a),
        "revenue": _relative_delta(rev_b, rev_a),
        "score": (
            max(-1.0, min(1.0, ((score_after or 0) - (score_before or 0)) / 30.0))
            if score_before is not None and score_after is not None
            else 0.0
        ),
    }

    weighted = (
        0.23 * deltas["impressions"]
        + 0.23 * deltas["clicks"]
        + 0.12 * deltas["ctr"]
        + 0.12 * deltas["position"]
        + 0.12 * deltas["conversions"]
        + 0.10 * deltas["revenue"]
        + 0.08 * deltas["score"]
    )

    control = control_metrics or {}
    control_uplift = 0.0
    if control:
        control_delta = _relative_delta(
            _metric(control, "impressions_before"),
            _metric(control, "impressions_after"),
        )
        control_uplift = deltas["impressions"] - control_delta
        weighted = 0.8 * weighted + 0.2 * max(-1.0, min(1.0, control_uplift))

    outcome_score = max(-100.0, min(100.0, weighted * 100.0))
    return {
        "outcome_score": round(outcome_score, 2),
        "deltas": deltas,
        "control_uplift": round(control_uplift, 4),
    }


def calculate_confidence(
    *,
    before_metrics: dict[str, Any],
    after_metrics: dict[str, Any],
    control_metrics: dict[str, Any] | None,
    window_days: int,
    outcome_deltas: dict[str, float],
) -> int:
    """Return a confidence score between 0 and 100."""
    impressions = max(_metric(before_metrics, "impressions"), _metric(after_metrics, "impressions"))
    volume_score = min(30.0, math.sqrt(max(impressions, 0.0)) / math.sqrt(500.0) * 30.0)
    score = volume_score
    if _has(before_metrics, "gsc") or _metric(before_metrics, "impressions") > 0:
        score += 18
    if _has(before_metrics, "ga4") or _metric(before_metrics, "conversions") > 0:
        score += 12
    if control_metrics:
        score += 12
    score += 12 if window_days >= PRIMARY_WINDOW_DAYS else 6

    signals = _trend_signals(outcome_deltas)
    if signals:
        positives = sum(1 for signal in signals if signal > 0)
        negatives = sum(1 for signal in signals if signal < 0)
        consistency = abs(positives - negatives) / max(len(signals), 1)
        score += 16 * consistency
        if positives and negatives:
            score -= 10

    if impressions < 25:
        score = min(score, 35)
    elif impressions < 50:
        score = min(score, 45)
    if window_days == 14:
        score = min(score, 75)
    return max(0, min(100, round(score)))


def build_observation_from_event(
    event: dict[str, Any],
    *,
    window_days: int,
    control_metrics: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a serializable learning observation payload from a ledger event."""
    before = event.get("metrics_before") or {}
    after = event.get("metrics_after") or {}
    if not after and event.get("observed_impact"):
        after = {"observed": event.get("observed_impact") or {}}
    outcome = calculate_outcome(
        before_metrics=before,
        after_metrics=after,
        control_metrics=control_metrics,
        score_before=event.get("score_before"),
        score_after=event.get("score_after"),
    )
    confidence = calculate_confidence(
        before_metrics=before,
        after_metrics=after,
        control_metrics=control_metrics,
        window_days=window_days,
        outcome_deltas=outcome["deltas"],
    )
    return {
        "resource_type": str(event.get("resource_type") or "product"),
        "resource_id": str(event.get("resource_id") or ""),
        "action_type": str(event.get("action_type") or "unknown"),
        "surface": "product_page"
        if event.get("resource_type") == "product"
        else str(event.get("resource_type") or "cms"),
        "keyword_source": str(
            (event.get("estimated_impact") or {}).get("keyword_source") or "unknown"
        ),
        "before_metrics": before,
        "after_metrics": after,
        "control_metrics": control_metrics or {},
        "window_days": window_days,
        "window_label": f"J+{window_days}",
        "is_primary_window": window_days == PRIMARY_WINDOW_DAYS,
        "outcome_score": outcome["outcome_score"],
        "confidence_score": confidence,
        "deltas": outcome["deltas"],
    }


def event_age_days(event: dict[str, Any], *, now: datetime | None = None) -> int | None:
    """Return event age in whole days from its applied or created date."""
    value = str(event.get("created_at") or "")
    for entry in event.get("status_history") or []:
        if str(entry.get("status") or "").lower() in {"applied", "measured"}:
            value = str(entry.get("changed_at") or value)
            break
    if not value:
        return None
    try:
        created = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if created.tzinfo is None:
        created = created.replace(tzinfo=UTC)
    return ((now or datetime.now(UTC)).astimezone(UTC) - created.astimezone(UTC)).days
