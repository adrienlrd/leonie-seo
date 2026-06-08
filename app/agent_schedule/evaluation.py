"""Effectiveness evaluation for the GEO agent.

Answers two merchant questions from data the agent already produces:

1. *Is the agent actually improving SEO and GEO?* — a clear per-dimension verdict
   (improving / no_effect / regressing / inconclusive) built from matured
   learning observations (J+14/J+28/J+60 before/after deltas).
2. *If not, how do I improve it?* — actionable, prioritised recommendations
   (e.g. proposals waiting for validation, window not matured yet, low
   measurement confidence, low content quality, regressions).

Read-only: it never mutates data and reuses existing outcome math
(``app.learning.outcomes``) so the verdict matches the learning engine.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.learning.models import PRIMARY_WINDOW_DAYS
from app.learning.outcomes import calculate_outcome
from app.learning.store import get_settings, list_observations, list_pending_approvals, list_runs

# Verdict thresholds. A dimension needs enough matured samples and a minimum
# measurement confidence before we commit to "improving" or "regressing".
_MIN_SAMPLE = 3
_MIN_CONFIDENCE = 35.0
_IMPROVE_THRESHOLD = 8.0  # on a -100..+100 scale
_LOW_QUALITY = 60


def _num(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _deltas_for(observation: dict[str, Any]) -> dict[str, float]:
    """Return per-metric deltas for one observation, recomputing if absent."""
    metadata = observation.get("metadata") if isinstance(observation.get("metadata"), dict) else {}
    deltas = metadata.get("outcome_deltas")
    if isinstance(deltas, dict) and deltas:
        return {key: _num(value) for key, value in deltas.items()}
    outcome = calculate_outcome(
        before_metrics=observation.get("before_metrics") or {},
        after_metrics=observation.get("after_metrics") or {},
        control_metrics=observation.get("control_metrics") or {},
    )
    return {key: _num(value) for key, value in outcome["deltas"].items()}


def _seo_delta(deltas: dict[str, float]) -> float:
    """SEO search-performance signal in -1..1 (impressions, clicks, ctr, rank)."""
    return (
        0.30 * deltas.get("impressions", 0.0)
        + 0.35 * deltas.get("clicks", 0.0)
        + 0.20 * deltas.get("ctr", 0.0)
        + 0.15 * deltas.get("position", 0.0)
    )


def _geo_delta(deltas: dict[str, float]) -> float:
    """GEO readiness signal in -1..1 (before/after GEO score)."""
    return deltas.get("score", 0.0)


def _weighted_average(pairs: list[tuple[float, float]]) -> float:
    """Confidence-weighted average of (value, weight); plain mean if no weight."""
    if not pairs:
        return 0.0
    total_weight = sum(weight for _value, weight in pairs)
    if total_weight <= 0:
        return sum(value for value, _weight in pairs) / len(pairs)
    return sum(value * weight for value, weight in pairs) / total_weight


def _dimension_verdict(score: float, sample: int, avg_confidence: float) -> str:
    if sample < _MIN_SAMPLE or avg_confidence < _MIN_CONFIDENCE:
        return "inconclusive"
    if score >= _IMPROVE_THRESHOLD:
        return "improving"
    if score <= -_IMPROVE_THRESHOLD:
        return "regressing"
    return "no_effect"


def _overall_verdict(seo: str, geo: str) -> str:
    verdicts = {seo, geo}
    if seo == "improving" and geo == "improving":
        return "improving"
    if "improving" in verdicts and "regressing" not in verdicts:
        return "partially_improving"
    if "regressing" in verdicts and "improving" not in verdicts:
        return "regressing"
    if verdicts == {"inconclusive"}:
        return "inconclusive"
    return "no_effect"


def _by_field(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Aggregate learnable observations per field to show what works."""
    buckets: dict[str, dict[str, Any]] = {}
    for row in rows:
        field = str(row["field"] or "unknown")
        bucket = buckets.setdefault(
            field, {"field": field, "sample": 0, "seo": [], "geo": [], "outcome": []}
        )
        bucket["sample"] += 1
        bucket["seo"].append((row["seo_delta"] * 100, row["confidence"]))
        bucket["geo"].append((row["geo_delta"] * 100, row["confidence"]))
        bucket["outcome"].append(row["outcome_score"])
    result = []
    for bucket in buckets.values():
        result.append(
            {
                "field": bucket["field"],
                "sample": bucket["sample"],
                "seo_score": round(_weighted_average(bucket["seo"]), 1),
                "geo_score": round(_weighted_average(bucket["geo"]), 1),
                "avg_outcome": round(sum(bucket["outcome"]) / len(bucket["outcome"]), 1),
            }
        )
    result.sort(key=lambda item: item["avg_outcome"], reverse=True)
    return result


def _rec(code: str, severity: str, fr: str, en: str) -> dict[str, str]:
    return {"code": code, "severity": severity, "fr": fr, "en": en}


def _build_recommendations(
    *,
    seo_verdict: str,
    geo_verdict: str,
    sample: int,
    avg_confidence: float,
    proposals_count: int,
    applied_count: int,
    pending_count: int,
    mode: str,
    avg_quality: float,
    positive_tags: int,
    negative_tags: int,
    has_any_run: bool,
) -> list[dict[str, str]]:
    recs: list[dict[str, str]] = []

    if not has_any_run:
        recs.append(
            _rec(
                "NO_RUNS",
                "info",
                "L'agent n'a encore jamais tourné. Activez l'agent quotidien ou lancez un "
                "test dans 5 minutes pour générer des propositions.",
                "The agent has never run yet. Enable the daily agent or run a 5-minute test "
                "to generate proposals.",
            )
        )
        return recs

    if proposals_count > 0 and applied_count == 0 and pending_count > 0 and mode == "semi_auto":
        recs.append(
            _rec(
                "PROPOSALS_AWAITING_VALIDATION",
                "critical",
                f"{pending_count} proposition(s) attendent votre validation. En semi-automatique, "
                "rien n'est appliqué tant que vous n'avez pas validé : approuvez les actions sûres "
                "pour que l'agent ait un effet mesurable.",
                f"{pending_count} proposal(s) are awaiting your validation. In semi-automatic mode "
                "nothing is applied until you approve: approve the safe actions so the agent can "
                "have a measurable effect.",
            )
        )

    if applied_count > 0 and sample == 0:
        recs.append(
            _rec(
                "WAIT_FOR_WINDOW",
                "info",
                "Des changements ont été appliqués récemment mais aucune fenêtre de mesure "
                "(J+14/J+28) n'est encore mûre. Patientez pour obtenir un verdict fiable.",
                "Changes were applied recently but no measurement window (J+14/J+28) has matured "
                "yet. Wait to get a reliable verdict.",
            )
        )

    if sample > 0 and avg_confidence < _MIN_CONFIDENCE:
        recs.append(
            _rec(
                "LOW_CONFIDENCE",
                "warning",
                "Confiance de mesure faible. Connectez Google Search Console / GA4, ciblez des "
                "pages à plus fort trafic et laissez le groupe contrôle se constituer.",
                "Low measurement confidence. Connect Google Search Console / GA4, target "
                "higher-traffic pages, and let the control group build up.",
            )
        )

    if seo_verdict in {"no_effect", "regressing"} and geo_verdict == "improving":
        recs.append(
            _rec(
                "SEO_FLAT_GEO_OK",
                "warning",
                "La préparation GEO progresse mais la performance de recherche reste plate. "
                "Ciblez des mots-clés à plus fort volume et améliorez meta-titres/descriptions "
                "pour le taux de clic.",
                "GEO readiness improves but search performance stays flat. Target higher-volume "
                "keywords and improve meta titles/descriptions for click-through rate.",
            )
        )

    if geo_verdict in {"no_effect", "regressing"} and seo_verdict == "improving":
        recs.append(
            _rec(
                "GEO_FLAT_SEO_OK",
                "warning",
                "La recherche progresse mais la préparation GEO reste plate. Ajoutez des faits "
                "confirmés, des FAQ et des blocs de réponse structurés pour les moteurs IA.",
                "Search improves but GEO readiness stays flat. Add confirmed facts, FAQs and "
                "structured answer blocks for AI engines.",
            )
        )

    if seo_verdict == "regressing" and geo_verdict == "regressing":
        recs.append(
            _rec(
                "REGRESSING",
                "critical",
                "L'agent dégrade SEO et GEO. Repassez en semi-automatique, suspendez l'auto-apply, "
                "et revoyez les dernières propositions et les tags négatifs avant de continuer.",
                "The agent is degrading both SEO and GEO. Switch back to semi-automatic, pause "
                "auto-apply, and review recent proposals and negative tags before continuing.",
            )
        )

    if avg_quality and avg_quality < _LOW_QUALITY:
        recs.append(
            _rec(
                "LOW_QUALITY",
                "warning",
                f"Qualité de contenu moyenne faible ({avg_quality:.0f}/100). Confirmez les faits "
                "manquants et affinez le profil/niche pour de meilleures générations.",
                f"Average content quality is low ({avg_quality:.0f}/100). Confirm missing facts "
                "and refine the business/niche profile for better generations.",
            )
        )

    if negative_tags > positive_tags and negative_tags >= 3:
        recs.append(
            _rec(
                "NEGATIVE_TAGS",
                "warning",
                f"{negative_tags} tags négatifs dominent. Les signaux de niche sont peut-être "
                "mal calibrés : revoyez les tags et relancez une analyse de marché.",
                f"{negative_tags} negative tags dominate. The niche signals may be miscalibrated: "
                "review tags and re-run a market analysis.",
            )
        )

    if seo_verdict == "improving" and geo_verdict == "improving":
        recs.append(
            _rec(
                "IMPROVING_KEEP",
                "success",
                "L'agent améliore SEO et GEO. Gardez ces réglages. Si vous êtes en "
                "semi-automatique, envisagez l'auto-apply pour les actions à faible risque.",
                "The agent improves both SEO and GEO. Keep these settings. If you are in "
                "semi-automatic mode, consider auto-apply for low-risk actions.",
            )
        )

    if not recs:
        recs.append(
            _rec(
                "INSUFFICIENT_DATA",
                "info",
                "Pas encore assez de données mûres pour conclure. Laissez l'agent tourner "
                "quelques cycles et atteindre les fenêtres J+14/J+28.",
                "Not enough matured data to conclude yet. Let the agent run a few cycles and "
                "reach the J+14/J+28 windows.",
            )
        )
    return recs


def evaluate_agent_effectiveness(shop: str, *, db_path: Path | None = None) -> dict[str, Any]:
    """Return a clear SEO/GEO effectiveness verdict plus how to improve it."""
    observations = list_observations(shop, limit=500, db_path=db_path)
    runs = list_runs(shop, limit=50, db_path=db_path)
    pending = list_pending_approvals(shop, include_closed=False, limit=200, db_path=db_path)
    settings = get_settings(shop, db_path=db_path)

    # Reuse the continuous-improvement aggregate for proposals/applied/tag counts.
    from app.geo.continuous_improvement import list_continuous_improvement  # noqa: PLC0415

    continuous = list_continuous_improvement(shop, limit=300, db_path=db_path)
    agent_runs = continuous.get("agent_runs", [])
    summary = continuous.get("summary", {}) if isinstance(continuous.get("summary"), dict) else {}

    learnable: list[dict[str, Any]] = []
    verdict_distribution: dict[str, int] = {}
    quality_scores: list[float] = []
    for observation in observations:
        metadata = (
            observation.get("metadata") if isinstance(observation.get("metadata"), dict) else {}
        )
        verdict = str(metadata.get("experiment_verdict") or "")
        if verdict:
            verdict_distribution[verdict] = verdict_distribution.get(verdict, 0) + 1
        quality = _num(metadata.get("content_quality_score"))
        if quality > 0:
            quality_scores.append(quality)
        if not metadata.get("learnable", True):
            continue
        deltas = _deltas_for(observation)
        learnable.append(
            {
                "field": metadata.get("field") or observation.get("action_type"),
                "confidence": _num(observation.get("confidence_score")),
                "outcome_score": _num(observation.get("outcome_score")),
                "seo_delta": _seo_delta(deltas),
                "geo_delta": _geo_delta(deltas),
                "is_primary_window": bool(observation.get("is_primary_window")),
            }
        )

    sample = len(learnable)
    avg_confidence = (
        sum(row["confidence"] for row in learnable) / sample if sample else 0.0
    )
    seo_score = _weighted_average([(row["seo_delta"] * 100, row["confidence"]) for row in learnable])
    geo_score = _weighted_average([(row["geo_delta"] * 100, row["confidence"]) for row in learnable])
    seo_verdict = _dimension_verdict(seo_score, sample, avg_confidence)
    geo_verdict = _dimension_verdict(geo_score, sample, avg_confidence)

    proposals_count = sum(
        int(run.get("summary", {}).get("proposals_created") or len(run.get("proposals") or []))
        for run in agent_runs
    )
    applied_count = sum(int(run.get("summary", {}).get("applied") or 0) for run in agent_runs)
    avg_quality = sum(quality_scores) / len(quality_scores) if quality_scores else 0.0

    recommendations = _build_recommendations(
        seo_verdict=seo_verdict,
        geo_verdict=geo_verdict,
        sample=sample,
        avg_confidence=avg_confidence,
        proposals_count=proposals_count,
        applied_count=applied_count,
        pending_count=len(pending),
        mode=settings.mode.value,
        avg_quality=avg_quality,
        positive_tags=int(summary.get("positive_tags") or 0),
        negative_tags=int(summary.get("negative_tags") or 0),
        has_any_run=bool(runs or agent_runs),
    )

    return {
        "shop": shop,
        "generated_at": datetime.now(UTC).isoformat(),
        "overall_verdict": _overall_verdict(seo_verdict, geo_verdict),
        "sample_size": sample,
        "primary_window_sample": sum(1 for row in learnable if row["is_primary_window"]),
        "avg_confidence": round(avg_confidence, 1),
        "min_sample_for_verdict": _MIN_SAMPLE,
        "primary_window_days": PRIMARY_WINDOW_DAYS,
        "seo": {
            "verdict": seo_verdict,
            "score": round(seo_score, 1),
            "sample": sample,
        },
        "geo": {
            "verdict": geo_verdict,
            "score": round(geo_score, 1),
            "sample": sample,
        },
        "verdict_distribution": verdict_distribution,
        "by_field": _by_field(learnable),
        "proposals_count": proposals_count,
        "applied_count": applied_count,
        "pending_approvals": len(pending),
        "avg_content_quality": round(avg_quality, 1),
        "recommendations": recommendations,
    }
