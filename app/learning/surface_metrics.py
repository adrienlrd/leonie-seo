"""Surface-aware metric profiles for outcome scoring.

Each optimization surface (meta title, meta description, alt text, ...) moves a
different lever in search. Judging them all on one fixed metric mix is wrong:
a meta description is not a ranking factor (it can't move impressions/position),
it wins the click (CTR). This module maps each surface to the metric profile it
actually owns, and decomposes an observed change into a human-readable cause.

Metric keys match the deltas produced by ``calculate_outcome`` in outcomes.py:
``impressions``, ``clicks``, ``ctr``, ``position``, ``conversions``,
``revenue``, ``score``.
"""

from __future__ import annotations

from typing import Any

# Default profile = the historical fixed weighting (backward compatible).
DEFAULT_PROFILE: dict[str, float] = {
    "impressions": 0.23,
    "clicks": 0.23,
    "ctr": 0.12,
    "position": 0.12,
    "conversions": 0.12,
    "revenue": 0.10,
    "score": 0.08,
}

# Per-surface weighting. Each sums to ~1.0 over the metrics it touches.
SURFACE_METRIC_PROFILES: dict[str, dict[str, float]] = {
    # Title is both a ranking signal AND the blue clickable line.
    "meta_title": {"position": 0.30, "impressions": 0.25, "ctr": 0.20, "clicks": 0.15, "score": 0.10},
    # Description is NOT a ranking factor — it wins the click (CTR).
    "meta_description": {"ctr": 0.50, "clicks": 0.40, "score": 0.10},
    # Body content drives relevance (ranking) + on-page conversion.
    "product_description": {
        "impressions": 0.20,
        "position": 0.15,
        "conversions": 0.25,
        "clicks": 0.20,
        "revenue": 0.10,
        "score": 0.10,
    },
    "collection_description": {"impressions": 0.40, "position": 0.30, "clicks": 0.20, "score": 0.10},
    # Image understanding / accessibility — mostly image search reach.
    "alt_text": {"impressions": 0.55, "clicks": 0.35, "score": 0.10},
    # Long-tail / AI-answer surfaces.
    "faq_block": {"impressions": 0.45, "clicks": 0.25, "ctr": 0.20, "score": 0.10},
    "answer_block": {"impressions": 0.45, "clicks": 0.25, "ctr": 0.20, "score": 0.10},
    "buying_guide": {"impressions": 0.45, "clicks": 0.25, "ctr": 0.20, "score": 0.10},
    # Structured data: rich-result / AI citation eligibility, little direct rank.
    "jsonld_faqpage": {"ctr": 0.45, "clicks": 0.45, "score": 0.10},
    "jsonld": {"ctr": 0.45, "clicks": 0.45, "score": 0.10},
    # Facts enrich both content (rank) and snippet/AI (click).
    "schema_facts": {"impressions": 0.35, "ctr": 0.25, "clicks": 0.30, "score": 0.10},
    # Internal links move the linked-to pages' ranking.
    "internal_link": {"impressions": 0.45, "position": 0.45, "score": 0.10},
}

# action_type values that map onto a surface profile.
_ACTION_TYPE_ALIASES: dict[str, str] = {
    "enrich_product_facts": "schema_facts",
    "add_answer_blocks": "answer_block",
    "create_collection_or_guide": "buying_guide",
    "strengthen_internal_links": "internal_link",
}


def _normalize(value: str | None) -> str:
    return str(value or "").strip().lower()


def get_metric_profile(
    field: str | None = None,
    action_type: str | None = None,
) -> dict[str, float]:
    """Return the metric weighting for a surface, falling back to the default."""
    key = _normalize(field)
    if key in SURFACE_METRIC_PROFILES:
        return SURFACE_METRIC_PROFILES[key]
    action_key = _normalize(action_type)
    if action_key in SURFACE_METRIC_PROFILES:
        return SURFACE_METRIC_PROFILES[action_key]
    if action_key in _ACTION_TYPE_ALIASES:
        return SURFACE_METRIC_PROFILES[_ACTION_TYPE_ALIASES[action_key]]
    return DEFAULT_PROFILE


def weighted_outcome(deltas: dict[str, float], profile: dict[str, float]) -> float:
    """Combine relative deltas using a surface profile, in [-1, 1]."""
    total = sum(profile.get(metric, 0.0) * deltas.get(metric, 0.0) for metric in profile)
    return max(-1.0, min(1.0, total))


# Which lever each metric represents, in merchant language.
_CAUSE_BY_METRIC: dict[str, dict[str, str]] = {
    "impressions": {
        "fr": "le classement s'est amélioré (titre / mots-clés / contenu)",
        "en": "ranking improved (title / keywords / content)",
    },
    "position": {
        "fr": "le rang Google a progressé (titre / mots-clés / contenu)",
        "en": "Google rank improved (title / keywords / content)",
    },
    "ctr": {
        "fr": "l'extrait donne plus envie de cliquer (description / formulation)",
        "en": "the snippet is more clickable (description / wording)",
    },
    "clicks": {
        "fr": "plus de clics générés vers le produit",
        "en": "more clicks generated to the product",
    },
    "conversions": {
        "fr": "meilleure conversion sur la page produit",
        "en": "better conversion on the product page",
    },
    "revenue": {
        "fr": "revenu organique en hausse",
        "en": "organic revenue up",
    },
}


def decompose_outcome(
    deltas: dict[str, float],
    *,
    field: str | None = None,
    action_type: str | None = None,
) -> dict[str, Any]:
    """Identify the dominant moved metric and map it to a human cause.

    Returns a dict with the primary metric, its direction, and a bilingual
    cause string. Used to explain *what worked* per surface on the Analyse page.
    """
    profile = get_metric_profile(field, action_type)
    # Score each metric by its profile weight × absolute movement.
    ranked = sorted(
        ((m, profile.get(m, 0.0) * abs(deltas.get(m, 0.0))) for m in profile),
        key=lambda pair: pair[1],
        reverse=True,
    )
    primary_metric = ranked[0][0] if ranked and ranked[0][1] > 0 else None
    if primary_metric is None:
        return {
            "primary_metric": None,
            "direction": "flat",
            "cause_fr": "Pas de mouvement significatif sur cette surface.",
            "cause_en": "No significant movement on this surface.",
        }
    raw = deltas.get(primary_metric, 0.0)
    direction = "up" if raw > 0 else "down"
    cause = _CAUSE_BY_METRIC.get(primary_metric, _CAUSE_BY_METRIC["clicks"])
    return {
        "primary_metric": primary_metric,
        "direction": direction,
        "cause_fr": cause["fr"],
        "cause_en": cause["en"],
    }
