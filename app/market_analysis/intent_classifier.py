"""Deterministic search intent classifier from SERP features.

Replaces the LLM's blind intent guess with rule-based classification grounded
in observed SERP signals (top competitor titles, People-Also-Ask presence,
featured snippet, AI Overview flag). When SERP data is missing, falls back to
the LLM's guess but marks the source as `llm_guessed` for transparency.
"""

from __future__ import annotations

import re
from typing import Any

_ECOMMERCE_DOMAINS = frozenset(
    {
        "amazon.fr",
        "amazon.com",
        "zooplus.fr",
        "zooplus.com",
        "wanimo.com",
        "bitiba.fr",
        "fnac.com",
        "cdiscount.com",
        "leroymerlin.fr",
        "boulanger.com",
        "darty.com",
        "ebay.fr",
        "ebay.com",
        "etsy.com",
        "manomano.fr",
        "rakuten.com",
        "rakuten.fr",
        "lacentrale.fr",
        "auchan.fr",
        "carrefour.fr",
        "leclerc.fr",
        "lidl.fr",
        "decathlon.fr",
    }
)

_ECOMMERCE_TITLE_TOKENS = frozenset(
    {
        "acheter",
        "achat",
        "prix",
        "promo",
        "soldes",
        "livraison",
        "boutique",
        "shop",
        "magasin",
        "commander",
        "ajouter",
        "stock",
    }
)

_COMPARISON_TITLE_TOKENS = frozenset(
    {
        "meilleur",
        "meilleurs",
        "meilleure",
        "meilleures",
        "top",
        "comparatif",
        "comparaison",
        "vs",
        "versus",
        "guide",
        "selection",
        "sélection",
        "choisir",
        "quel",
        "quelle",
    }
)

_INFORMATIONAL_QUERY_PREFIXES = frozenset(
    {
        "pourquoi",
        "comment",
        "qu'est-ce",
        "que",
        "quand",
        "où",
        "ou ",
        "définition",
        "differance",
        "différence",
        "c'est",
    }
)

_LOCAL_HINTS = frozenset(
    {
        "près de moi",
        "pres de moi",
        "à côté",
        "a cote",
        "autour de moi",
        "livraison",
        "magasin",
        "boutique",
        "à paris",
        "à lyon",
        "à marseille",
        "à toulouse",
        "à bordeaux",
        "à lille",
        "à nantes",
        "à nice",
        "à strasbourg",
    }
)

_VALID_INTENTS = frozenset(
    {
        "transactional",
        "informational",
        "commercial_investigation",
        "commercial",
        "local",
        "navigational",
        "unknown",
    }
)


def classify_intent(
    *,
    query: str,
    serp: dict[str, Any] | None,
    llm_intent: str | None = None,
) -> dict[str, Any]:
    """Classify search intent from SERP features, with LLM fallback.

    Args:
        query: the keyword being classified.
        serp: SERP intelligence dict with `paa`, `top_competitors`,
            `featured_snippet`, optional `has_ai_overview`.
        llm_intent: optional LLM-guessed intent used as fallback.

    Returns:
        `{intent_type, intent_type_source, serp_feature_targets, signals}`.
        `intent_type_source` is `serp_classified` when SERP rules fired,
        `llm_guessed` when only the LLM was usable, or `unclassified` otherwise.
    """
    query_lc = (query or "").lower()
    feature_targets = _detect_feature_targets(serp)

    if _query_is_local(query_lc) or _serp_has_local_hints(serp):
        return _result("local", "serp_classified", feature_targets, ["local_hint"])

    serp_signals = _gather_serp_signals(serp)

    if serp_signals["has_any"]:
        if serp_signals["comparison_score"] >= 2:
            return _result(
                "commercial_investigation",
                "serp_classified",
                feature_targets,
                ["comparison_titles"],
            )
        if serp_signals["ecommerce_score"] >= 2:
            return _result(
                "transactional",
                "serp_classified",
                feature_targets,
                ["ecommerce_domains", "ecommerce_titles"],
            )
        if serp_signals["paa_count"] >= 2 and serp_signals["ecommerce_score"] == 0:
            return _result(
                "informational",
                "serp_classified",
                feature_targets,
                ["paa_present", "no_ecommerce"],
            )
        if _query_looks_informational(query_lc):
            return _result("informational", "serp_classified", feature_targets, ["query_prefix"])

    fallback = (llm_intent or "").strip().lower()
    if fallback and fallback in _VALID_INTENTS:
        return _result(fallback, "llm_guessed", feature_targets, [])

    return _result("unknown", "unclassified", feature_targets, [])


def classify_batch(
    serp_intel: dict[str, dict[str, Any]],
    *,
    llm_intents: dict[str, str] | None = None,
) -> dict[str, dict[str, Any]]:
    """Classify each keyword in a SERP intelligence batch."""
    llm_intents = llm_intents or {}
    out: dict[str, dict[str, Any]] = {}
    for query, serp in serp_intel.items():
        out[query] = classify_intent(query=query, serp=serp, llm_intent=llm_intents.get(query))
    return out


def _result(
    intent_type: str,
    source: str,
    targets: list[str],
    signals: list[str],
) -> dict[str, Any]:
    return {
        "intent_type": intent_type,
        "intent_type_source": source,
        "serp_feature_targets": targets,
        "signals": signals,
    }


def _detect_feature_targets(serp: dict[str, Any] | None) -> list[str]:
    if not isinstance(serp, dict):
        return []
    targets: list[str] = []
    if serp.get("paa"):
        targets.append("paa")
    if serp.get("featured_snippet"):
        targets.append("featured_snippet")
    if serp.get("has_ai_overview"):
        targets.append("ai_overview")
    return targets


def _query_is_local(query_lc: str) -> bool:
    return any(hint in query_lc for hint in _LOCAL_HINTS)


def _serp_has_local_hints(serp: dict[str, Any] | None) -> bool:
    if not isinstance(serp, dict):
        return False
    for paa in serp.get("paa") or []:
        if any(hint in paa.lower() for hint in _LOCAL_HINTS):
            return True
    return False


def _query_looks_informational(query_lc: str) -> bool:
    return any(query_lc.startswith(prefix) for prefix in _INFORMATIONAL_QUERY_PREFIXES)


def _gather_serp_signals(serp: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(serp, dict):
        return {"has_any": False, "ecommerce_score": 0, "comparison_score": 0, "paa_count": 0}
    competitors = serp.get("top_competitors") or []
    paa = serp.get("paa") or []
    ecommerce_score = 0
    comparison_score = 0
    for comp in competitors:
        if not isinstance(comp, dict):
            continue
        domain = (comp.get("domain") or "").lower()
        title_tokens = set(re.findall(r"[a-zàâäéèêëîïôùûüç]+", (comp.get("title") or "").lower()))
        if domain in _ECOMMERCE_DOMAINS:
            ecommerce_score += 1
        if title_tokens & _ECOMMERCE_TITLE_TOKENS:
            ecommerce_score += 1
        if title_tokens & _COMPARISON_TITLE_TOKENS:
            comparison_score += 1
    return {
        "has_any": bool(competitors or paa),
        "ecommerce_score": ecommerce_score,
        "comparison_score": comparison_score,
        "paa_count": len(paa),
    }
