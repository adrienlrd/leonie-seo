"""Before/After impact report for GEO optimization events (task 122).

Produces a per-event report with score deltas, GSC/GA4 before/after,
confidence score, human-readable verdict and next recommendation.
Also renders a Markdown export suitable for merchant sharing.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

_VERDICTS = {
    "positif_probable": "positif_probable",
    "neutre": "neutre",
    "inconclusif": "inconclusif",
    "négatif_possible": "négatif_possible",
}

_RECOMMENDATIONS: dict[str, str] = {
    "positif_probable": "répliquer",
    "neutre": "ajuster",
    "négatif_possible": "rollback",
    "inconclusif": "attendre",
}


def _coerce_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _coerce_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _delta_int(before: int | None, after: int | None) -> int | None:
    if before is None or after is None:
        return None
    return after - before


def _delta_float(before: float | None, after: float | None) -> float | None:
    if before is None or after is None:
        return None
    return after - before


def _extract_scores(event: dict[str, Any]) -> dict[str, Any]:
    geo_before = _coerce_int(event.get("score_before"))
    geo_after = _coerce_int(event.get("score_after"))
    geo_delta = _delta_int(geo_before, geo_after)

    seo_before = _coerce_int((event.get("before_snapshot") or {}).get("seo_score"))
    seo_after = _coerce_int((event.get("after_snapshot") or {}).get("seo_score"))
    seo_delta = _delta_int(seo_before, seo_after)

    return {
        "geo_before": geo_before,
        "geo_after": geo_after,
        "geo_delta": geo_delta,
        "seo_before": seo_before,
        "seo_after": seo_after,
        "seo_delta": seo_delta,
    }


def _extract_gsc(event: dict[str, Any]) -> dict[str, Any]:
    before_gsc = (event.get("metrics_before") or {}).get("gsc") or {}
    after_gsc = (event.get("metrics_after") or {}).get("gsc") or {}
    has_after = bool(event.get("metrics_after"))

    imp_b = _coerce_int(before_gsc.get("impressions"))
    imp_a = _coerce_int(after_gsc.get("impressions")) if has_after else None
    clk_b = _coerce_int(before_gsc.get("clicks"))
    clk_a = _coerce_int(after_gsc.get("clicks")) if has_after else None
    ctr_b = _coerce_float(before_gsc.get("ctr"))
    ctr_a = _coerce_float(after_gsc.get("ctr")) if has_after else None
    pos_b = _coerce_float(before_gsc.get("position"))
    pos_a = _coerce_float(after_gsc.get("position")) if has_after else None

    return {
        "impressions_before": imp_b,
        "impressions_after": imp_a,
        "impressions_delta": _delta_int(imp_b, imp_a),
        "clicks_before": clk_b,
        "clicks_after": clk_a,
        "clicks_delta": _delta_int(clk_b, clk_a),
        "ctr_before": ctr_b,
        "ctr_after": ctr_a,
        "position_before": pos_b,
        "position_after": pos_a,
    }


def _extract_ga4(event: dict[str, Any]) -> dict[str, Any]:
    before_ga4 = (event.get("metrics_before") or {}).get("ga4") or {}
    after_ga4 = (event.get("metrics_after") or {}).get("ga4") or {}
    has_after = bool(event.get("metrics_after"))

    sessions_b = _coerce_float(before_ga4.get("sessions"))
    sessions_a = _coerce_float(after_ga4.get("sessions")) if has_after else None
    conv_b = _coerce_float(before_ga4.get("conversions"))
    conv_a = _coerce_float(after_ga4.get("conversions")) if has_after else None
    rev_b = _coerce_float(before_ga4.get("revenue"))
    rev_a = _coerce_float((event.get("observed_impact") or {}).get("revenue"))

    return {
        "sessions_before": sessions_b,
        "sessions_after": sessions_a,
        "conversions_before": conv_b,
        "conversions_after": conv_a,
        "revenue_before": rev_b,
        "revenue_after": rev_a,
    }


def _compute_verdict(
    confidence_score: int,
    geo_delta: int | None,
    gsc_impressions_delta: int | None = None,
) -> tuple[str, str]:
    if geo_delta is not None and geo_delta < 0:
        if gsc_impressions_delta is not None and gsc_impressions_delta > 0:
            return "neutre", "Le score GEO a baissé mais les impressions GSC ont augmenté."
        return "négatif_possible", "Le score GEO a diminué après l'optimisation."
    # GSC improvement can strengthen verdict even without GEO score change
    if gsc_impressions_delta is not None and gsc_impressions_delta > 0 and confidence_score >= 25:
        return "positif_probable", "Les impressions GSC ont augmenté après l'optimisation."
    if confidence_score >= 50 and (geo_delta is None or geo_delta >= 0):
        return "positif_probable", "Score de confiance élevé et score GEO stable ou en hausse."
    if confidence_score >= 25 and geo_delta == 0:
        return "neutre", "Score de confiance modéré mais aucun delta GEO observable."
    return "inconclusif", "Données insuffisantes pour conclure — attendez la prochaine fenêtre."


def build_event_report(
    event: dict[str, Any],
    confidence: dict[str, Any],
) -> dict[str, Any]:
    """Build a before/after report dict for a single GEO optimization event.

    Args:
        event: Row from ``list_geo_events``.
        confidence: Output of ``compute_event_confidence`` for the same event.

    Returns:
        Report dict with scores, GSC, GA4, verdict and recommendation.
    """
    scores = _extract_scores(event)
    gsc = _extract_gsc(event)
    ga4 = _extract_ga4(event)

    conf_score = confidence.get("score", 0)
    conf_label = confidence.get("label", "données_insuffisantes")
    verdict, verdict_note = _compute_verdict(
        conf_score, scores["geo_delta"], gsc["impressions_delta"],
    )
    next_rec = _RECOMMENDATIONS.get(verdict, "attendre")

    applied_at = ""
    for entry in event.get("status_history") or []:
        if (entry.get("status") or "").lower() == "applied":
            applied_at = entry.get("changed_at") or event.get("created_at", "")
    if not applied_at:
        applied_at = event.get("created_at", "")

    from app.geo.measurement_loop import build_verdict_summary  # noqa: PLC0415

    report = {
        "event_id": event.get("id"),
        "resource_type": event.get("resource_type", ""),
        "resource_id": event.get("resource_id", ""),
        "resource_title": event.get("resource_title") or event.get("resource_id", ""),
        "action_type": event.get("action_type", ""),
        "applied_at": applied_at,
        "scores": scores,
        "gsc": gsc,
        "ga4": ga4,
        "confidence": {"score": conf_score, "label": conf_label},
        "learning_windows": {
            "intermediate": "J+14",
            "primary": "J+28",
            "long_term": "J+60",
        },
        "verdict": verdict,
        "verdict_note": verdict_note,
        "next_recommendation": next_rec,
        "verdict_summary": "",
    }
    report["verdict_summary"] = build_verdict_summary(report)
    return report


def build_catalog_report(
    events: list[dict[str, Any]],
    confidence_entries: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build a full catalog report from all events and their confidence entries.

    Args:
        events: List of event dicts from ``list_geo_events``.
        confidence_entries: Parallel list from ``compute_catalog_confidence`` scores.

    Returns:
        Dict with list of per-event reports and aggregate summary.
    """
    conf_by_id: dict[int | None, dict[str, Any]] = {
        c.get("event_id"): c for c in confidence_entries
    }

    reports: list[dict[str, Any]] = []
    by_verdict: dict[str, int] = {
        "positif_probable": 0,
        "neutre": 0,
        "inconclusif": 0,
        "négatif_possible": 0,
    }
    for event in events:
        eid = event.get("id")
        conf = conf_by_id.get(eid) or {"score": 0, "label": "données_insuffisantes"}
        report = build_event_report(event, conf)
        reports.append(report)
        v = report["verdict"]
        by_verdict[v] = by_verdict.get(v, 0) + 1

    return {
        "reports": reports,
        "summary": {
            "total": len(reports),
            "by_verdict": by_verdict,
        },
    }


# ---------------------------------------------------------------------------
# Markdown export
# ---------------------------------------------------------------------------


def _fmt_int(value: int | None) -> str:
    if value is None:
        return "—"
    sign = "+" if value > 0 else ""
    return f"{sign}{value:,}".replace(",", " ")


def _fmt_pct(value: float | None) -> str:
    if value is None:
        return "—"
    return f"{value * 100:.2f}%"


def _fmt_pos(value: float | None) -> str:
    if value is None:
        return "—"
    return f"{value:.1f}"


def _fmt_eur(value: float | None) -> str:
    if value is None:
        return "—"
    return f"{value:.2f} €"


def render_markdown(reports: list[dict[str, Any]]) -> str:
    """Render a list of event reports as a Markdown string for merchant export.

    Args:
        reports: Output of ``build_catalog_report``'s ``reports`` list.

    Returns:
        Markdown-formatted string.
    """
    now_str = datetime.utcnow().strftime("%Y-%m-%d")
    lines: list[str] = [
        "# Rapport d'impact GEO — Giulio Geo",
        "",
        f"Généré le : {now_str}",
        "",
        "---",
    ]

    for report in reports:
        title = report.get("resource_title") or report.get("resource_id") or "—"
        action = report.get("action_type") or "—"
        applied = (report.get("applied_at") or "")[:10]

        scores = report.get("scores") or {}
        gsc = report.get("gsc") or {}
        ga4 = report.get("ga4") or {}
        conf = report.get("confidence") or {}
        conf_score = conf.get("score", 0)
        conf_label = conf.get("label", "données_insuffisantes")
        verdict = report.get("verdict", "inconclusif")
        verdict_note = report.get("verdict_note", "")
        rec = report.get("next_recommendation", "attendre")

        geo_b = scores.get("geo_before")
        geo_a = scores.get("geo_after")
        geo_d = scores.get("geo_delta")
        seo_b = scores.get("seo_before")
        seo_a = scores.get("seo_after")
        seo_d = scores.get("seo_delta")

        imp_b = gsc.get("impressions_before")
        imp_a = gsc.get("impressions_after")
        imp_d = gsc.get("impressions_delta")
        clk_b = gsc.get("clicks_before")
        clk_a = gsc.get("clicks_after")
        clk_d = gsc.get("clicks_delta")
        ctr_b = gsc.get("ctr_before")
        ctr_a = gsc.get("ctr_after")
        pos_b = gsc.get("position_before")
        pos_a = gsc.get("position_after")

        rev_b = ga4.get("revenue_before")
        rev_a = ga4.get("revenue_after")

        def _vi(v: int | None) -> str:
            return "—" if v is None else str(v)

        def _vd(v: int | None) -> str:
            if v is None:
                return "—"
            sign = "+" if v > 0 else ""
            return f"{sign}{v}"

        lines += [
            "",
            f"## {title} — {action} ({applied})",
            "",
            "| Métrique | Avant | Après | Δ |",
            "|---|---|---|---|",
            f"| Score GEO | {_vi(geo_b)} | {_vi(geo_a)} | {_vd(geo_d)} |",
            f"| Score SEO | {_vi(seo_b)} | {_vi(seo_a)} | {_vd(seo_d)} |",
            f"| Impressions GSC | {_vi(imp_b)} | {_vi(imp_a)} | {_vd(imp_d)} |",
            f"| Clics GSC | {_vi(clk_b)} | {_vi(clk_a)} | {_vd(clk_d)} |",
            f"| CTR | {_fmt_pct(ctr_b)} | {_fmt_pct(ctr_a)} | — |",
            f"| Position | {_fmt_pos(pos_b)} | {_fmt_pos(pos_a)} | — |",
            f"| Revenu observé | {_fmt_eur(rev_b)} | {_fmt_eur(rev_a)} | — |",
            "",
            f"**Score de confiance :** {conf_score} / 100 — {conf_label.replace('_', ' ')}",
            "",
            f"**Verdict :** {verdict.replace('_', ' ')}",
            "",
            f"_{verdict_note}_",
            "",
            f"**Recommandation :** {rec.capitalize()} sur les produits similaires.",
            "",
            "---",
        ]

    return "\n".join(lines)
