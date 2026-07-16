"""Market analysis engine — per-product SEO/GEO opportunity + content pack generation."""

from __future__ import annotations

import json
import logging
import os
import re
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from app.business_profile.context import build_business_profile_context_meta
from app.geo.facts import analyze_product_facts
from app.llm import LLMError, get_router
from app.market_analysis.competitor_crawl.config import CompetitorCrawlConfig
from app.market_analysis.competitor_crawl.extractor import extract_merchant_product_features
from app.market_analysis.competitor_crawl.fetcher import fetch_competitor_targets
from app.market_analysis.competitor_crawl.insights import build_competitor_crawl_insights
from app.market_analysis.competitor_crawl.models import CompetitorCrawlTarget
from app.market_analysis.competitor_crawl.prompt import format_competitor_crawl_for_prompt
from app.market_analysis.competitor_crawl.store import record_competitor_crawl_run
from app.market_analysis.competitor_crawl.url_selection import select_competitor_urls_for_product
from app.market_analysis.competitors import (
    build_competitor_signals,
    load_excluded_competitors,
)
from app.market_analysis.history_context import (
    build_optimization_history,
    format_optimization_history,
)
from app.market_analysis.providers.dataforseo_provider import DataForSEOProvider
from app.market_analysis.providers.free_provider import (
    FreeProvider,
    signals_from_llm_keywords,
)
from app.market_analysis.providers.google_ads_provider import GoogleAdsKeywordProvider
from app.market_analysis.providers.types import KeywordSignal
from app.niche.signals.google_suggest import fetch_suggestions_bulk
from app.observability.metrics import check_budget
from app.shop_identity import brand_terms as shop_brand_terms
from app.shop_identity import storefront_host
from app.snapshot.scope import filter_products_by_scope

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "Tu es un expert SEO et GEO copywriter pour boutiques Shopify. "
    "Réponds toujours avec du JSON valide et rien d'autre. "
    "Ne jamais inventer de faits. Signaler clairement les affirmations incertaines."
)

# Pass 1 (targeting): product understanding + candidate keywords.
_PASS1_KEYS = (
    "product_summary",
    "target_customer",
    "buying_intents",
    "seo_keywords",
    "geo_questions",
)

# Pass 2 (content): the full content pack, generated with real SERP/PAA/crawl data.
_PASS2_KEYS = (
    "proposed_meta_title",
    "proposed_meta_description",
    "proposed_image_alts",
    "proposed_product_title_if_different",
    "proposed_product_description",
    "proposed_faq",
    "proposed_geo_answer_block",
    "proposed_geo_definition_block",
    "proposed_geo_quick_facts",
    "proposed_geo_comparison_table",
    "proposed_blog_title",
    "proposed_blog_outline",
    "proposed_blog_intro",
    "proposed_blog_ideas",
    "recommended_content_actions",
    "facts_used",
    "facts_missing",
    "claims_used",
    "confidence",
)

_JSON_KEYS = _PASS1_KEYS + _PASS2_KEYS

# Per-plan monthly LLM budget (USD). Two LLM passes per product double the cost,
# so the engine gates pass 2 on remaining budget. Free keeps a small non-zero
# budget so it still gets content (degraded, no DataForSEO). Provisional until
# real billing wires the plan through.
_PLAN_BUDGETS_USD = {"free": 2.0, "starter": 5.0, "pro": 20.0, "agency": 50.0}
_DEFAULT_BUDGET_USD = 20.0

_INFORMATIVE_FACT_KEYS = frozenset(
    {
        "description",
        "product_type",
        "price",
        "materials",
        "certifications",
        "origins",
        "origin",
        "targets",
        "properties",
        "warranty",
        "delivery",
        "returns",
        "care",
        "care_instructions",
        "dimensions",
        "capacity",
        "battery_autonomy",
        "compatibility",
        "size_recommendation",
        "color",
        "size",
        "product_status",
        "use_cases",
        "selection_criteria",
    }
)
_NARRATIVE_FACT_KEYS = _INFORMATIVE_FACT_KEYS - {"description", "price"}
_STRICT_CLAIM_FACT_KEYS = frozenset(
    {
        "materials",
        "origins",
        "origin",
        "certifications",
        "warranty",
        "delivery",
        "returns",
        "care",
        "care_instructions",
        "dimensions",
        "compatibility",
        "size_recommendation",
        "health_benefit",
        "anti_pull",
        "durability",
        "sustainability",
    }
)
_MERCHANT_FACT_LABELS = {
    "materials": "Materials",
    "origins": "Manufacturing origin",
    "certifications": "Certifications",
    "warranty": "Warranty",
    "care": "Care instructions",
    "care_instructions": "Care instructions",
    "dimensions": "Dimensions",
    "capacity": "Capacity",
    "battery_autonomy": "Battery or autonomy",
    "compatibility": "Compatibility",
    "color": "Color",
    "size": "Size",
    "size_recommendation": "Size recommendation",
    "use_cases": "Confirmed use cases",
    "selection_criteria": "Selection criteria",
}

_CLAIM_PATTERNS: tuple[tuple[str, str], ...] = (
    (
        "materials",
        r"\b(cachemire|laine|coton|nylon|cuir|acier|inox|bois|silicone|bambou|polyester|corde)\b",
    ),
    ("origins", r"\b(fabriqu[ée]?\s+en|made\s+in|origine|france|europ[ée]en)\b"),
    ("certifications", r"\b(certifi[ée]?|bio|organic|fsc|oeko|gots)\b"),
    ("warranty", r"\b(garantie|garanti|warranty|satisfait\s+ou\s+rembours)\b"),
    ("delivery", r"\b(livraison|exp[ée]dition|delivery|shipping)\b"),
    ("returns", r"\b(retours?|remboursement|refund|returns?)\b"),
    ("care", r"\b(lavable|nettoyage|entretien|washable|cleaning)\b"),
    ("dimensions", r"\b\d+(?:[.,]\d+)?\s?(?:cm|mm|ml|l|kg|g)\b"),
    (
        "compatibility",
        r"\b(compatible|adapt[ée]\s+[àa]|convient\s+[àa]|taille|race|petits?\s+chiens?|grands?\s+chiens?)\b",
    ),
    ("performance", r"\b(silencieu(?:x|se)|ultra[- ]?silencieu(?:x|se)|anti[- ]?fuite)\b"),
    ("anti_pull", r"\b(anti[- ]?traction|no[- ]?pull|empêche\s+de\s+tirer)\b"),
    (
        "health_benefit",
        r"\b(sant[ée]|v[ée]t[ée]rinaire|douleurs?|arthrose|anxi[ée]t[ée]|anti[- ]?stress|maladie|pr[ée]vient)\b",
    ),
    (
        "durability",
        r"\b(r[ée]sistant|robuste|indestructible|longue\s+dur[ée]e|qualit[ée]\s+sup[ée]rieure)\b",
    ),
    (
        "sustainability",
        r"\b([ée]cologique|[ée]co[- ]?responsable|durable|recycl[ée]?|biod[ée]gradable)\b",
    ),
)

_SURFACE_OUTPUT_FIELDS: dict[str, tuple[str, ...]] = {
    "metadata": ("proposed_meta_title", "proposed_meta_description"),
    "product_description": ("proposed_product_description",),
    "faq": ("proposed_faq",),
    "geo_answer": (
        "proposed_geo_answer_block",
        "proposed_geo_definition_block",
        "proposed_geo_quick_facts",
        "proposed_geo_comparison_table",
    ),
    "blog": (
        "proposed_blog_title",
        "proposed_blog_intro",
        "proposed_blog_outline",
        "proposed_blog_ideas",
    ),
}

_SURFACE_BLOCKED_ISSUES = {
    "metadata": "metadata_blocked_missing_evidence",
    "product_description": "product_description_blocked_missing_evidence",
    "faq": "faq_blocked_missing_evidence",
    "geo_answer": "geo_answer_blocked_missing_evidence",
    "blog": "blog_blocked_missing_evidence",
}

_BLOCKING_REASON_LABELS = {
    "product_consistency_below_threshold": "Bloqué : cohérence produit insuffisante",
    "unsupported_product_claims": "Bloqué : claims non justifiés",
    "unverified_claim_reference": "Bloqué : claims non justifiés",
    "missing_claim_evidence_ledger": "Bloqué : claims non justifiés",
    "forbidden_promise_detected": "Bloqué : claims non justifiés",
    "faq_blocked_missing_evidence": "Bloqué : FAQ générée sans preuves suffisantes",
    "product_fact_conflict": "Bloqué : conflit dans les faits produit",
    "keyword_guardrail_blocked": "Bloqué : mots-clés non alignés avec le besoin client",
    "keyword_customer_need_alignment_low": "Bloqué : mots-clés non alignés avec le besoin client",
    "insufficient_product_page_keyword_targets": "Bloqué : mots-clés produit insuffisants",
    "keyword_targets_too_indirect": "Bloqué : trop de mots-clés indirects ou non prouvés",
    "primary_keyword_not_used_in_content": "Bloqué : mot-clé principal non utilisé dans le contenu",
    "secondary_keyword_coverage_low": "Bloqué : mots-clés secondaires trop peu utilisés",
    "important_keyword_coverage_low": "Bloqué : mots-clés sélectionnés peu exploités",
    "important_keyword_missing_from_metadata": "Bloqué : mots-clés absents des métadonnées",
}

_REFLECTION_THRESHOLD = 75
_REFLECTION_MAX_RETRIES = 1
_REFLECTION_QUESTIONS: tuple[dict[str, str], ...] = (
    {
        "key": "business_alignment",
        "question": "Is the proposal coherent with the validated business analysis?",
    },
    {
        "key": "product_consistency",
        "question": "Is the proposal faithful to the product and its confirmed facts?",
    },
    {
        "key": "seo_potential",
        "question": "Can the proposal realistically generate SEO traffic?",
    },
    {
        "key": "geo_potential",
        "question": "Can the proposal answer extractable GEO/AI-search questions?",
    },
    {
        "key": "merchant_actionability",
        "question": "Can a merchant understand, review, and publish the proposal easily?",
    },
)


def _strip_html(html: str) -> str:
    without_tags = re.sub(r"<[^>]+>", " ", str(html))
    return re.sub(r"\s+", " ", without_tags).strip()


def _coerce_list(value: Any) -> list[Any]:
    """Coerce a Shopify field to a list, regardless of REST or GraphQL shape."""
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        edges = value.get("edges")
        if isinstance(edges, list):
            return [e.get("node", e) if isinstance(e, dict) else e for e in edges]
        nodes = value.get("nodes")
        if isinstance(nodes, list):
            return nodes
    return []


def _coerce_str(value: Any, fallback: str = "") -> str:
    """Recursively flatten any LLM field to a plain string.

    Handles nested dicts and lists so that e.g.
    {demographics: {age: "25-45", ...}, psychographics: ["Animaux", ...]}
    becomes "25-45, Tous, France — Animaux, Accessoires" instead of the raw repr.
    """
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        parts = [_coerce_str(v) for v in value.values() if v is not None]
        return " — ".join(p for p in parts if p)
    if isinstance(value, list):
        parts = [_coerce_str(item) for item in value if item is not None]
        return ", ".join(p for p in parts if p)
    if value is None:
        return fallback
    return str(value)


def _coerce_str_list(value: Any) -> list[str]:
    """Ensure a list of LLM strings contains only plain strings."""
    if not isinstance(value, list):
        return []
    return [_coerce_str(item) for item in value if item]


def _coerce_target_customer(value: Any) -> str:
    return _coerce_str(value)


# The LLM occasionally prepends a marker (e.g. "new: …") into the keyword string
# itself instead of using the separate "new" field. Strip it so the query stays clean
# for matching, SERP lookups and merchant display.
_KEYWORD_PREFIX_RE = re.compile(
    r"^\s*(?:new|nouveau|nouvelle|ajout[ée]?|added)\s*[:\-–—]\s*", re.IGNORECASE
)


def _clean_keyword_query(value: Any) -> str:
    """Normalize a keyword query: drop parasitic prefixes, collapse whitespace."""
    text = _KEYWORD_PREFIX_RE.sub("", _coerce_str(value).strip())
    return " ".join(text.split())


def _coerce_seo_keywords(value: Any) -> list[dict[str, Any]]:
    """Ensure every seo_keyword item has plain-string scalar fields."""
    if not isinstance(value, list):
        return []
    out = []
    for kw in value:
        if not isinstance(kw, dict):
            continue
        kw = dict(kw)
        kw["query"] = _clean_keyword_query(kw.get("query", ""))
        for field in ("intent_type", "reason"):
            kw[field] = _coerce_str(kw.get(field, ""))
        out.append(kw)
    return out


_CONFIDENCE_ALIASES = {
    "high": "high",
    "élevée": "high",
    "elevee": "high",
    "élevé": "high",
    "eleve": "high",
    "haute": "high",
    "forte": "high",
    "fort": "high",
    "medium": "medium",
    "moyenne": "medium",
    "moyen": "medium",
    "modérée": "medium",
    "moderee": "medium",
    "moderate": "medium",
    "low": "low",
    "faible": "low",
    "basse": "low",
    "bas": "low",
}


def _normalize_confidence(value: Any) -> str:
    """Map any LLM confidence wording (incl. French) to high/medium/low.

    The LLM sometimes returns localized values like "élevée" despite the prompt;
    canonicalize so the frontend confidence colour mapping stays correct.
    """
    raw = _coerce_str(value).strip().lower()
    if not raw:
        return ""
    return _CONFIDENCE_ALIASES.get(raw, "medium")


def _coerce_geo_questions(value: Any) -> list[dict[str, Any]]:
    """Ensure every geo_question item has plain-string scalar fields."""
    if not isinstance(value, list):
        return []
    out = []
    for q in value:
        if not isinstance(q, dict):
            continue
        q = dict(q)
        for field in ("question", "answer_angle", "content_block_type"):
            q[field] = _coerce_str(q.get(field, ""))
        q["confidence"] = _normalize_confidence(q.get("confidence", ""))
        out.append(q)
    return out


def _coerce_faq(value: Any) -> list[dict[str, str]]:
    """Ensure every FAQ item has plain-string q and a fields."""
    if not isinstance(value, list):
        return []
    out = []
    for item in value:
        if not isinstance(item, dict):
            continue
        out.append({"q": _coerce_str(item.get("q", "")), "a": _coerce_str(item.get("a", ""))})
    return out


def _coerce_blog_ideas(value: Any) -> list[dict[str, Any]]:
    """Ensure every blog idea has title, target_keyword, intro and outline."""
    if not isinstance(value, list):
        return []
    ideas: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        title = _coerce_str(item.get("title") or item.get("blog_title", "")).strip()
        keyword = _clean_keyword_query(item.get("target_keyword") or item.get("keyword", ""))
        intro = _coerce_str(item.get("intro") or item.get("summary", "")).strip()
        outline = _coerce_str_list(item.get("outline") or item.get("h2_questions") or [])
        if title:
            ideas.append(
                {
                    "title": title,
                    "target_keyword": keyword,
                    "intro": intro,
                    "outline": outline[:7],
                }
            )
    return ideas


def _extract_product_images(product: dict[str, Any]) -> list[dict[str, Any]]:
    """Return up to 5 images from a Shopify product (GraphQL edges/node or flat list)."""
    raw = product.get("images")
    if isinstance(raw, dict):
        edges: list[Any] = raw.get("edges", [])
    elif isinstance(raw, list):
        edges = raw
    else:
        return []
    result: list[dict[str, Any]] = []
    for edge in edges[:10]:
        if not isinstance(edge, dict):
            continue
        node = edge.get("node", edge)
        if not isinstance(node, dict):
            continue
        result.append(
            {
                "id": str(node.get("id") or ""),
                "url": str(node.get("url") or node.get("src") or ""),
                "current_alt": node.get("altText") or node.get("alt"),
            }
        )
    return result


def _default_image_alt(product_title: str, keyword: str) -> str:
    """Deterministic alt text: product title plus a value-adding keyword."""
    base = product_title.strip()
    kw = keyword.strip()
    if kw and kw.lower() not in base.lower():
        base = f"{base} – {kw}"
    return base[:125].rstrip()


def _fill_image_alts(
    value: Any,
    product_images: list[dict[str, Any]],
    product_title: str,
    keywords: list[str],
) -> list[dict[str, str]]:
    """Return exactly one alt proposal per product image, in image order.

    LLM-provided alts are matched by image id (then by position). For any image
    the LLM skipped, the existing alt is kept when it has one — overwriting a
    human-written description with a "title – keyword" template is a downgrade
    (Google Images wants alts that describe the image). Only images with NO alt
    at all fall back to the product title plus a distinct value-adding keyword.
    """
    llm_items = value if isinstance(value, list) else []
    by_id: dict[str, str] = {}
    positional: list[str] = []
    for item in llm_items:
        if isinstance(item, dict):
            alt = _coerce_str(item.get("proposed_alt", "")).strip()
            image_id = _coerce_str(item.get("image_id", "")).strip()
            if image_id:
                by_id[image_id] = alt
            positional.append(alt)
        elif isinstance(item, str):
            positional.append(_coerce_str(item).strip())

    title_lower = product_title.lower()
    value_keywords: list[str] = []
    seen: set[str] = set()
    for kw in keywords:
        clean = kw.strip()
        if clean and clean.lower() not in title_lower and clean.lower() not in seen:
            value_keywords.append(clean)
            seen.add(clean.lower())

    out: list[dict[str, str]] = []
    fallback_index = 0
    for i, img in enumerate(product_images):
        image_id = str(img.get("id") or "")
        alt = by_id.get(image_id, "")
        if not alt and i < len(positional):
            alt = positional[i]
        if not alt:
            alt = str(img.get("current_alt") or "").strip()
        if not alt:
            if value_keywords:
                keyword = value_keywords[fallback_index % len(value_keywords)]
            else:
                keyword = keywords[0] if keywords else ""
            fallback_index += 1
            alt = _default_image_alt(product_title, keyword)
        out.append({"image_id": image_id, "proposed_alt": alt[:125]})
    return out


def _coerce_claims(value: Any) -> list[dict[str, Any]]:
    """Normalize generated claims and their supporting confirmed fact keys."""
    if not isinstance(value, list):
        return []
    claims: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        claim = _coerce_str(item.get("claim", "")).strip()
        fact_keys = [
            fact_key.strip()
            for fact_key in _coerce_str_list(item.get("fact_keys", []))
            if fact_key.strip()
        ]
        if claim:
            claims.append({"claim": claim, "fact_keys": fact_keys})
    return claims


def _fetch_trends_once(
    top_titles: list[str], status_out: dict[str, Any] | None = None
) -> list[Any]:
    """Call Google Trends once with up to 5 product title seeds. Returns [] on any error.

    ``status_out`` (optional) is populated with the outcome (``ok`` | ``empty`` |
    ``error`` | ``unavailable`` + detail + count) so the analysis can record *why*
    Trends returned no data, distinguishing a real empty result from a 429 block.
    """
    if not top_titles:
        if status_out is not None:
            status_out.update({"status": "empty", "detail": "no product titles", "count": 0})
        return []
    try:
        from app.niche.signals.trends import fetch_related_queries  # noqa: PLC0415

        return fetch_related_queries(
            top_titles[:5], geo="FR", timeframe="today 12-m", status_out=status_out
        )
    except Exception as exc:
        logger.warning("Google Trends unavailable: %s", exc)
        if status_out is not None:
            status_out.update(
                {"status": "error", "detail": f"{type(exc).__name__}: {exc}", "count": 0}
            )
        return []


def _fetch_realtime_signals_once(
    shop: str,
    niche_hypothesis: dict[str, Any] | None,
    top_titles: list[str],
    db_path: Path | None,
    *,
    force: bool = False,
    status_out: dict[str, Any] | None = None,
    persist: bool = True,
) -> dict[str, Any] | None:
    """Call the grounded real-time signal fetcher once per product. Fail-open.

    Already gated to the "agency" plan + a configured GEMINI_API_KEY inside
    `fetch_realtime_signals` itself — this wrapper only adds the same
    exception safety net as `_fetch_trends_once` for the unlikely case of an
    error the fetcher itself didn't already catch. ``force`` bypasses the
    plan gate (Pro/Grande boutique comparison tool only). ``status_out``
    (optional) is populated with why the call did or didn't run — so a
    silent no-op (e.g. missing GEMINI_API_KEY) is diagnosable in the result
    instead of just leaving `realtime_grounding` out of `sources_used`.
    ``persist=False`` (used by the per-product Pass 1 loop) skips writing to
    disk immediately — the caller merges every product's signal and persists
    once via `persist_realtime_signals`.
    """
    try:
        from app.niche.signals.realtime_trends import fetch_realtime_signals  # noqa: PLC0415

        return fetch_realtime_signals(
            shop,
            niche_hypothesis,
            [t for t in top_titles if t],
            db_path=db_path,
            force=force,
            status_out=status_out,
            persist=persist,
        )
    except Exception as exc:
        logger.warning("Real-time signals unavailable: %s", exc)
        if status_out is not None:
            status_out.update({"status": "llm_error", "detail": f"{type(exc).__name__}: {exc}"})
        return None


def _verify_keywords_once(
    shop: str,
    keywords: list[str],
    niche_summary: str,
    *,
    force: bool = False,
    status_out: dict[str, Any] | None = None,
) -> dict[str, dict[str, Any]] | None:
    """Call the grounded keyword-verification fetcher once per job. Fail-open,
    same exception safety net as `_fetch_realtime_signals_once`.
    """
    try:
        from app.niche.signals.realtime_trends import (
            verify_keywords_against_market,  # noqa: PLC0415
        )

        return verify_keywords_against_market(
            shop, keywords, niche_summary, force=force, status_out=status_out
        )
    except Exception as exc:
        logger.warning("Keyword market verification unavailable: %s", exc)
        if status_out is not None:
            status_out.update({"status": "llm_error", "detail": f"{type(exc).__name__}: {exc}"})
        return None


def _merge_realtime_signals(per_product_signals: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Combine each product's own grounded signal (events/rising_queries/
    competitor_moves/citations) into one deduplicated catalog-wide snapshot.

    Each product now gets its own grounded realtime-signal call (see the Pass 1
    loop), so the same event/query can legitimately be returned by several
    products — dedup by title/query text keeps the merged file from repeating
    the same canicule alert once per product. Returns None if nothing was
    fetched (fail-open — mirrors every other grounded-call caller here).
    """
    if not per_product_signals:
        return None
    events: list[dict[str, Any]] = []
    rising_queries: list[dict[str, Any]] = []
    competitor_moves: list[dict[str, Any]] = []
    citations: list[dict[str, Any]] = []
    seen_events: set[str] = set()
    seen_queries: set[str] = set()
    seen_moves: set[str] = set()
    seen_citation_urls: set[str] = set()
    latest_fetched_at = ""
    for signal in per_product_signals:
        for event in signal.get("events") or []:
            key = str((event or {}).get("title") or "").strip().lower()
            if key and key not in seen_events:
                seen_events.add(key)
                events.append(event)
        for query in signal.get("rising_queries") or []:
            key = str((query or {}).get("query") or "").strip().lower()
            if key and key not in seen_queries:
                seen_queries.add(key)
                rising_queries.append(query)
        for move in signal.get("competitor_moves") or []:
            key = str((move or {}).get("summary") or "").strip().lower()
            if key and key not in seen_moves:
                seen_moves.add(key)
                competitor_moves.append(move)
        for citation in signal.get("citations") or []:
            url = str((citation or {}).get("url") or "").strip()
            if url and url not in seen_citation_urls:
                seen_citation_urls.add(url)
                citations.append(citation)
        fetched_at = str(signal.get("fetched_at") or "")
        if fetched_at > latest_fetched_at:
            latest_fetched_at = fetched_at
    if not events and not rising_queries and not competitor_moves:
        return None
    return {
        "events": events,
        "rising_queries": rising_queries,
        "competitor_moves": competitor_moves,
        "citations": citations,
        "fetched_at": latest_fetched_at or datetime.now(UTC).isoformat(),
    }


def _apply_market_verification(
    pass1_states: list[dict[str, Any]], verifications: dict[str, dict[str, Any]]
) -> int:
    """Write market-verification verdicts onto matching seo_keywords in place.

    Bumps `demand_score` (+10 "rising", +5 "confirmed", -10 "declining",
    capped 0-100) — the field pass-1's own keyword items already carry and
    that downstream sorting already reads as a priority signal (see
    `_repair_keyword_selection...` and the candidate pool sort) — so the
    agency plan's real market signal actually shifts keyword ranking, not
    just prompt context. "confirmed" gets a smaller bump than "rising"
    because most verdicts come back confirmed (17/21 in the live 2026-07-16
    comparison) — a web-verified keyword should outrank an unverified or
    no_signal one, without drowning out the rising signal. Returns the count
    of keywords annotated (surfaced as `keywords_with_market_verification`
    in the plan-comparison diff summary).
    """
    deltas = {"rising": 10.0, "confirmed": 5.0, "declining": -10.0}
    annotated = 0
    for state in pass1_states:
        for kw in state["pack"].get("seo_keywords") or []:
            if not isinstance(kw, dict):
                continue
            query = str(kw.get("query") or "").strip().lower()
            verdict = verifications.get(query)
            if not verdict:
                continue
            kw["market_verification"] = verdict
            notes = kw.setdefault("notes", [])
            if isinstance(notes, list):
                notes.append("verified_by_market")
            delta = deltas.get(verdict["evidence"])
            if delta is not None:
                base = float(kw.get("demand_score") or 0)
                kw["demand_score"] = max(0.0, min(100.0, base + delta))
            annotated += 1
    return annotated


def _format_realtime_signals(signals: dict[str, Any] | None) -> str:
    """Render events + rising queries into one prompt-ready line, or "" if none."""
    if not signals:
        return ""
    parts: list[str] = []
    for event in signals.get("events") or []:
        title = str((event or {}).get("title") or "").strip()
        if title:
            parts.append(title)
    for query in signals.get("rising_queries") or []:
        q = str((query or {}).get("query") or "").strip()
        if q:
            parts.append(q)
    return ", ".join(parts)


def _match_trends(
    product_title: str,
    all_trend_signals: list[Any],
) -> tuple[list[str], list[str]]:
    """Return (top_queries, rising_queries) whose keywords overlap with the product title."""
    title_words = {w for w in product_title.lower().split() if len(w) > 3}
    top, rising = [], []
    for sig in all_trend_signals:
        kw = getattr(sig, "keyword", "")
        if not any(w in kw for w in title_words):
            continue
        if getattr(sig, "source", "") == "trends_rising":
            rising.append(kw)
        else:
            top.append(kw)
    return top[:5], rising[:5]


def _read_stock(product: dict[str, Any]) -> tuple[int | None, str]:
    """Return (quantity, status_label) from the first variant. quantity=None if unmanaged."""
    variants = _coerce_list(product.get("variants"))
    first = variants[0] if variants else {}
    if not isinstance(first, dict):
        return None, "inconnu"
    qty_raw = first.get("inventory_quantity") or first.get("inventoryQuantity")
    if qty_raw is None:
        return None, "non géré"
    qty = int(qty_raw)
    if qty <= 0:
        return qty, "rupture de stock"
    if qty < 10:
        return qty, "stock faible"
    return qty, "en stock"


def _build_pass1_prompt(
    product_title: str,
    handle: str,
    description: str,
    collections: list[str],
    tags: str,
    price: str,
    nb_variants: int,
    current_meta_title: str,
    current_meta_description: str,
    matched_queries: list[str],
    opportunity_score: int,
    niche_summary: str,
    ga4_metrics: dict[str, Any],
    trend_top: list[str],
    trend_rising: list[str],
    stock_qty: int | None,
    stock_status: str,
    merchant_label: str = "",
    business_context: str = "",
    candidate_pool: list[dict[str, Any]] | None = None,
    optimization_history_block: str = "",
    realtime_text: str = "",
) -> str:
    queries_text = ", ".join(matched_queries[:5]) if matched_queries else "aucune donnée GSC"
    collections_text = ", ".join(collections) if collections else "aucune"
    today = datetime.now(UTC).strftime("%d/%m/%Y")
    current_year = datetime.now(UTC).year

    ga4_text = "non connecté"
    if ga4_metrics:
        sessions = ga4_metrics.get("sessions", 0)
        conversions = ga4_metrics.get("conversions", 0)
        revenue = ga4_metrics.get("revenue", 0.0)
        conv_rate = ga4_metrics.get("conversion_rate", 0.0)
        ga4_text = (
            f"{sessions} sessions, {conversions} conversions, "
            f"{revenue}€ revenus, taux conv. {conv_rate:.1%}"
        )

    stock_text = f"{stock_qty} unités ({stock_status})" if stock_qty is not None else stock_status

    trend_text = ""
    if trend_top:
        trend_text += f"Top tendances : {', '.join(trend_top)}. "
    if trend_rising:
        trend_text += f"En hausse : {', '.join(trend_rising)}."
    if not trend_text:
        trend_text = "aucune donnée Trends disponible"

    merchant_label_text = f"LABEL SEO MARCHAND: {merchant_label}\n" if merchant_label else ""
    business_context_text = f"{business_context}\n" if business_context else ""
    pool_block, question_block, has_pool = _format_candidate_pool(candidate_pool or [])

    if has_pool:
        keyword_instructions = (
            "ÉTAPE 1/2 — CIBLAGE À PARTIR DE DONNÉES RÉELLES.\n"
            "Une liste de mots-clés CANDIDATS RÉELS (issus de Google Search Console, "
            "DataForSEO, Google Suggest et Google Trends) t'est fournie ci-dessous avec leurs "
            "métriques observées. Ne rédige PAS encore de contenu : cela viendra à l'étape 2.\n"
            "RÈGLES DE SÉLECTION (impératif) :\n"
            "1. seo_keywords doit être composé EXCLUSIVEMENT de requêtes copiées EXACTEMENT "
            "depuis la liste CANDIDATS (même orthographe), choisies pour leur pertinence avec CE produit. "
            "Sélectionne-en 6 à 10, en privilégiant volume/impressions réels et adéquation produit.\n"
            "2. Pour chaque mot-clé sélectionné, renseigne intent_type "
            "(informational/commercial/transactional/navigational), product_fit_score (0-100) et reason. "
            "N'invente JAMAIS de demand_score/competition_score/volume : ils proviennent des données réelles.\n"
            "3. Écarte les candidats hors-sujet (ne les inclus pas). Mieux vaut 6 mots-clés pertinents "
            "que 10 approximatifs. Le mot-clé classé en premier doit cibler LE PRODUIT lui-même, "
            "jamais un accessoire/consommable/pièce détachée (ex. 'filtre', 'recharge', 'pièce') "
            "si le produit n'en est pas un.\n"
            "4. Tu peux ajouter AU PLUS 2 mots-clés longue traîne manquants SEULEMENT si une intention "
            'produit évidente n\'est couverte par aucun candidat ; marque-les avec "new": true.\n'
            "5. geo_questions (5-8) : appuie-toi en priorité sur les QUESTIONS DÉTECTÉES ci-dessous "
            "(reformulation autorisée) — ce sont de vraies recherches type ChatGPT/Google. "
            "Chaque objet : question/answer_angle/content_block_type/confidence.\n"
            "Réponds uniquement en JSON valide avec exactement ces clés : "
            "product_summary, target_customer, buying_intents (liste de strings), "
            'seo_keywords (objets avec query/intent_type/product_fit_score/reason, +"new":true si ajouté), '
            "geo_questions (objets avec question/answer_angle/content_block_type/confidence)."
        )
    else:
        # No real candidates available (e.g. brand-new shop, no GSC/DataForSEO) — fall back
        # to LLM-proposed targeting, clearly the degraded path.
        keyword_instructions = (
            "ÉTAPE 1/2 — CIBLAGE. Aucune donnée mots-clés réelle disponible pour ce produit : "
            "propose des cibles plausibles (elles seront marquées comme estimées).\n"
            "RÈGLE MOTS-CLÉS : priorité aux requêtes mid-tail (2-4 mots) réalistes en France. "
            "Les 2-3 premiers seo_keywords doivent être mid-tail. Longues traînes en fin de liste pour FAQ/GEO.\n"
            "Réponds uniquement en JSON valide avec exactement ces clés : "
            "product_summary, target_customer, buying_intents (liste de strings), "
            "seo_keywords (5-8 objets avec query/intent_type/demand_score/competition_score/product_fit_score/reason), "
            "geo_questions (5-8 objets avec question/answer_angle/content_block_type/confidence)."
        )

    return (
        f"DATE_ACTUELLE: {today} (année {current_year})\n"
        f"NICHE: {niche_summary or 'Non définie'}\n"
        f"{business_context_text}"
        f"PRODUIT: {product_title} | handle: {handle} | prix: {price or 'non renseigné'}"
        f" | {nb_variants} variante(s)\n"
        f"{merchant_label_text}"
        f"DESCRIPTION: {description[:400]}\n"
        f"COLLECTIONS: {collections_text}\n"
        f"TAGS: {tags or 'aucun'}\n"
        f"META TITLE ACTUEL: {current_meta_title or 'absent'}\n"
        f"META DESCRIPTION ACTUELLE: {current_meta_description or 'absente'}\n"
        f"REQUÊTES GSC TOP: {queries_text}\n"
        f"GA4 (90 derniers jours): {ga4_text}\n"
        f"TENDANCES GOOGLE: {trend_text}\n"
        + (f"DONNÉES TEMPS RÉEL (sourcées, recherche web du jour): {realtime_text}\n" if realtime_text else "")
        + f"STOCK: {stock_text}\n"
        f"SCORE OPPORTUNITÉ: {opportunity_score}/100\n"
        f"{pool_block}"
        f"{question_block}\n"
        f"IMPORTANT: nous sommes en {current_year}. "
        "N'utilise jamais d'années passées dans les titres, exemples ou références. "
        "Toutes les propositions doivent être actuelles et pertinentes pour l'année en cours.\n"
        + (f"{optimization_history_block}\n" if optimization_history_block else "")
        + f"\n{keyword_instructions}"
    )


_POOL_SOURCE_LABELS = {
    "gsc": "GSC",
    "dataforseo": "DataForSEO",
    "google_suggest": "Suggest",
    "trends": "Trends",
    "google_ads": "GoogleAds",
}


def _format_candidate_pool(
    candidate_pool: list[dict[str, Any]],
) -> tuple[str, str, bool]:
    """Render the real candidate pool + detected questions for the Pass 1 prompt.

    Returns (pool_block, question_block, has_pool). Each candidate line shows the
    exact query plus its real metrics so the LLM selects from observed demand.
    """
    pool = [c for c in candidate_pool if isinstance(c, dict) and str(c.get("query", "")).strip()]
    if not pool:
        return "", "", False

    lines: list[str] = []
    for idx, cand in enumerate(pool, start=1):
        query = str(cand.get("query", "")).strip()
        source = _POOL_SOURCE_LABELS.get(str(cand.get("data_source", "")), "estimé")
        metric_bits: list[str] = []
        vol = cand.get("search_volume")
        if vol is not None:
            metric_bits.append(f"{vol} rech./mois")
        if cand.get("gsc_impressions"):
            metric_bits.append(
                f"{cand.get('gsc_impressions')} impr. GSC (pos. {cand.get('gsc_position', '?')})"
            )
        if not metric_bits:
            metric_bits.append("volume à confirmer")
        lines.append(f'  #{idx} "{query}" — {source}, {", ".join(metric_bits)}')

    question_words = {q for q in _QUESTION_PREFIXES}
    questions = [
        str(c.get("query", "")).strip()
        for c in pool
        if str(c.get("query", "")).strip()
        and (
            str(c.get("query", "")).strip().lower().split()[0] in question_words
            or "?" in str(c.get("query", ""))
        )
    ]

    pool_block = "\n=== CANDIDATS MOTS-CLÉS RÉELS (sélectionne ici) ===\n" + "\n".join(lines) + "\n"
    question_block = ""
    if questions:
        question_block = (
            "\n=== QUESTIONS DÉTECTÉES (base pour geo_questions) ===\n"
            + "\n".join(f"  - {q}" for q in questions[:12])
            + "\n"
        )
    return pool_block, question_block, True


def _crawl_for_handle(
    handle: str, crawl_findings: list[dict[str, Any]] | None
) -> list[dict[str, Any]]:
    """Return crawl findings whose URL points at this product (keyed by URL only)."""
    if not handle or not crawl_findings:
        return []
    needle = f"/products/{handle}"
    return [f for f in crawl_findings if isinstance(f, dict) and needle in str(f.get("url", ""))]


def _build_pass2_retry_prompt(
    *,
    product_title: str,
    niche_summary: str,
    keywords: list[str],
    current_meta_title: str,
    current_meta_description: str,
    confirmed_facts: list[dict[str, Any]] | None = None,
    surface_plan: dict[str, Any] | None = None,
) -> str:
    """Simplified fallback prompt for Pass 2 when the main prompt returns incomplete JSON.

    Requests only the essential fields in a compact format to avoid any token overflow.
    """
    today = datetime.now(UTC).strftime("%d/%m/%Y")
    kw_str = ", ".join(f'"{q}"' for q in keywords) if keywords else "non disponible"
    facts_text = (
        "; ".join(
            f"{fact.get('key')}: {_coerce_str(fact.get('value', ''))[:100]}"
            for fact in (confirmed_facts or [])
            if isinstance(fact, dict) and fact.get("key")
        )
        or "aucun fait confirmé"
    )
    enabled_surfaces = (
        ", ".join(
            name
            for name, decision in (surface_plan or {}).items()
            if isinstance(decision, dict) and decision.get("generate")
        )
        or "metadata uniquement"
    )
    return (
        f"DATE: {today}\n"
        f"NICHE: {niche_summary or 'Non définie'}\n"
        f"PRODUIT: {product_title}\n"
        f"META TITLE ACTUEL: {current_meta_title or 'absent'}\n"
        f"META DESCRIPTION ACTUELLE: {current_meta_description or 'absente'}\n"
        f"MOTS-CLÉS SEO CIBLES: {kw_str}\n\n"
        f"FAITS SHOPIFY AUTORISÉS: {facts_text}\n"
        f"SURFACES AUTORISÉES: {enabled_surfaces}\n"
        "N'utilise aucune affirmation produit qui ne soit soutenue par un fait autorisé. "
        "Retourne une valeur vide pour chaque surface non autorisée.\n\n"
        "Génère en JSON valide UNIQUEMENT ces clés (ne rien omettre) :\n"
        "proposed_meta_title (≤70 car.), proposed_meta_description (≤160 car.), "
        "proposed_product_title_if_different, proposed_product_description (2-3 phrases), "
        "proposed_faq (3 objets {q, a}), proposed_geo_answer_block (1 phrase), "
        "proposed_blog_title, proposed_blog_outline (3 strings), proposed_blog_intro (1 phrase), "
        "proposed_blog_ideas (5 objets {title, target_keyword, intro, outline}), "
        "recommended_content_actions (2 strings), facts_used (2 strings), "
        "facts_missing (1 string), claims_used (liste d'objets {claim, fact_keys}), "
        "confidence (high/medium/low)."
    )


def _build_pass2_prompt(
    *,
    product_title: str,
    handle: str,
    niche_summary: str,
    pass1: dict[str, Any],
    enriched_keywords: list[dict[str, Any]],
    serp_intel: dict[str, dict[str, Any]],
    crawl_findings: list[dict[str, Any]],
    current_meta_title: str,
    current_meta_description: str,
    merchant_label: str = "",
    ga4_metrics: dict[str, Any] | None = None,
    domain_competitors: list[dict[str, Any]] | None = None,
    confirmed_facts: list[dict[str, Any]] | None = None,
    missing_facts: list[dict[str, Any]] | None = None,
    surface_plan: dict[str, Any] | None = None,
    forbidden_phrases: list[str] | None = None,
    business_context: str = "",
    cannibalization_hint: dict[str, Any] | None = None,
    eeat_signals: list[dict[str, Any]] | None = None,
    product_images: list[dict[str, Any]] | None = None,
    competitor_crawl_summary: str | None = None,
    optimization_history_block: str = "",
) -> str:
    """Build the pass-2 (content) prompt with strict per-field rules.

    Each external signal (DataForSEO keywords, GSC performance, GA4 metrics, SERP/PAA,
    competitor titles, crawl findings) is surfaced and the LLM is bound by mandatory
    usage rules — the merchant pays for that data, so every field of the content pack
    must reference it.
    """
    today = datetime.now(UTC).strftime("%d/%m/%Y")
    current_year = datetime.now(UTC).year

    sorted_kws = sorted(
        [k for k in enriched_keywords if isinstance(k, dict)],
        key=lambda k: (
            int(k.get("target_rank", 999) or 999),
            -float(k.get("priority_score", k.get("demand_score", 0)) or 0),
        ),
    )
    top_kws = sorted_kws[:8]
    top_queries = [str(k.get("query", "")) for k in top_kws[:5] if k.get("query")]
    geo_question_lines = [
        f"  - {question.get('question', '')} | angle: {question.get('answer_angle', '')}"
        for question in _coerce_geo_questions(pass1.get("geo_questions", []))
        if question.get("question")
    ]

    # ── Targeted keywords (real volume/difficulty + GSC perf inline) ────────
    target_lines: list[str] = []
    for idx, kw in enumerate(top_kws, start=1):
        vol = kw.get("search_volume")
        vol_text = f"{vol}/mois" if vol is not None else "volume n/a"
        line = (
            f'  #{idx} "{kw.get("query", "")}" [{kw.get("target_role", "supporting")}] '
            f"— priorité {kw.get('priority_score', '?')}/100, {vol_text}, "
            f"difficulté {kw.get('competition_score', '?')}/100 "
            f"({kw.get('difficulty_source', 'free_estimated')}), "
            f"intent {kw.get('intent_type', '?')}"
        )
        # Surface GSC perf for keywords already ranking — the LLM must defend these positions.
        gsc_impr = kw.get("gsc_impressions")
        gsc_pos = kw.get("gsc_position")
        gsc_clicks = kw.get("gsc_clicks")
        if gsc_impr or gsc_pos is not None:
            line += (
                f"\n      └ GSC réel: {gsc_impr or 0} impressions, "
                f"{gsc_clicks or 0} clics, position moyenne {gsc_pos if gsc_pos is not None else '?'}"
            )
        cpc = kw.get("cpc")
        if cpc:
            line += f" | CPC AdWords {cpc}€ (valeur commerciale)"
        if kw.get("serp_evidence"):
            line += " | SERP/PAA vérifié"
        target_lines.append(line)
    related_ideas = [str(k.get("query", "")) for k in sorted_kws[8:] if k.get("query")]

    # ── SERP intelligence (PAA, competitor angles, featured snippet) ────────
    product_keys = [str(k.get("query", "")).strip().lower() for k in sorted_kws if k.get("query")]
    paa_questions: list[str] = []
    competitor_lines: list[str] = []
    featured_snippets: list[str] = []
    for key in product_keys:
        intel = serp_intel.get(key)
        if not intel:
            continue
        for q in intel.get("paa", []):
            if q not in paa_questions:
                paa_questions.append(q)
        comps = intel.get("top_competitors", [])[:3]
        if comps:
            joined = "; ".join(f'{c.get("domain", "")} — "{c.get("title", "")}"' for c in comps)
            competitor_lines.append(f'"{key}": {joined}')
        fs = intel.get("featured_snippet")
        if fs and fs not in featured_snippets:
            featured_snippets.append(fs)

    # ── GA4 page perf (organic traffic + conversions for THIS product page) ──
    ga4_line = ""
    if ga4_metrics:
        sessions = ga4_metrics.get("sessions") or ga4_metrics.get("organic_sessions")
        conversions = ga4_metrics.get("conversions") or ga4_metrics.get("conversion_count")
        engagement = ga4_metrics.get("engagement_rate") or ga4_metrics.get("avg_engagement_time")
        bits: list[str] = []
        if sessions is not None:
            bits.append(f"{sessions} sessions organiques (90j)")
        if conversions is not None:
            bits.append(f"{conversions} conversions")
        if engagement is not None:
            bits.append(f"engagement {engagement}")
        if bits:
            ga4_line = "  " + " | ".join(bits)

    # ── Crawl findings ──────────────────────────────────────────────────────
    crawl_lines = [
        f"  - {f.get('issue_type', '?')} ({f.get('severity', '?')}): {f.get('detail', '')}"
        for f in crawl_findings[:8]
    ]
    fact_lines = [
        f"  - {fact.get('key')}: {_coerce_str(fact.get('value', ''))[:180]} "
        f"[source={fact.get('source', 'shopify_snapshot')}]"
        for fact in (confirmed_facts or [])
        if isinstance(fact, dict) and fact.get("key")
    ]
    missing_fact_lines = [
        f"  - {fact.get('key')}: {fact.get('label', '')}"
        for fact in (missing_facts or [])
        if isinstance(fact, dict) and fact.get("key")
    ]
    surface_lines = [
        f"  - {surface}: {'GÉNÉRER' if decision.get('generate') else 'NE PAS GÉNÉRER'} "
        f"({decision.get('reason', '')})"
        for surface, decision in (surface_plan or {}).items()
        if isinstance(decision, dict)
    ]

    merchant_label_text = f"LABEL SEO MARCHAND: {merchant_label}" if merchant_label else ""

    parts: list[str] = [
        f"DATE_ACTUELLE: {today} (année {current_year})",
        f"NICHE: {niche_summary or 'Non définie'}",
        f"PRODUIT: {product_title} | handle: {handle}",
        merchant_label_text,
        business_context,
        f"META TITLE ACTUEL: {current_meta_title or 'absent'}",
        f"META DESCRIPTION ACTUELLE: {current_meta_description or 'absente'}",
        "",
        "COMPRÉHENSION (étape 1):",
        f"  Résumé: {pass1.get('product_summary', '')}",
        f"  Client cible: {pass1.get('target_customer', '')}",
        f"  Intentions d'achat: {', '.join(pass1.get('buying_intents', []) or [])}",
    ]

    if target_lines:
        parts.append("\n=== TOP MOTS-CLÉS CIBLES (à utiliser en priorité) ===")
        parts.extend(target_lines)
    if related_ideas:
        parts.append(
            "\nAUTRES MOTS-CLÉS LIÉS (utilise-les seulement dans la surface qui correspond à leur intention): "
            + ", ".join(related_ideas[:15])
        )
    if ga4_line:
        parts.append("\n=== GA4 PERFORMANCE PAGE PRODUIT (90 derniers jours) ===")
        parts.append(ga4_line)
    if competitor_lines:
        parts.append("\n=== CONCURRENTS SERP (titres réels — différencie-toi, ne copie pas) ===")
        parts.extend(f"  {c}" for c in competitor_lines)
    if featured_snippets:
        parts.append(
            "Extraits SERP observés à utiliser seulement comme contexte: "
            + " | ".join(featured_snippets[:3])
        )
    if paa_questions:
        parts.append("\n=== QUESTIONS PAA Google (à REPRENDRE dans proposed_faq) ===")
        parts.extend(f"  - {q}" for q in paa_questions[:10])
    if geo_question_lines:
        parts.append("\n=== QUESTIONS GEO/IA DÉTECTÉES (base obligatoire pour proposed_faq) ===")
        parts.extend(geo_question_lines[:10])
    if crawl_lines:
        parts.append("\n=== PROBLÈMES TECHNIQUES DÉTECTÉS (crawl) ===")
        parts.extend(crawl_lines)
    if competitor_crawl_summary:
        parts.append("\n=== BENCHMARK STRUCTUREL CONCURRENTS CRAWLÉS ===")
        parts.append(competitor_crawl_summary)
    parts.append("\n=== FAITS PRODUIT CONFIRMÉS — SEULE SOURCE AUTORISÉE POUR LES AFFIRMATIONS ===")
    parts.extend(
        fact_lines or ["  - aucun fait produit confirmé : ne génère aucun contenu factuel"]
    )
    if missing_fact_lines:
        parts.append("\nFAITS MANQUANTS — NE PAS LES AFFIRMER :")
        parts.extend(missing_fact_lines)
    if surface_lines:
        parts.append("\n=== PLAN DES SURFACES À PRODUIRE ===")
        parts.extend(surface_lines)
    if product_images:
        parts.append("\n=== IMAGES PRODUIT (pour proposed_image_alts) ===")
        for i, img in enumerate(product_images):
            alt_actuel = img.get("current_alt") or "(vide)"
            parts.append(f"  [{i + 1}] id={img['id']} | alt actuel: {alt_actuel}")
    if forbidden_phrases:
        parts.append("\n=== FORMULATIONS INTERDITES ===")
        parts.extend(f"  - {phrase}" for phrase in forbidden_phrases)

    if optimization_history_block:
        parts.append(optimization_history_block)

    if eeat_signals:
        from app.market_analysis import eeat as _eeat  # noqa: PLC0415

        eeat_block = _eeat.format_prompt_block(eeat_signals)
        if eeat_block:
            parts.append("\n" + eeat_block)

    if cannibalization_hint:
        head = str(cannibalization_hint.get("cluster_head") or "")
        pivots = cannibalization_hint.get("pivot_suggestions") or []
        parts.append("\n=== CONFLIT DE CANNIBALISATION DÉTECTÉ ===")
        parts.append(
            f'  Le produit principal positionné sur "{head}" est un autre produit du catalogue.'
        )
        parts.append(
            "  Ce produit DOIT viser une variante longue traîne plus spécifique, pas le mot-clé tête."
        )
        if pivots:
            parts.append("  Pivots suggérés (utiliser un de ceux-ci comme angle principal):")
            parts.extend(f'    - "{p}"' for p in pivots[:5])
        else:
            parts.append(
                "  Aucun pivot longue traîne disponible — propose une intention plus spécifique"
                " liée à un fait confirmé (matériau, taille, usage particulier)."
            )

    # ── Domain-level competitors (DataForSEO Competitors Domain) ────────────
    if domain_competitors:
        parts.append("\n=== CONCURRENTS DE DOMAINE PRIORITAIRES (DataForSEO) ===")
        parts.append(
            "Ces sites se positionnent sur les mêmes mots-clés que la boutique. Utilise-les pour différencier."
        )
        for comp in domain_competitors[:10]:
            domain = comp.get("domain", "")
            angle = comp.get("content_angle", "")
            strength = comp.get("estimated_strength", 0)
            parts.append(f"  • {domain} (force {strength}/100) — {angle}")

    # ── Strict per-field rules — every paid signal above MUST be used ──────
    top_kw_1 = top_queries[0] if top_queries else "le mot-clé principal"
    top_kw_list = ", ".join(f'"{q}"' for q in top_queries) if top_queries else "—"
    product_page_queries = [
        str(kw.get("query", ""))
        for kw in sorted_kws
        if kw.get("keyword_surface") == "product_page" and kw.get("query")
    ][:5]
    blog_queries = [
        str(kw.get("query", ""))
        for kw in sorted_kws
        if kw.get("keyword_surface") == "blog" and kw.get("query")
    ][:5]
    faq_queries = [
        str(kw.get("query", ""))
        for kw in sorted_kws
        if kw.get("keyword_surface") == "faq" and kw.get("query")
    ][:5]

    parts.append(
        f"\n═══════════════════════════════════════════════════════════════════\n"
        f"ÉTAPE 2/2 — RÈGLES STRICTES PAR CHAMP (RESPECT OBLIGATOIRE)\n"
        f"═══════════════════════════════════════════════════════════════════\n"
        f"\nTOP 5 mots-clés à utiliser : {top_kw_list}\n"
        f"Mots-clés page produit : {', '.join(product_page_queries) or 'aucun'}\n"
        f"Mots-clés blog/guide : {', '.join(blog_queries) or 'aucun'}\n"
        f"Mots-clés FAQ : {', '.join(faq_queries) or 'aucun'}\n"
        f"Les cibles sont classées selon demande, concurrence, adéquation produit et niveau de preuve. "
        f"Les mots-clés guident l'intention, jamais des affirmations. "
        f"Utilise uniquement les faits confirmés pour parler du produit.\n"
        f"\n▶ proposed_meta_title (45-60 caractères) :\n"
        f'   • Contient naturellement le mot-clé #1 ("{top_kw_1}") OU une variation proche, placé le plus tôt possible dans le titre.\n'
        f"   • Ne renvoie JAMAIS le titre produit tel quel : reformule avec le mot-clé en tête et un bénéfice court.\n"
        f"   • Chaque mot-clé primary/secondary du TOP 5 doit apparaître dans proposed_meta_title OU proposed_meta_description.\n"
        f"   • Différenciant vs CONCURRENTS SERP et TITRES SEO CONCURRENTS listés : reprends l'angle gagnant mais formule-le autrement (jamais copier).\n"
        f"\n▶ proposed_meta_description (120-160 caractères) :\n"
        f"   • Contient naturellement le mot-clé #1 ; ajoute une cible secondaire seulement si la phrase reste utile et lisible.\n"
        f"   • Doit compléter proposed_meta_title pour couvrir les mots-clés primary/secondary absents du titre.\n"
        f"   • Bénéfice produit ou CTA seulement s'il est confirmé par les données produit fournies.\n"
        f"   • Inspire-toi des META DESCRIPTIONS CONCURRENTES (angle, bénéfice mis en avant) sans reprendre leur formulation ni leurs promesses non vérifiées.\n"
        f"\n▶ proposed_image_alts (tableau JSON — UNE ENTRÉE POUR CHAQUE image listée dans IMAGES PRODUIT) :\n"
        f'   • Chaque objet : {{"image_id": "<id exact>", "proposed_alt": "<alt proposé>"}}\n'
        f"   • Réutilise l'`image_id` EXACT de chaque image listée ; n'en oublie aucune.\n"
        f"   • L'alt décrit d'abord CE QUE MONTRE L'IMAGE (couleur, matière, angle, mise en situation), "
        f"comme pour un lecteur d'écran — ce n'est pas un slot à mot-clé.\n"
        f"   • CHAQUE alt doit être DIFFÉRENT des autres : varie l'angle décrit (face, étiquette, "
        f"détail, mise en situation, échelle…).\n"
        f"   • Intègre un mot-clé du TOP 5 naturellement dans 1 ou 2 alts MAXIMUM ; les autres restent purement descriptifs. "
        f'Jamais le schéma "titre produit – mot-clé".\n'
        f"   • proposed_alt ≤ 125 caractères, jamais de texte générique.\n"
        f"   • Si aucune image n'est fournie dans IMAGES PRODUIT : retourner [].\n"
        f"\n▶ proposed_product_description (200-300 mots, plusieurs paragraphes) :\n"
        f"   • Si la surface est marquée NE PAS GÉNÉRER, retourne une chaîne vide.\n"
        f"   • Doit intégrer le pack GEO dans la description : réponse courte, définition extractible, faits rapides et tableau comparatif si disponibles.\n"
        f"   • Couvre l'intention principale puis des sujets secondaires uniquement lorsqu'ils apportent une information vérifiée.\n"
        f"   • Première phrase peut contenir le mot-clé #1 si cela reste naturel.\n"
        f"   • Explique seulement les caractéristiques et usages confirmés dans le contexte produit.\n"
        f"   • Vise la longueur médiane du BENCHMARK STRUCTUREL CONCURRENTS et couvre les SOUS-THÈMES / H2 CONCURRENTS pertinents (matériaux, usage, entretien…) lorsqu'un fait produit confirmé existe.\n"
        f"\n▶ proposed_faq (5-8 entrées) :\n"
        f"   • Génère toujours une FAQ dès qu'un mot-clé principal existe.\n"
        f"   • Utilise en priorité les QUESTIONS GEO/IA DÉTECTÉES, puis les QUESTIONS PAA Google, puis les thèmes des SOUS-THÈMES / H2 CONCURRENTS.\n"
        f"   • Si une réponse manque de preuve produit, formule une réponse prudente et ajoute le fait manquant dans facts_missing.\n"
        f"   • Utilise les mots-clés naturellement, sans répétition forcée dans chaque question.\n"
        f"   • Réponses 2-4 phrases factuelles ; pas de blabla marketing.\n"
        f"\n▶ proposed_geo_answer_block :\n"
        f"   • Si la surface est marquée NE PAS GÉNÉRER, retourne une chaîne vide.\n"
        f"   • Fournit une réponse courte uniquement à partir des faits confirmés.\n"
        f"   • Si un EXTRAIT REPRIS PAR GOOGLE est fourni, inspire-toi de son format court et extractible (sans copier le texte).\n"
        f"\n▶ proposed_blog_title :\n"
        f"   • Si la surface blog est marquée NE PAS GÉNÉRER, retourne title/intro vides et outline vide.\n"
        f"   • S'il est généré, contient un mot-clé longue traîne ou un intent informationnel depuis la liste.\n"
        f"   • Différent des titres concurrents SERP ET des domaines concurrents listés.\n"
        f"\n▶ proposed_blog_intro (2-3 phrases) :\n"
        f"   • Seulement si le blog est généré : introduit naturellement l'intention ciblée.\n"
        f"\n▶ proposed_blog_outline (5-7 sections H2) :\n"
        f"   • Seulement si le blog est généré : chaque H2 couvre une intention ou question pertinente.\n"
        f"   • Structure-toi à partir des SOUS-THÈMES / H2 CONCURRENTS et des QUESTIONS PAA pour couvrir les angles qui rankent, reformulés à ta façon.\n"
        f"   • Si des concurrents sont présents, différencie le cadrage sans affirmer ce qu'ils ne traitent pas.\n"
        f"   • N'inclus JAMAIS de H2 qui présente le produit sous un angle négatif (ex : "
        f"« Inconvénients », « Points faibles », « Pourquoi hésiter », prix présenté comme un "
        f"défaut) — même si un concurrent en a un : reformule l'angle en quelque chose de "
        f"constructif (ex : « Pour qui est-ce fait ? », « Ce qu'il faut savoir avant d'acheter »).\n"
        f"\n▶ proposed_blog_ideas :\n"
        f"   • Propose exactement 5 idées d'articles.\n"
        f"   • Chaque objet contient title, target_keyword, intro, outline (5-7 H2).\n"
        f"   • Chaque idée cible un mot-clé différent ou une intention très liée aux mots-clés sélectionnés.\n"
        f"   • Appuie-toi sur les SOUS-THÈMES / H2 CONCURRENTS et les QUESTIONS PAA pour identifier des angles d'articles à fort potentiel.\n"
        f"   • Ces idées doivent pouvoir être générées en article séparé par le marchand.\n"
        f"\n▶ recommended_content_actions :\n"
        f"   • Si des CONCURRENTS DE DOMAINE sont listés, propose au plus une analyse comparative fondée sur les titres observés ;\n"
        f"     n'affirme jamais qu'un sujet est absent ou qu'un produit est supérieur sans preuve fournie.\n"
        f"\n▶ facts_used (CRITIQUE — c'est ta trace d'utilisation) :\n"
        f"   • Liste, par champ, les mots-clés/PAA/concurrents effectivement utilisés.\n"
        f'   • Format : ["meta_title: <kw>", "meta_desc: <kw>", "description: <kw/utilité>", "faq: <PAA>", "blog: <intent>", "actions: <observation>"]\n'
        f"   • Si tu n'as pas pu utiliser un signal payant (GA4, GSC, concurrent), explique-le dans facts_missing.\n"
        f"\n▶ claims_used (OBLIGATOIRE pour tout texte généré) :\n"
        f'   • Liste chaque affirmation vérifiable au format {{"claim": "...", "fact_keys": ["description", "materials"]}}.\n'
        f"   • `fact_keys` ne peut contenir que des clés listées dans FAITS PRODUIT CONFIRMÉS.\n"
        f"   • Si une affirmation n'a aucune preuve confirmée, retire-la du texte et ajoute le manque dans facts_missing.\n"
        f"\n▶ facts_missing : signaux absents ou inexploitables (ex : 'pas de PAA pour ce mot-clé', 'concurrents domaine absents').\n"
        f"\n▶ confidence : high (≥80% des règles respectées) | medium (≥50%) | low (<50%).\n"
        f"\nCONTRAINTES GLOBALES :\n"
        f"- Nous sommes en {current_year}. JAMAIS d'années passées dans titres ou exemples.\n"
        f"- N'invente JAMAIS de faits (matériau, dimensions, certifications) — liste-les dans facts_missing.\n"
        f"- Ne reprends aucune formulation listée dans FORMULATIONS INTERDITES.\n"
        f"- N'ajoute jamais un champ uniquement pour répéter un mot-clé : un contenu générique doit rester vide.\n"
        f"- Priorise les mots-clés à fort volume (>500/mois) dans les champs visibles seulement si l'intention correspond au produit.\n"
        f"- Les requêtes DIY/gratuites/tricot/crochet ne doivent JAMAIS être la cible principale de la page produit premium ; utilise-les seulement en blog indirect si le blog est autorisé.\n"
        f"- Les requêtes 'meilleur/meilleure/comment choisir/avis/comparatif' vont en blog ou guide, pas en primary keyword produit.\n"
        f"- Si GSC réel montre un keyword en position 4-20 et que le blog est autorisé, traite cette intention en priorité.\n"
        f"- Si des CONCURRENTS DE DOMAINE sont listés : différencie uniquement les champs autorisés de leurs formulations.\n"
        f"- Utilise les insights de crawl concurrent uniquement comme benchmark structurel : FAQ, answer block, schema, maillage, structure H2.\n"
        f"- Ne copie jamais le wording concurrent, n'infère jamais de faits produit depuis les concurrents, ne reprends aucune promesse concurrente.\n"
        f"\n▶ proposed_geo_definition_block (≈25 mots) :\n"
        f'   • Format extractible par IA : "{{Produit}} est {{catégorie}} qui {{bénéfice vérifié}}."\n'
        f"   • Première phrase utilisable telle quelle dans un AI Overview / extrait Perplexity.\n"
        f"   • Uniquement des faits confirmés ; pas d'adjectifs marketing.\n"
        f"\n▶ proposed_geo_quick_facts (liste de 3-5 puces) :\n"
        f"   • Phrases nominales courtes (≤15 mots), auto-suffisantes hors contexte.\n"
        f"   • Chaque puce = un fait extractible par un LLM tiers (ChatGPT, Perplexity).\n"
        f'   • Exemple : "Fabriqué en France depuis 2010" plutôt que "De qualité supérieure".\n'
        f"   • Liste vide si moins de 3 faits confirmés disponibles.\n"
        f"\n▶ proposed_geo_comparison_table (liste d'objets {{critère, valeur}}) :\n"
        f"   • Active SEULEMENT si ≥3 critères factuels confirmés (dimensions, matériau, compatibilité, garantie…).\n"
        f"   • Liste vide sinon ; n'invente pas de critères.\n"
        f"\nRéponds UNIQUEMENT en JSON valide avec ces clés exactes : "
        f"proposed_meta_title, proposed_meta_description, proposed_product_title_if_different, "
        f"proposed_product_description, proposed_faq (5-8 objets {{q, a}}), "
        f"proposed_geo_answer_block (40-80 mots, factuel, cite 1 mot-clé), "
        f"proposed_geo_definition_block (≈25 mots, format extractible IA), "
        f"proposed_geo_quick_facts (liste strings courtes), "
        f"proposed_geo_comparison_table (liste objets {{critère, valeur}}), "
        f"proposed_blog_title, proposed_blog_outline (liste strings), proposed_blog_intro, "
        f"proposed_blog_ideas (5 objets {{title, target_keyword, intro, outline}}), "
        f"recommended_content_actions (liste strings), facts_used (liste strings), "
        f"facts_missing (liste strings), claims_used (liste d'objets {{claim, fact_keys}}), "
        f"confidence (high/medium/low)."
    )

    return "\n".join(p for p in parts if p != "")


_GENERIC_DOMAINS = frozenset(
    {
        "amazon.fr",
        "amazon.com",
        "amazon.co.uk",
        "amazon.de",
        "amazon.es",
        "amazon.it",
        "ebay.fr",
        "ebay.com",
        "ebay.co.uk",
        "fnac.com",
        "cdiscount.com",
        "rakuten.fr",
        "aliexpress.com",
        "wish.com",
        "wikipedia.org",
        "fr.wikipedia.org",
        "en.wikipedia.org",
        "youtube.com",
        "youtu.be",
        "facebook.com",
        "instagram.com",
        "pinterest.com",
        "tiktok.com",
        "twitter.com",
        "reddit.com",
        "google.com",
        "google.fr",
        "leboncoin.fr",
        "vinted.fr",
        "manomano.fr",
        "boulanger.com",
        "darty.com",
        "ldlc.com",
        "decathlon.fr",
        "maxizoo.fr",
        "zooplus.fr",
        "bitiba.fr",
        "animalis.com",
        "truffaut.com",
        "jardiland.com",
        "wanimo.com",
    }
)

_RETAILER_BRAND_QUERY_MARKERS = frozenset(
    {
        "amazon",
        "cdiscount",
        "decathlon",
        "maxi zoo",
        "maxizoo",
        "zooplus",
        "bitiba",
        "animalis",
        "truffaut",
        "jardiland",
        "wanimo",
    }
)


def _filter_domain_competitors(
    signals: list[dict[str, Any]],
    *,
    limit: int = 10,
) -> list[dict[str, Any]]:
    """Remove generic marketplaces and keep the top `limit` by estimated_strength."""
    filtered = [
        s
        for s in signals
        if s.get("detected_from") == "paid_provider"
        and str(s.get("domain", "")).strip().lower() not in _GENERIC_DOMAINS
    ]
    return sorted(filtered, key=lambda s: s.get("estimated_strength", 0), reverse=True)[:limit]


def _format_business_profile_context(profile: dict[str, Any] | None) -> str:
    """Return a compact validated business profile block for LLM prompts."""
    if not isinstance(profile, dict):
        return ""

    def _take(values: Any, limit: int = 6) -> list[str]:
        return [
            _coerce_str(value).strip()
            for value in _coerce_list(values)[:limit]
            if _coerce_str(value).strip()
        ]

    content_style = (
        profile.get("content_style") if isinstance(profile.get("content_style"), dict) else {}
    )
    personas = (
        profile.get("target_personas") if isinstance(profile.get("target_personas"), list) else []
    )
    persona_lines = []
    for persona in personas[:3]:
        if not isinstance(persona, dict):
            continue
        name = _coerce_str(persona.get("name", "")).strip()
        need = _coerce_str(persona.get("main_need", "")).strip()
        trigger = _coerce_str(persona.get("buying_trigger", "")).strip()
        if name or need or trigger:
            persona_lines.append(f"{name}: besoin={need}; déclencheur={trigger}".strip())

    lines = [
        "=== PROFIL ENTREPRISE VALIDÉ — CONTEXTE STRATÉGIQUE À RESPECTER ===",
        f"Marque: {_coerce_str(profile.get('brand_name', '')).strip() or 'non définie'}",
        f"Résumé niche: {_coerce_str(profile.get('niche_summary', '')).strip() or 'non défini'}",
        f"Voix de marque: {_coerce_str(profile.get('brand_voice', '')).strip() or 'non définie'}",
        f"Ton éditorial: {_coerce_str(content_style.get('tone', '')).strip() or 'non défini'}",
    ]

    if persona_lines:
        lines.append("Personas prioritaires: " + " | ".join(persona_lines))
    key_themes = _take(profile.get("key_themes"), 8)
    if key_themes:
        lines.append("Thèmes éditoriaux prioritaires: " + ", ".join(key_themes))
    vocabulary_to_use = _take(content_style.get("vocabulary_to_use"), 8)
    if vocabulary_to_use:
        lines.append("Vocabulaire à utiliser: " + ", ".join(vocabulary_to_use))
    vocabulary_to_avoid = _take(content_style.get("vocabulary_to_avoid"), 8)
    if vocabulary_to_avoid:
        lines.append("Vocabulaire à éviter: " + ", ".join(vocabulary_to_avoid))
    competitor_domains = _take(profile.get("competitor_domains"), 10)
    if competitor_domains:
        lines.append("Concurrents connus: " + ", ".join(competitor_domains))
    competitor_insights = _take(profile.get("competitor_insights"), 5)
    if competitor_insights:
        lines.append("Observations concurrentielles: " + " | ".join(competitor_insights))
    content_gaps = _take(profile.get("content_gaps"), 5)
    if content_gaps:
        lines.append("Lacunes de contenu à exploiter: " + " | ".join(content_gaps))
    internal_links = _take(profile.get("internal_link_priorities"), 8)
    if internal_links:
        lines.append("Priorités de maillage interne: " + ", ".join(internal_links))

    lines.append(
        "Utilise ce contexte pour choisir les angles, la voix, les différenciations et les sujets support, "
        "mais n'en déduis jamais des faits produit non confirmés."
    )
    return "\n".join(lines)


def _find_parent_keyword_data(
    query: str,
    all_keywords: list[dict[str, Any]],
    signals_by_keyword: dict[str, Any],
) -> tuple[int | None, str | None]:
    """Find the broadest sibling keyword that shares ≥2 content words and has real volume.

    Returns (parent_volume, parent_query). Cheap heuristic — no extra API calls.
    Useful when DataForSEO has no data for a long-tail variation but does for its parent.
    """
    query_words = _content_words(query)
    if len(query_words) < 2:
        return None, None
    best_vol = 0
    best_query: str | None = None
    for kw in all_keywords:
        if not isinstance(kw, dict):
            continue
        other_query = str(kw.get("query", "")).strip()
        if not other_query or other_query.lower() == query.lower():
            continue
        other_words = _content_words(other_query)
        # Parent must share words with our query AND be shorter (broader)
        if len(other_words & query_words) < 2 or len(other_words) >= len(query_words):
            continue
        # Fetch the other keyword's real volume from the signal map
        sig = signals_by_keyword.get(other_query.lower())
        vol = sig.get("search_volume") if sig else None
        if vol and vol > best_vol:
            best_vol = vol
            best_query = other_query
    return (best_vol or None, best_query)


def _apply_signals_to_keywords(
    seo_keywords: list[dict[str, Any]],
    signals: list[KeywordSignal],
) -> list[dict[str, Any]]:
    """Merge enriched KeywordSignal data back into the LLM-shaped keyword dicts.

    The frontend consumes the LLM shape (query, demand_score, …) and now also
    reads the normalised fields (search_volume, cpc, ads_competition, source,
    difficulty_source) directly from the same object.
    """
    by_keyword: dict[str, KeywordSignal] = {
        str(s.get("keyword", "")).strip().lower(): s for s in signals
    }
    out: list[dict[str, Any]] = []
    for kw in seo_keywords:
        if not isinstance(kw, dict):
            continue
        merged = dict(kw)
        key = str(merged.get("query", "")).strip().lower()
        sig = by_keyword.get(key)
        # Skip "empty" DataForSEO signals — when the provider returns the keyword but
        # with no measurable data, the merchant gets the LLM hallucination labelled
        # "DataForSEO" which is misleading. Treat as no signal in that case.
        if sig and sig.get("source") == "dataforseo":
            has_dfs_data = (
                sig.get("search_volume") is not None
                or sig.get("cpc") is not None
                or sig.get("ads_competition") is not None
            )
            if not has_dfs_data:
                sig = None

        # Parent-keyword fallback: if this keyword has no real data, look for
        # a broader keyword in the SAME list that does — its volume becomes
        # an upper-bound estimate. Cheap (no extra API call) and transparent.
        if not sig and not merged.get("search_volume"):
            parent_vol, parent_query = _find_parent_keyword_data(
                merged.get("query", ""), seo_keywords, by_keyword
            )
            if parent_vol is not None and parent_query:
                merged["search_volume_estimated_ceiling"] = parent_vol
                merged["estimated_from_parent"] = parent_query
                # Map the parent volume to a demand score, lowered one bucket to reflect
                # that the long-tail variation will capture only a fraction of parent traffic.
                merged["demand_score"] = max(_volume_bucket(parent_vol) - 15, 5)
                merged["data_source"] = "parent_estimated"
                merged.setdefault("notes", []).append(
                    f"Volume estimé ≤ {parent_vol}/mois (extrapolé depuis « {parent_query} »)"
                )

        if sig:
            # Real free signals override LLM estimates when available
            if sig.get("source") == "gsc":
                impressions = sig.get("impressions") or 0
                merged["demand_score"] = _impressions_bucket(int(impressions))
                merged["competition_score"] = int(
                    sig.get("difficulty_score", merged.get("competition_score", 50))
                )
                merged["gsc_impressions"] = sig.get("impressions")
                merged["gsc_clicks"] = sig.get("clicks")
                merged["gsc_position"] = sig.get("avg_position")
            # Paid-provider overrides (DataForSEO) — replace estimates with real volume/CPC
            if sig.get("source") == "dataforseo" and sig.get("search_volume") is not None:
                merged["demand_score"] = _volume_bucket(int(sig["search_volume"]))
                merged["competition_score"] = int(
                    sig.get("difficulty_score", merged.get("competition_score", 50))
                )
            # Only real-data sources upgrade provenance. A Google Suggest / Trends
            # candidate keeps its data_source when no stronger signal is found, so
            # the UI never mislabels a real suggestion as "llm_estimated".
            sig_source = sig.get("source", "llm_estimated")
            if sig_source in ("gsc", "dataforseo", "google_ads"):
                merged["data_source"] = sig_source
            else:
                merged.setdefault("data_source", sig_source)
            merged["difficulty_source"] = sig.get("difficulty_source", "free_estimated")
            # Never null out a real volume/CPC already carried by the candidate.
            if sig.get("search_volume") is not None:
                merged["search_volume"] = sig["search_volume"]
            else:
                merged.setdefault("search_volume", None)
            if sig.get("cpc") is not None:
                merged["cpc"] = sig["cpc"]
            else:
                merged.setdefault("cpc", None)
            if sig.get("ads_competition") is not None:
                merged["ads_competition"] = sig["ads_competition"]
            else:
                merged.setdefault("ads_competition", None)
            merged["confidence"] = sig.get("confidence", merged.get("confidence", "low"))
            if sig.get("notes"):
                merged["notes"] = sig["notes"]
            else:
                merged.setdefault("notes", [])
        else:
            merged.setdefault("data_source", "llm_estimated")
            merged.setdefault("difficulty_source", "free_estimated")
            merged.setdefault("search_volume", None)
            merged.setdefault("cpc", None)
            merged.setdefault("ads_competition", None)
        out.append(merged)
    return out


_FR_STOP_WORDS = frozenset(
    "de du la le les des pour avec sans sur par en au aux un une et ou à dans que qui ne pas"
    " se ce cet cette ces mon ma mes ton ta tes son sa ses notre nos votre vos leur leurs"
    " je tu il elle nous vous ils elles".split()
)


def _content_words(text: str) -> frozenset[str]:
    """Extract meaningful lowercase words (≥3 chars, non-stop) from a keyword string."""
    return frozenset(
        w
        for w in re.findall(r"[a-zàâäéèêëîïôùûüç]+", text.lower())
        if len(w) >= 3 and w not in _FR_STOP_WORDS
    )


def _content_word_sequence(text: str) -> list[str]:
    """Extract meaningful lowercase words while preserving order."""
    return [
        w
        for w in re.findall(r"[a-zàâäéèêëîïôùûüç]+", text.lower())
        if len(w) >= 3 and w not in _FR_STOP_WORDS
    ]


def _content_word_count(text: str) -> int:
    """Count meaningful words while preserving repetitions for length checks."""
    return sum(
        1
        for word in re.findall(r"[a-zàâäéèêëîïôùûüç]+", text.lower())
        if len(word) >= 3 and word not in _FR_STOP_WORDS
    )


def _domain_to_keyword_marker(domain: str) -> str:
    """Convert a domain into a rough brand marker for keyword filtering."""
    host = _normalize_domain_value(domain)
    if not host:
        return ""
    parts = host.split(".")
    label = parts[1] if parts and parts[0] == "www" and len(parts) > 1 else parts[0]
    return label.replace("-", " ").strip()


def _normalize_domain_value(value: str) -> str:
    """Normalize a URL/domain string to a bare lowercase host."""
    raw = str(value or "").strip().lower()
    if not raw:
        return ""
    if raw.startswith("sc-domain:"):
        raw = raw.removeprefix("sc-domain:")
    if "://" in raw:
        raw = urlsplit(raw).netloc
    return raw.split("/")[0].split(":")[0].removeprefix("www.")


def _drop_excluded_signals(
    signals: list[dict[str, Any]], excluded: set[str]
) -> list[dict[str, Any]]:
    """Remove competitor signals whose domain is in the merchant exclusion set."""
    return [
        signal
        for signal in signals
        if _normalize_domain_value(str(signal.get("domain", ""))) not in excluded
    ]


def _merchant_public_domains(
    shop: str,
    *,
    gsc_page_rows: dict[str, dict[str, Any]] | None = None,
) -> list[str]:
    """Return known merchant domains beyond the myshopify hostname."""
    domains: list[str] = []
    seen: set[str] = set()

    def add(value: Any) -> None:
        domain = _normalize_domain_value(str(value or ""))
        if domain and domain not in seen:
            domains.append(domain)
            seen.add(domain)

    add(shop)
    add(storefront_host(shop))
    for value in os.getenv("COMPETITOR_CRAWL_MERCHANT_DOMAINS", "").split(","):
        add(value)
    for key in gsc_page_rows or {}:
        add(str(key))
    return domains


def _merchant_brand_terms(
    shop: str,
    *,
    business_profile: dict[str, Any] | None = None,
) -> frozenset[str]:
    """Return brand terms that must not be treated as competitor brands."""
    terms: set[str] = set()
    profile = business_profile or {}
    for value in (
        profile.get("brand_name"),
        shop,
        _domain_to_keyword_marker(shop),
    ):
        terms.update(_content_words(_coerce_str(value)))
    terms.update(shop_brand_terms(shop))
    terms.update(_content_words(_domain_to_keyword_marker(storefront_host(shop))))
    return frozenset(terms)


def _competitor_brand_markers(
    *,
    business_profile: dict[str, Any] | None = None,
    merchant_terms: frozenset[str] | None = None,
) -> tuple[frozenset[str], ...]:
    """Build normalized competitor/retailer markers to exclude from product keywords."""
    markers = set(_RETAILER_BRAND_QUERY_MARKERS)
    profile = business_profile or {}
    for domain in profile.get("competitor_domains", []) or []:
        marker = _domain_to_keyword_marker(str(domain))
        if marker:
            markers.add(marker)
    for item in profile.get("competitors", []) or []:
        if not isinstance(item, dict):
            continue
        name = _coerce_str(item.get("name", ""))
        domain_marker = _domain_to_keyword_marker(_coerce_str(item.get("domain", "")))
        if name:
            markers.add(name)
        if domain_marker:
            markers.add(domain_marker)
    allowed = merchant_terms or frozenset()
    out: list[frozenset[str]] = []
    for marker in markers:
        words = _content_words(marker)
        if not words or words <= allowed:
            continue
        out.append(words)
    return tuple(out)


def _has_competitor_brand_marker(
    query: str,
    competitor_markers: tuple[frozenset[str], ...],
    merchant_terms: frozenset[str],
) -> bool:
    """Return True when a query targets a competitor/retailer brand."""
    query_words = _content_words(query)
    if not query_words:
        return False
    if query_words & merchant_terms:
        return False
    return any(marker <= query_words for marker in competitor_markers)


def _filter_competitor_brand_keywords(
    keywords: list[dict[str, Any]],
    *,
    competitor_markers: tuple[frozenset[str], ...],
    merchant_terms: frozenset[str],
) -> list[dict[str, Any]]:
    """Remove competitor-branded keywords from product-page target selection."""
    if not competitor_markers:
        return list(keywords)
    filtered: list[dict[str, Any]] = []
    for keyword in keywords:
        if not isinstance(keyword, dict):
            continue
        query = _clean_keyword_query(keyword.get("query", ""))
        if _has_competitor_brand_marker(query, competitor_markers, merchant_terms):
            continue
        filtered.append(keyword)
    return filtered


def _seed_text_list(seed_texts: str | list[str]) -> list[str]:
    """Normalize source texts used to discover product seed phrases."""
    if isinstance(seed_texts, str):
        return [seed_texts]
    return [str(text) for text in seed_texts if str(text).strip()]


def _idea_is_relevant(
    idea_query: str,
    seed_queries: list[str],
    min_overlap: int = 2,
    product_words: frozenset[str] | None = None,
) -> bool:
    """Return True if the idea shares ≥min_overlap content words with any seed keyword.

    Filters out DataForSEO Keyword Ideas that are semantically unrelated to the
    product context (e.g. 'fable de la fontaine' when seeds are about cat fountains).
    """
    idea_words = _content_words(idea_query)
    if not idea_words:
        return False
    seed_words = frozenset().union(*(_content_words(s) for s in seed_queries))
    if len(idea_words & seed_words) >= min_overlap:
        return True
    if product_words is None:
        return False
    # Long, premium product seeds can be too narrow ("pull en cachemire pour chien")
    # and hide broader real-market ideas ("manteau chien", "vêtement chien").
    # Keep them when they match the product text itself on at least two words.
    return len(idea_words & product_words) >= min_overlap


def _generic_product_seeds(seed_texts: str | list[str], *, limit: int = 6) -> list[str]:
    """Build short product seeds from observed text, without domain vocabularies."""
    seeds: list[str] = []
    for text in _seed_text_list(seed_texts):
        raw_words = re.findall(r"[a-zàâäéèêëîïôùûüç]+", text.lower())
        words = _content_word_sequence(text)
        for idx, word in enumerate(raw_words):
            if word != "pour":
                continue
            before = [w for w in raw_words[:idx] if len(w) >= 3 and w not in _FR_STOP_WORDS]
            after = [w for w in raw_words[idx + 1 :] if len(w) >= 3 and w not in _FR_STOP_WORDS]
            if before and after:
                head = before[0]
                audience_or_use = after[0]
                seeds.append(f"{head} {audience_or_use}")
                seeds.append(f"{head} pour {audience_or_use}")
        if len(words) >= 3:
            seeds.append(" ".join(words[:3]))
            seeds.append(f"{words[0]} {words[-1]}")
            seeds.append(f"{words[0]} pour {words[-1]}")
        elif len(words) == 2:
            seeds.append(" ".join(words))
            seeds.append(f"{words[0]} pour {words[-1]}")
    return list(dict.fromkeys(seed for seed in seeds if seed.strip()))[:limit]


def _word_bigrams(sequence: list[str]) -> frozenset[tuple[str, str]]:
    return frozenset(zip(sequence, sequence[1:]))


def _score_idea_fit(
    idea_query: str,
    product_words: frozenset[str],
    product_bigrams: frozenset[tuple[str, str]] = frozenset(),
) -> int:
    """Heuristic product_fit_score for DataForSEO keyword ideas (no extra LLM call).

    Counts content-word overlap between the idea and the product's own text
    (title + handle + tags + collections). Ideas already passed _idea_is_relevant,
    so they share words with the seed keywords; a 0-overlap result here still gets
    a non-zero floor (50) rather than the misleading 0 from the provider.

    Bag-of-words overlap alone is fooled by unrelated noun phrases sharing an
    adjective ("harnais chaise haute" vs "harnais haute couture" both contain
    "harnais" + "haute"): a 2+ overlap only earns a high score when the idea also
    shares an adjacent word pair with the product text.
    """
    idea_seq = _content_word_sequence(idea_query)
    idea_words = frozenset(idea_seq)
    overlap = len(idea_words & product_words)
    if overlap >= 2 and product_bigrams and not (_word_bigrams(idea_seq) & product_bigrams):
        overlap = 1
    if overlap >= 3:
        return 90
    if overlap >= 2:
        return 75
    if overlap >= 1:
        return 60
    return 50


# ── Real-data-first candidate pool ───────────────────────────────────────────
# The engine seeds keyword candidates from REAL sources before the LLM, so the
# model selects from observed demand instead of inventing terms. Source priority
# decides which entry wins when the same query comes from several sources.
_SOURCE_PRIORITY = {
    "dataforseo": 4,
    "gsc": 3,
    "google_suggest": 2,
    "trends": 1,
    "market_seed": 1,
    "llm_proposed": 0,
    "llm_estimated": 0,
}
_POOL_MAX = 40
_GSC_POOL_LIMIT = 12
_SUGGEST_SEED_MAX = 5
# Question prefixes used to harvest GEO/AEO intents from Google Suggest — these
# mirror what shoppers type into Google and ask assistants like ChatGPT.
_QUESTION_PREFIXES = ("comment", "pourquoi", "quelle", "quel", "combien")

_CUSTOMER_PROBLEM_TERMS = frozenset(
    {
        "froid",
        "froide",
        "hiver",
        "chaud",
        "chaude",
        "frileux",
        "frileuse",
        "tire",
        "traction",
        "boit",
        "boire",
        "hydratation",
        "soif",
        "silencieux",
        "silencieuse",
    }
)

_UNCONFIRMED_QUERY_MODIFIERS = frozenset(
    {
        "personnalisé",
        "personnalise",
        "personnalisée",
        "personnalisee",
        "custom",
        "mesure",
    }
)


# Intent-type labels and generic intent verbs coming back in Pass 1
# ``buying_intents`` — they describe HOW someone searches, never belong inside a
# keyword ("pull chien transactional", "harnais haute couture commercial").
_INTENT_META_WORDS = frozenset(
    {
        "transactional",
        "commercial",
        "informational",
        "navigational",
        "achat",
        "achats",
        "acheter",
        "recherche",
        "recherches",
        "rechercher",
        "chercher",
        "cherche",
        "trouver",
        "trouve",
        "comparer",
        "comparaison",
        "besoin",
        "besoins",
        "intérêt",
        "interet",
        "intention",
        "qualité",
        "qualite",
    }
)


def _market_need_seed_queries(
    source_text: str | list[str],
    *,
    buying_intents: list[str] | None = None,
    target_customer: str = "",
    limit: int = 10,
) -> list[str]:
    """Build deterministic product/customer-need seeds from discovered context."""
    seeds = list(_generic_product_seeds(source_text, limit=limit))
    base_seeds = [seed for seed in seeds if len(_content_words(seed)) >= 2]
    intent_words: list[str] = []
    for intent in buying_intents or []:
        for word in _content_word_sequence(str(intent)):
            if word not in intent_words and word not in _INTENT_META_WORDS:
                intent_words.append(word)
    customer_words = [
        word for word in _content_word_sequence(target_customer) if word not in _INTENT_META_WORDS
    ]

    for base_seed in base_seeds[:2]:
        base_words = _content_words(base_seed)
        for intent_word in intent_words[:3]:
            if intent_word not in base_words:
                seeds.append(f"{base_seed} {intent_word}")
    if customer_words and intent_words:
        customer = customer_words[0]
        for intent_word in intent_words[:2]:
            if intent_word != customer:
                seeds.append(f"{customer} {intent_word}")
    return list(dict.fromkeys(seed for seed in seeds if seed.strip()))[:limit]


def _seed_keyword_candidates(
    queries: list[str],
    product_words: frozenset[str],
) -> list[dict[str, Any]]:
    """Turn deterministic market-need seeds into enrichable keyword candidates."""
    candidates: list[dict[str, Any]] = []
    for query in queries:
        query = _clean_keyword_query(query)
        if not query:
            continue
        words = _content_words(query)
        is_problem = bool(words & _CUSTOMER_PROBLEM_TERMS)
        candidates.append(
            {
                "query": query,
                "intent_type": "informational" if is_problem else "commercial",
                "demand_score": 45 if is_problem else 50,
                "competition_score": 50,
                # Cap at 60 (neutral): a recombined seed is unverified by any real
                # source, so it must never surface as a "positive" keyword tag.
                "product_fit_score": min(_score_idea_fit(query, product_words), 60),
                "reason": (
                    "Seed déterministe de besoin client"
                    if is_problem
                    else "Seed déterministe de catégorie produit"
                ),
                "data_source": "market_seed",
                "difficulty_source": "free_estimated",
                "search_volume": None,
                "notes": ["Seed ajouté pour couvrir le besoin client avant génération"],
            }
        )
    return candidates


def _gsc_candidates(
    product_words: frozenset[str],
    gsc_query_rows: list[dict[str, Any]],
    *,
    limit: int = _GSC_POOL_LIMIT,
) -> list[dict[str, Any]]:
    """Real GSC queries matched to this product, carrying impressions/clicks/position.

    These are the strongest candidates: queries real shoppers already used to reach
    (or almost reach) the store, so they ground keyword selection in observed demand.
    """
    out: list[dict[str, Any]] = []
    for row in gsc_query_rows:
        query = str(row.get("query", "")).strip()
        if not query or not (_content_words(query) & product_words):
            continue
        impressions = int(row.get("impressions", 0) or 0)
        clicks = int(row.get("clicks", 0) or 0)
        position = round(float(row.get("position", 0) or 0), 1)
        out.append(
            {
                "query": query,
                "intent_type": "unknown",
                "demand_score": _impressions_bucket(impressions),
                "competition_score": 50,
                "product_fit_score": 0,
                "reason": (
                    f"Requête réelle GSC — {impressions} impressions, "
                    f"{clicks} clics, position moyenne {position}"
                ),
                "data_source": "gsc",
                "difficulty_source": "free_estimated",
                "search_volume": None,
                "gsc_impressions": impressions,
                "gsc_clicks": clicks,
                "gsc_position": position,
                "notes": [],
            }
        )
    out.sort(key=lambda k: int(k.get("gsc_impressions", 0) or 0), reverse=True)
    return out[:limit]


def _suggest_candidates(
    seeds: list[str],
    product_words: frozenset[str],
    *,
    fetcher: Callable[[list[str]], list[Any]],
) -> list[dict[str, Any]]:
    """Google Autocomplete expansions of the product seeds (real search intents).

    Adds question-prefixed seeds to surface GEO/AEO intents. Free, no volume data —
    DataForSEO enrichment fills volumes for these candidates afterwards.
    """
    core = seeds[0] if seeds else ""
    question_seeds = [f"{prefix} {core}".strip() for prefix in _QUESTION_PREFIXES[:2] if core]
    all_seeds = list(dict.fromkeys([*seeds, *question_seeds]))
    try:
        raw = fetcher(all_seeds)
    except Exception as exc:  # pragma: no cover — network/parse guarded upstream too
        logger.warning("Google Suggest pool fetch failed: %s", exc)
        return []
    out: list[dict[str, Any]] = []
    for item in raw or []:
        kw = getattr(item, "keyword", None)
        if kw is None and isinstance(item, dict):
            kw = item.get("keyword")
        query = str(kw or "").strip()
        if not query or not (_content_words(query) & product_words):
            continue
        out.append(
            {
                "query": query,
                "intent_type": "unknown",
                "demand_score": 40,
                "competition_score": 50,
                "product_fit_score": 0,
                "reason": "Suggestion Google Autocomplete (intention de recherche réelle)",
                "data_source": "google_suggest",
                "difficulty_source": "free_estimated",
                "search_volume": None,
                "notes": ["Google Suggest — popularité réelle, volume à confirmer"],
            }
        )
    return out


def _trend_candidates(
    trend_top: list[str],
    trend_rising: list[str],
    product_words: frozenset[str],
) -> list[dict[str, Any]]:
    """Google Trends related queries matched to the product."""
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for query, rising in [(q, False) for q in trend_top] + [(q, True) for q in trend_rising]:
        query = str(query or "").strip()
        key = query.lower()
        if not query or key in seen or not (_content_words(query) & product_words):
            continue
        seen.add(key)
        out.append(
            {
                "query": query,
                "intent_type": "unknown",
                "demand_score": 55 if rising else 45,
                "competition_score": 50,
                "product_fit_score": 0,
                "reason": "En hausse sur Google Trends" if rising else "Tendance Google Trends",
                "data_source": "trends",
                "difficulty_source": "free_estimated",
                "search_volume": None,
                "notes": ["Google Trends (12 derniers mois)"],
            }
        )
    return out


def _merge_pool_candidate(pool: dict[str, dict[str, Any]], cand: dict[str, Any]) -> None:
    """Insert a candidate into the pool, deduplicating by normalised query.

    On collision the higher-priority source becomes the base, but real GSC metrics
    are always preserved so we never lose observed performance data.
    """
    query = str(cand.get("query", "")).strip()
    if not query:
        return
    key = query.lower()
    priority = _SOURCE_PRIORITY.get(str(cand.get("data_source", "")), 0)
    existing = pool.get(key)
    if existing is None:
        cand["_src_priority"] = priority
        pool[key] = cand
        return
    # Preserve GSC performance regardless of which base wins.
    if cand.get("gsc_impressions") and not existing.get("gsc_impressions"):
        for fld in ("gsc_impressions", "gsc_clicks", "gsc_position"):
            existing[fld] = cand.get(fld)
    if priority > existing.get("_src_priority", 0):
        gsc_fields = {
            fld: existing.get(fld)
            for fld in ("gsc_impressions", "gsc_clicks", "gsc_position")
            if existing.get(fld)
        }
        cand["_src_priority"] = priority
        cand.update(gsc_fields)
        pool[key] = cand


def _build_keyword_candidate_pool(
    fields: dict[str, Any],
    gsc_query_rows: list[dict[str, Any]],
    *,
    dataforseo: Any = None,
    suggest_fetcher: Callable[[list[str]], list[Any]] | None = None,
    competitor_markers: tuple[frozenset[str], ...] = (),
    merchant_terms: frozenset[str] = frozenset(),
    use_suggest: bool = True,
    ideas_limit: int = 25,
    max_pool: int = _POOL_MAX,
) -> list[dict[str, Any]]:
    """Build a pool of REAL candidate keywords for a product, before any LLM call.

    Sources, most reliable first: GSC matched queries (observed impressions/clicks),
    DataForSEO keyword ideas (real French volume), Google Suggest (real autocomplete,
    incl. question intents for GEO), Google Trends. Each candidate is shaped like an
    seo_keyword dict carrying its ``data_source`` so the LLM selects from observed
    demand instead of inventing terms — the root cause of unreliable, AI-estimated
    keyword lists. Returns a deduplicated, source-ranked list capped at ``max_pool``.
    """
    title = str(fields.get("product_title", "")).strip()
    label = str(fields.get("merchant_label", "")).strip()
    handle_words = str(fields.get("handle", "")).replace("-", " ")
    product_text = " ".join([fields.get("source_product_text", "") or title, label, handle_words])
    product_words = _content_words(product_text)
    product_bigrams = _word_bigrams(_content_word_sequence(product_text))

    gsc_cands = _gsc_candidates(product_words, gsc_query_rows)

    seed_texts = [
        label,
        title,
        handle_words,
    ]
    seeds: list[str] = []
    for seed in [label or title, title]:
        seed = seed.strip()
        if seed and seed.lower() not in {s.lower() for s in seeds}:
            seeds.append(seed)
    for seed in _market_need_seed_queries(seed_texts):
        if seed and seed.lower() not in {s.lower() for s in seeds}:
            seeds.append(seed)
    if gsc_cands and gsc_cands[0]["query"].lower() not in {s.lower() for s in seeds}:
        seeds.append(gsc_cands[0]["query"])
    seeds = seeds[:_SUGGEST_SEED_MAX]

    pool: dict[str, dict[str, Any]] = {}
    for cand in gsc_cands:
        _merge_pool_candidate(pool, cand)
    for cand in _trend_candidates(
        fields.get("trend_top", []) or [], fields.get("trend_rising", []) or [], product_words
    ):
        _merge_pool_candidate(pool, cand)
    for cand in _seed_keyword_candidates(_market_need_seed_queries(seed_texts), product_words):
        _merge_pool_candidate(pool, cand)

    if dataforseo is not None and getattr(dataforseo, "available", False) and seeds:
        ideas = dataforseo.fetch_keyword_ideas(seeds, limit=ideas_limit)
        for idea in ideas or []:
            query = str(idea.get("query", "")).strip()
            if not query or not _idea_is_relevant(query, seeds, product_words=product_words):
                continue
            idea["product_fit_score"] = _score_idea_fit(query, product_words, product_bigrams)
            _merge_pool_candidate(pool, idea)

    if use_suggest and seeds:
        fetcher = suggest_fetcher or fetch_suggestions_bulk
        for cand in _suggest_candidates(seeds, product_words, fetcher=fetcher):
            _merge_pool_candidate(pool, cand)

    candidates = list(pool.values())
    candidates.sort(
        key=lambda k: (
            k.get("_src_priority", 0),
            int(k.get("search_volume") or 0),
            int(k.get("demand_score", 0) or 0),
        ),
        reverse=True,
    )
    for cand in candidates:
        cand.pop("_src_priority", None)
    candidates = _filter_competitor_brand_keywords(
        candidates,
        competitor_markers=competitor_markers,
        merchant_terms=merchant_terms,
    )
    return candidates[:max_pool]


def _enrich_keyword_dicts(
    keywords: list[dict[str, Any]],
    free_provider: Any,
    paid_providers: list[Any],
    *,
    shop: str,
) -> list[dict[str, Any]]:
    """Run free + paid keyword enrichment over LLM-shaped keyword dicts."""
    if not keywords:
        return keywords
    signals = signals_from_llm_keywords(keywords)
    signals = free_provider.enrich(signals, shop=shop)
    for paid in paid_providers:
        signals = paid.enrich(signals, shop=shop)
    return _apply_signals_to_keywords(keywords, signals)


def _is_real_keyword(keyword: dict[str, Any]) -> bool:
    """True when a keyword is backed by observed demand, not an LLM estimate."""
    return (
        str(keyword.get("data_source", ""))
        in ("gsc", "dataforseo", "google_ads", "google_suggest", "trends")
        or bool(keyword.get("search_volume"))
        or bool(keyword.get("gsc_impressions"))
    )


def _merge_pass1_selection(
    llm_keywords: list[dict[str, Any]],
    candidate_pool: list[dict[str, Any]],
    *,
    min_real_floor: int = 5,
) -> list[dict[str, Any]]:
    """Merge the LLM's keyword selection back onto the real candidate metrics.

    Selected queries inherit the pool's real data_source / volume / GSC metrics; the
    LLM only contributes intent_type, product_fit_score and reason. Keywords the LLM
    added (absent from the pool) are flagged ``data_source='llm_proposed'`` so they
    are never confused with observed demand.

    To keep results grounded and consistent run-to-run, the strongest real candidates
    are guaranteed a floor of ``min_real_floor`` entries: the LLM can label and
    reorder, but cannot silently drop high observed demand. Falls back to the top pool
    entries when the LLM returns nothing usable.
    """
    pool_by_query = {
        str(c.get("query", "")).strip().lower(): c
        for c in candidate_pool
        if isinstance(c, dict) and str(c.get("query", "")).strip()
    }
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for kw in llm_keywords or []:
        if not isinstance(kw, dict):
            continue
        query = _clean_keyword_query(kw.get("query", ""))
        key = query.lower()
        if not query or key in seen:
            continue
        seen.add(key)
        base = pool_by_query.get(key)
        if base is not None:
            merged = dict(base)
            if kw.get("intent_type"):
                merged["intent_type"] = kw["intent_type"]
            if kw.get("product_fit_score") is not None:
                merged["product_fit_score"] = kw["product_fit_score"]
            if kw.get("reason"):
                merged["reason"] = kw["reason"]
        else:
            merged = dict(kw)
            merged["query"] = query  # cleaned (no "new:" prefix)
            merged["data_source"] = "llm_proposed"
            merged.setdefault("difficulty_source", "free_estimated")
            merged.setdefault("search_volume", None)
            merged.setdefault("competition_score", 50)
            notes = list(merged.get("notes", []) or [])
            notes.append("Proposé par l'IA — aucune donnée marché")
            merged["notes"] = notes
        out.append(merged)

    # Guarantee a floor of the strongest REAL candidates the LLM may have skipped.
    real_in_out = sum(1 for k in out if _is_real_keyword(k))
    if real_in_out < min_real_floor:
        real_pool = sorted(
            (c for c in candidate_pool if isinstance(c, dict) and _is_real_keyword(c)),
            key=_keyword_priority_score,
            reverse=True,
        )
        for cand in real_pool:
            if real_in_out >= min_real_floor:
                break
            key = str(cand.get("query", "")).strip().lower()
            if key and key not in seen:
                out.append(dict(cand))
                seen.add(key)
                real_in_out += 1

    if not out:
        return [dict(c) for c in candidate_pool[:8]]
    return out


# A small/new store cannot realistically rank for very high-difficulty head terms,
# so raw search volume must not let a generic head term outrank a specific,
# winnable mid-tail that also converts better. These thresholds drive a penalty.
_HARD_DIFFICULTY = 85
_TOUGH_DIFFICULTY = 70


# Consumable / spare-part / accessory markers. A query containing one of these
# targets a different buying intent (e.g. a replacement *filter*) than the product
# itself (e.g. the *fountain*). When the product is not that accessory, such a query
# must not become the primary target — it stays in the list as supporting content.
_ACCESSORY_MARKERS = frozenset(
    {
        "filtre",
        "filtres",
        "recharge",
        "recharges",
        "cartouche",
        "cartouches",
        "piece",
        "pieces",
        "pièce",
        "pièces",
        "accessoire",
        "accessoires",
        "batterie",
        "batteries",
        "cable",
        "câble",
        "adaptateur",
        "housse",
        "embout",
        "mousse",
        "pompe",
    }
)

_DIY_FREE_QUERY_MARKERS = frozenset(
    {
        "gratuit",
        "gratuite",
        "gratuits",
        "gratuits",
        "modele",
        "modèle",
        "patron",
        "crochet",
        "tricot",
        "tricoter",
        "facile",
        "tuto",
        "diy",
    }
)

_BLOG_QUERY_MARKERS = frozenset(
    {
        "meilleur",
        "meilleure",
        "meilleurs",
        "meilleures",
        "comment",
        "choisir",
        "guide",
        "comparatif",
        "comparaison",
        "avis",
        "pourquoi",
        "quelle",
        "quelles",
        "quel",
        "quels",
    }
)

_COMMERCIAL_INTENT_TERMS = frozenset(
    {
        "acheter",
        "achat",
        "achats",
        "commande",
        "commander",
        "boutique",
        "vente",
        "prix",
        "tarif",
        "tarifs",
    }
)


def _classify_keyword_surface(keyword: dict[str, Any]) -> dict[str, Any]:
    """Classify the safest content surface for a keyword target."""
    query = _clean_keyword_query(keyword.get("query", ""))
    words = _content_words(query)
    intent = str(keyword.get("intent_type", "")).lower()
    is_question = "?" in query or bool(words & {"comment", "pourquoi", "quelle", "quelles", "quel"})
    is_diy_free = bool(words & _DIY_FREE_QUERY_MARKERS)
    is_problem_need = bool(words & _CUSTOMER_PROBLEM_TERMS)
    has_unconfirmed_modifier = bool(words & _UNCONFIRMED_QUERY_MODIFIERS)
    is_blog = (
        is_diy_free
        or bool(words & _BLOG_QUERY_MARKERS)
        or intent
        in {
            "informational",
            "informationnel",
            "informatif",
            "informative",
            "comparison",
            "comparative",
            "how-to",
            "question",
        }
    )
    if has_unconfirmed_modifier:
        surface = "blog"
        reason = "unconfirmed_segment_or_modifier"
    elif is_diy_free:
        surface = "blog"
        reason = "indirect_diy_or_free_query"
    elif is_problem_need and intent in {
        "informational",
        "informationnel",
        "informatif",
        "informative",
        "how-to",
        "question",
    }:
        surface = "blog"
        reason = "customer_problem_or_need"
    elif is_question:
        surface = "faq"
        reason = "short_fact_question"
    elif is_blog:
        surface = "blog"
        reason = "informational_or_indirect_acquisition"
    else:
        surface = "product_page"
        reason = "transactional_or_commercial_product_fit"
    return {
        "query": query,
        "surface": surface,
        "reason": reason,
        "product_primary_allowed": surface == "product_page",
        "is_indirect_acquisition": is_diy_free or has_unconfirmed_modifier,
    }


def _build_keyword_surface_mapping(keywords: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return a stable keyword-to-surface map for JSON transparency."""
    mapping: list[dict[str, Any]] = []
    for keyword in keywords:
        if not isinstance(keyword, dict):
            continue
        item = _classify_keyword_surface(keyword)
        if item["query"]:
            item["target_role"] = keyword.get("target_role", "supporting")
            item["customer_need_alignment_score"] = keyword.get(
                "customer_need_alignment_score",
                _keyword_need_alignment_score(keyword, frozenset()),
            )
            mapping.append(item)
    return mapping


def _keyword_need_alignment_score(keyword: dict[str, Any], product_words: frozenset[str]) -> int:
    """Score whether a keyword expresses the product category or a customer need."""
    query = _clean_keyword_query(keyword.get("query", ""))
    words = _content_words(query)
    if not words:
        return 0
    product_overlap = len(words & product_words)
    has_problem = bool(words & _CUSTOMER_PROBLEM_TERMS)
    has_diy = bool(words & _DIY_FREE_QUERY_MARKERS)
    has_unconfirmed_modifier = bool(words & _UNCONFIRMED_QUERY_MODIFIERS) and not (
        words & product_words & _UNCONFIRMED_QUERY_MODIFIERS
    )
    product_fit_raw = keyword.get("product_fit_score")
    product_fit = int(product_fit_raw) if isinstance(product_fit_raw, (int, float)) else None
    if has_diy:
        return 25
    if has_unconfirmed_modifier:
        return 35
    if product_fit is not None and product_fit < 50:
        return 45 if product_overlap >= 2 else 25
    if product_overlap >= 3:
        return 95
    if product_overlap >= 2:
        return 90
    if product_overlap == 1 and has_problem:
        return 75
    if product_overlap == 1:
        return 60
    return 15


def _merge_keyword_lists(*keyword_lists: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Deduplicate keyword dicts while preserving first occurrence order."""
    merged: list[dict[str, Any]] = []
    seen: set[str] = set()
    for keyword_list in keyword_lists:
        for keyword in keyword_list or []:
            if not isinstance(keyword, dict):
                continue
            query = _clean_keyword_query(keyword.get("query", ""))
            key = query.casefold()
            if not query or key in seen:
                continue
            candidate = dict(keyword)
            candidate["query"] = query
            merged.append(candidate)
            seen.add(key)
    return merged


def _repair_keyword_selection_for_customer_need(
    selected_keywords: list[dict[str, Any]],
    candidate_pool: list[dict[str, Any]],
    *,
    source_text: str | list[str],
    product_words: frozenset[str],
    buying_intents: list[str] | None = None,
    target_customer: str = "",
) -> list[dict[str, Any]]:
    """Inject deterministic category/problem seeds before ranking keyword targets."""
    seed_candidates = _seed_keyword_candidates(
        _market_need_seed_queries(
            source_text,
            buying_intents=buying_intents,
            target_customer=target_customer,
        ),
        product_words,
    )
    return _merge_keyword_lists(selected_keywords, seed_candidates, candidate_pool)


def _build_keyword_guardrail(
    keywords: list[dict[str, Any]],
    *,
    product_words: frozenset[str],
) -> dict[str, Any]:
    """Validate keyword targets before content generation starts."""
    top_targets = [keyword for keyword in keywords[:5] if isinstance(keyword, dict)]
    if not top_targets:
        return {
            "status": "blocked",
            "score": 0,
            "issues": ["missing_primary_keyword_target"],
            "blocking_reasons": [_BLOCKING_REASON_LABELS["keyword_guardrail_blocked"]],
            "recommended_next_actions": ["Regenerate keyword targets from product category seeds."],
        }

    evaluated: list[dict[str, Any]] = []
    for keyword in top_targets:
        surface = _classify_keyword_surface(keyword)
        score = _keyword_need_alignment_score(keyword, product_words)
        evaluated.append(
            {
                "query": surface["query"],
                "target_role": keyword.get("target_role", "supporting"),
                "surface": surface["surface"],
                "need_alignment_score": score,
                "product_primary_allowed": surface["product_primary_allowed"],
                "reason": surface["reason"],
            }
        )

    primary = next(
        (item for item in evaluated if item["target_role"] == "primary"),
        evaluated[0],
    )
    product_page_targets = [
        item
        for item in evaluated
        if item["surface"] == "product_page" and item["need_alignment_score"] >= 70
    ]
    indirect_targets = [
        item
        for item in evaluated
        if item["need_alignment_score"] < 50 or not item["product_primary_allowed"]
    ]

    issues: list[str] = []
    if primary["need_alignment_score"] < 70 or not primary["product_primary_allowed"]:
        issues.append("keyword_customer_need_alignment_low")
    if len(product_page_targets) < 2:
        issues.append("insufficient_product_page_keyword_targets")
    if len(indirect_targets) > 2:
        issues.append("keyword_targets_too_indirect")

    score = max(
        0,
        min(
            100,
            round(
                sum(item["need_alignment_score"] for item in evaluated) / len(evaluated)
                + min(len(product_page_targets), 3) * 5
                - max(0, len(indirect_targets) - 1) * 10
            ),
        ),
    )
    status = "blocked" if issues else "pass"
    return {
        "status": status,
        "score": score,
        "issues": issues,
        "evaluated_keywords": evaluated,
        "blocking_reasons": _blocking_reasons(
            ["keyword_guardrail_blocked", *issues] if issues else []
        ),
        "recommended_next_actions": (
            ["Regenerate keyword targets around category and customer-problem seeds."]
            if issues
            else []
        ),
    }


def _keyword_priority_score(
    keyword: dict[str, Any],
    product_words: frozenset[str] | None = None,
) -> int:
    """Score a keyword target on demand, *winnability*, and product specificity.

    Tuned for a small/premium store: difficulty is weighted more, very hard head
    terms are penalized (they are not realistically rankable), and product-fitting
    mid/long-tail queries get a specificity bonus — those convert better and are
    the ones a niche boutique can actually win. Evidence (GSC/DataForSEO) adds a
    small bonus without letting a low-fit keyword become primary on volume alone.

    When ``product_words`` is provided, a query that introduces an accessory /
    consumable intent the product itself is not (e.g. "filtre …" for a fountain)
    is penalized so it cannot become the primary target.
    """
    demand = max(0.0, min(100.0, float(keyword.get("demand_score", 0) or 0)))
    product_fit = max(0.0, min(100.0, float(keyword.get("product_fit_score", 0) or 0)))

    # Only a REAL difficulty (from DataForSEO) is trusted for the winnability term.
    # An estimated/zero difficulty means "unknown" — treat it as neutral instead of
    # "easy to rank", otherwise low-volume terms with no difficulty data (e.g. spare
    # parts) get a fake winnability boost and wrongly become the primary target.
    has_real_difficulty = str(keyword.get("difficulty_source", "")) == "dataforseo"
    competition = (
        max(0.0, min(100.0, float(keyword.get("competition_score", 50) or 50)))
        if has_real_difficulty
        else 50.0
    )
    score = 0.40 * demand + 0.25 * (100.0 - competition) + 0.35 * product_fit

    # Winnability: down-rank head terms a small store cannot realistically rank for.
    if has_real_difficulty:
        if competition >= _HARD_DIFFICULTY:
            score -= 25.0
        elif competition >= _TOUGH_DIFFICULTY:
            score -= 12.0
    else:
        # No real difficulty (the provider frequently omits it). Infer it from demand:
        # a high-volume head term is almost always highly competitive, so a small store
        # should not target it as primary just because its volume is large. Low ads
        # competition is NOT a proxy for organic difficulty.
        if demand >= 85:
            score -= 25.0
        elif demand >= 75:
            score -= 12.0

    # Specificity: reward product-fitting mid/long-tail (the queries that convert).
    word_count = len(_content_words(str(keyword.get("query", ""))))
    if word_count >= 3 and product_fit >= 60:
        score += 8.0
    elif word_count >= 2 and product_fit >= 70:
        score += 4.0

    source = str(keyword.get("data_source", "llm_estimated"))
    if source == "gsc":
        score += 5.0
    elif source in {"dataforseo", "google_ads"}:
        score += 3.0

    # Intent guard: penalize accessory/consumable queries when the product itself
    # is not that accessory, so the primary target stays on the product.
    if product_words is not None:
        query_words = _content_words(str(keyword.get("query", "")))
        accessory_terms = query_words & _ACCESSORY_MARKERS
        if accessory_terms and not (accessory_terms & product_words):
            score -= 20.0

    return max(0, min(100, round(score)))


def _assign_keyword_targets(
    keywords: list[dict[str, Any]],
    product_words: frozenset[str] | None = None,
) -> list[dict[str, Any]]:
    """Rank final keyword targets and attach their intended content role."""
    ranked: list[dict[str, Any]] = []
    seen: set[str] = set()
    for keyword in keywords:
        if not isinstance(keyword, dict):
            continue
        query = str(keyword.get("query", "")).strip()
        normalized_query = query.lower()
        if not normalized_query or normalized_query in seen:
            continue
        seen.add(normalized_query)
        candidate = dict(keyword)
        surface = _classify_keyword_surface(candidate)
        candidate["keyword_surface"] = surface["surface"]
        candidate["surface_reason"] = surface["reason"]
        candidate["product_primary_allowed"] = surface["product_primary_allowed"]
        alignment_score = (
            _keyword_need_alignment_score(candidate, product_words)
            if product_words is not None
            else 50
        )
        candidate["customer_need_alignment_score"] = alignment_score
        priority_score = _keyword_priority_score(candidate, product_words)
        if not surface["product_primary_allowed"]:
            priority_score = max(0, priority_score - 20)
        if alignment_score < 50:
            priority_score = max(0, priority_score - 25)
        candidate["priority_score"] = priority_score
        ranked.append(candidate)

    ranked.sort(
        key=lambda keyword: (
            not bool(keyword.get("product_primary_allowed", True)),
            -int(keyword.get("priority_score", 0)),
            -int(keyword.get("product_fit_score", 0) or 0),
            -int(keyword.get("demand_score", 0) or 0),
        )
    )
    primary_assigned = False
    for index, keyword in enumerate(ranked, start=1):
        keyword["target_rank"] = index
        if not primary_assigned and keyword.get("product_primary_allowed", True):
            keyword["target_role"] = "primary"
            primary_assigned = True
        elif index <= 5:
            keyword["target_role"] = "secondary"
        else:
            keyword["target_role"] = "supporting"
    return ranked


def _attach_serp_evidence(
    keywords: list[dict[str, Any]],
    serp_intel: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    """Attach SERP/PAA evidence gathered for the selected targets."""
    enriched: list[dict[str, Any]] = []
    for keyword in keywords:
        candidate = dict(keyword)
        key = str(candidate.get("query", "")).strip().lower()
        intel = serp_intel.get(key)
        candidate["serp_evidence"] = bool(intel)
        candidate["paa_questions"] = list((intel or {}).get("paa", []))
        candidate["serp_competitor_count"] = len((intel or {}).get("top_competitors", []))
        enriched.append(candidate)
    return enriched


def _build_surface_plan(
    keywords: list[dict[str, Any]],
    confirmed_facts: list[dict[str, Any]],
    geo_questions: list[dict[str, Any]] | None = None,
) -> dict[str, dict[str, Any]]:
    """Decide which content surfaces can add reliable user value."""
    confirmed_keys = {
        str(fact.get("key", ""))
        for fact in confirmed_facts
        if isinstance(fact, dict) and fact.get("confidence") == "confirmed"
    }
    merchant_confirmed_keys = {
        str(fact.get("key", ""))
        for fact in confirmed_facts
        if isinstance(fact, dict)
        and fact.get("confidence") == "confirmed"
        and fact.get("source") == "merchant_confirmation"
    }
    description_fact = next(
        (
            _coerce_str(fact.get("value", ""))
            for fact in confirmed_facts
            if isinstance(fact, dict)
            and fact.get("key") == "description"
            and fact.get("confidence") == "confirmed"
        ),
        "",
    )
    has_primary_target = bool(keywords and keywords[0].get("query"))
    has_informative_fact = (
        bool(confirmed_keys & _NARRATIVE_FACT_KEYS) or _content_word_count(description_fact) >= 12
    )
    has_paa = any(keyword.get("paa_questions") for keyword in keywords[:5])
    has_geo_questions = any(
        isinstance(question, dict) and _coerce_str(question.get("question", "")).strip()
        for question in (geo_questions or [])
    )
    has_informational_target = any(
        str(keyword.get("intent_type", "")).lower()
        in {
            "informational",
            "informationnel",
            "informatif",
            "informative",
            "question",
            "how-to",
            "navigationnel",
            "navigational",
            "information",
        }
        for keyword in keywords[:5]
    )
    has_merchant_faq_basis = bool(merchant_confirmed_keys) and has_primary_target
    has_merchant_support_topic = bool(merchant_confirmed_keys & {"use_cases", "selection_criteria"})

    return {
        "metadata": {
            "generate": has_primary_target,
            "reason": "primary_target_available"
            if has_primary_target
            else "missing_primary_target",
        },
        "product_description": {
            "generate": has_primary_target and has_informative_fact,
            "reason": "verified_product_facts_available"
            if has_informative_fact
            else "insufficient_verified_product_facts",
        },
        "faq": {
            "generate": has_primary_target,
            "reason": (
                "verified_paa_and_product_facts_available"
                if has_paa and has_informative_fact
                else "geo_ai_questions_available"
                if has_geo_questions and has_primary_target
                else "merchant_confirmed_faq_basis_available"
                if has_informative_fact and has_merchant_faq_basis
                else "paa_questions_available_pending_fact_validation"
                if has_paa and has_primary_target
                else "mandatory_faq_from_primary_keyword_pending_validation"
                if has_primary_target
                else "missing_primary_target"
            ),
        },
        "geo_answer": {
            "generate": has_primary_target and has_informative_fact,
            "reason": "verified_product_facts_available"
            if has_informative_fact
            else "insufficient_verified_product_facts",
        },
        "blog": {
            "generate": has_primary_target
            and (
                has_paa
                or has_informational_target
                or has_merchant_support_topic
                or has_informative_fact
            ),
            "reason": (
                "informational_demand_and_verified_facts_available"
                if has_informative_fact and (has_paa or has_informational_target)
                else "informational_demand_available"
                if has_paa or has_informational_target
                else "merchant_confirmed_support_topic_available"
                if has_merchant_support_topic
                else "verified_product_facts_available"
                if has_informative_fact
                else "insufficient_informational_evidence"
            ),
        },
    }


def _build_enrichment_questions(
    keywords: list[dict[str, Any]],
    missing_facts: list[dict[str, Any]],
    surface_plan: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    """Create merchant questions that improve content quality.

    Returns one fact-based question per genuinely missing fact (so the merchant can
    close every gap shown on the readiness card, not just two at a time), followed
    by the 2 editorial questions (benefit + selection guide). Answered questions are
    filtered out by the caller so the list stays in sync with what is still missing.
    """
    primary_query = str(keywords[0].get("query", "")).strip() if keywords else ""
    if not primary_query:
        return []
    paa_question = next(
        (
            str(question).strip()
            for keyword in keywords[:5]
            for question in keyword.get("paa_questions", [])
            if str(question).strip()
        ),
        "",
    )
    available_missing = {
        str(fact.get("key", "")) for fact in missing_facts if isinstance(fact, dict)
    }
    templates = {
        "warranty": (
            f"Quelle garantie pouvez-vous confirmer pour « {primary_query} » ?",
            "Ex. garantie 2 ans, avec les conditions exactes.",
        ),
        "compatibility": (
            f"Dans quel contexte ou usage principal « {primary_query} » est-il conçu ?",
            "Ex. en hiver pour les petits chiens frileux, en promenade par temps frais.",
        ),
        "dimensions": (
            f"Quelles dimensions exactes peut-on indiquer pour « {primary_query} » ?",
            "Ex. hauteur, largeur et capacité vérifiées.",
        ),
        "care": (
            f"Quel entretien exact recommandez-vous pour « {primary_query} » ?",
            "Ex. étapes de nettoyage et fréquence confirmées.",
        ),
        "materials": (
            f"Quels matériaux composent réellement « {primary_query} » ?",
            "Ex. acier inoxydable, coton bio ou silicone.",
        ),
        "origins": (
            f"Quelle origine de fabrication pouvez-vous prouver pour « {primary_query} » ?",
            "Ex. fabriqué en France, seulement si confirmé.",
        ),
        "certifications": (
            f"Quelle certification vérifiée concerne « {primary_query} » ?",
            "Ex. nom exact du label et périmètre concerné.",
        ),
        "size_recommendation": (
            f"Comment choisir la bonne taille de « {primary_query} » pour son animal ?",
            "Ex. mesure à prendre (tour de poitrine, longueur dos) et correspondance taille confirmée.",
        ),
        "targets": (
            f"À qui s'adresse principalement « {primary_query} » (espèce, race, profil) ?",
            "Ex. chiens adultes de petite race frileux, chats d'intérieur séniors, lapins nains.",
        ),
        "properties": (
            f"Quelles sont les 2-3 propriétés distinctives de « {primary_query} » face aux alternatives ?",
            "Ex. fermeture à clipper réglable, lavable en machine à 30°C, bandes réfléchissantes la nuit.",
        ),
        "delivery": (
            f"Quelle information de livraison souhaitez-vous mentionner pour « {primary_query} » ?",
            "Ex. expédié sous 24h, livraison offerte dès 49€.",
        ),
        "returns": (
            f"Quelle politique de retour ou satisfaction s'applique à « {primary_query} » ?",
            "Ex. retours acceptés 30 jours, remboursement garanti si insatisfait.",
        ),
    }
    questions: list[dict[str, Any]] = []
    for key in (
        "origins",
        "care",
        "dimensions",
        "size_recommendation",
        "materials",
        "certifications",
        "warranty",
        "compatibility",
    ):
        if key not in available_missing:
            continue
        question, placeholder = templates[key]
        questions.append(
            {
                "key": key,
                "field_key": key,
                "question": question,
                "placeholder": placeholder,
                "why_it_matters": (
                    f"Permet une réponse factuelle liée à « {paa_question or primary_query} »."
                ),
                "target_keyword": primary_query,
                "unlocks_surfaces": ["faq", "geo_answer"],
            }
        )
    # Score-boosting questions not gated by Shopify snapshot: always proposed until answered.
    # targets + properties → Répondabilité IA (20%). delivery + returns → Confiance (15%).
    for key, why in (
        ("targets", "Améliore la Répondabilité IA — pilier à 20% dans le Score GEO."),
        ("properties", "Améliore la Répondabilité IA — pilier à 20% dans le Score GEO."),
        ("delivery", "Améliore le pilier Confiance — à 15% dans le Score GEO."),
        ("returns", "Améliore le pilier Confiance — à 15% dans le Score GEO."),
    ):
        question, placeholder = templates[key]
        questions.append(
            {
                "key": key,
                "field_key": key,
                "question": question,
                "placeholder": placeholder,
                "why_it_matters": why,
                "target_keyword": primary_query,
                "unlocks_surfaces": ["faq", "geo_answer"],
            }
        )
    questions.extend(
        [
            {
                "key": "use_cases",
                "field_key": "use_cases",
                "question": f"Quel bénéfice concret « {primary_query} » apporte-t-il à vos clients, et quel problème résout-il ?",
                "placeholder": "Ex. tient chaud aux petits chiens frileux en hiver, évite les frissons après le bain.",
                "why_it_matters": "Fournit l'angle éditorial central pour un article ou une FAQ qui accroche.",
                "target_keyword": primary_query,
                "unlocks_surfaces": ["faq", "blog"],
            },
            {
                "key": "selection_criteria",
                "field_key": "selection_criteria",
                "question": f"Comment un client non-expert devrait-il choisir entre plusieurs « {primary_query} » ?",
                "placeholder": "Ex. selon la race, le poids, la météo ou le niveau d'activité.",
                "why_it_matters": "Structure un guide d'achat naturellement optimisé pour les requêtes de comparaison.",
                "target_keyword": primary_query,
                "unlocks_surfaces": ["blog"],
            },
        ]
    )
    return questions


def _forbidden_phrases_from_niche(niche_hypothesis: dict[str, Any] | None) -> list[str]:
    """Return merchant-defined phrases and promises the generator must avoid."""
    if not niche_hypothesis:
        return []
    phrases: list[str] = []
    for value in niche_hypothesis.get("forbidden_promises", []):
        phrase = _coerce_str(value.get("promise", "") if isinstance(value, dict) else value).strip()
        if phrase and phrase not in phrases:
            phrases.append(phrase)
    brand_voice = niche_hypothesis.get("brand_voice", {})
    if isinstance(brand_voice, dict):
        for value in brand_voice.get("do_not_say", []):
            phrase = _coerce_str(value).strip()
            if phrase and phrase not in phrases:
                phrases.append(phrase)
    return phrases


def _enabled_surface(surface_plan: dict[str, Any], surface: str, default: bool = True) -> bool:
    decision = surface_plan.get(surface)
    if not isinstance(decision, dict):
        return default
    return bool(decision.get("generate"))


def _build_evidence_ledger(
    claims: list[dict[str, Any]],
    confirmed_facts: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[str]]:
    """Resolve LLM-declared claims against deterministic Shopify facts."""
    fact_map = {
        str(fact.get("key", "")): fact
        for fact in confirmed_facts
        if isinstance(fact, dict) and fact.get("confidence") == "confirmed"
    }
    ledger: list[dict[str, Any]] = []
    invalid_claims: list[str] = []
    for claim in claims:
        fact_keys = claim.get("fact_keys", [])
        if not fact_keys or any(fact_key not in fact_map for fact_key in fact_keys):
            invalid_claims.append(str(claim.get("claim", "")))
            continue
        ledger.append(
            {
                "claim": claim["claim"],
                "facts": [
                    {
                        "key": fact_key,
                        "value": fact_map[fact_key].get("value"),
                        "source": fact_map[fact_key].get("source"),
                    }
                    for fact_key in fact_keys
                ],
            }
        )
    return ledger, invalid_claims


def _detect_unsupported_claim_categories(
    generated_text: str,
    source_text: str,
    confirmed_facts: list[dict[str, Any]],
) -> list[str]:
    """Flag sensitive generated claims absent from the source product record."""
    confirmed_keys = {
        str(fact.get("key", ""))
        for fact in confirmed_facts
        if isinstance(fact, dict) and fact.get("confidence") == "confirmed"
    }
    aliases = {
        "origin": {"origin", "origins"},
        "origins": {"origin", "origins"},
        "care": {"care", "care_instructions"},
        "care_instructions": {"care", "care_instructions"},
    }
    unsupported: list[str] = []
    for category, pattern in _CLAIM_PATTERNS:
        if not re.search(pattern, generated_text, flags=re.IGNORECASE):
            continue
        supported_by_source = bool(re.search(pattern, source_text, flags=re.IGNORECASE))
        supported_keys = aliases.get(category, {category})
        if not (confirmed_keys & supported_keys) and not supported_by_source:
            unsupported.append(category)
    return unsupported


def _claim_category_mentions(
    generated_text: str,
    unsupported_categories: list[str],
) -> list[str]:
    """Return short unsupported claim excerpts for the merchant-facing ledger."""
    mentions: list[str] = []
    seen: set[str] = set()
    for category in unsupported_categories:
        pattern = next((p for c, p in _CLAIM_PATTERNS if c == category), "")
        if not pattern:
            continue
        match = re.search(pattern, generated_text, flags=re.IGNORECASE)
        if not match:
            continue
        value = f"{category}: {match.group(0)}"
        if value not in seen:
            mentions.append(value)
            seen.add(value)
    return mentions


def _validate_claims(
    *,
    claims: list[dict[str, Any]],
    confirmed_facts: list[dict[str, Any]],
    evidence_ledger: list[dict[str, Any]],
    invalid_claims: list[str],
    generated_text: str,
    source_product_text: str,
) -> dict[str, Any]:
    """Validate generated claims against confirmed facts and source evidence."""
    valid_claims = [str(entry.get("claim", "")) for entry in evidence_ledger if entry.get("claim")]
    unsupported_categories = _detect_unsupported_claim_categories(
        generated_text,
        source_product_text,
        confirmed_facts,
    )
    unsupported_claims = [claim for claim in invalid_claims if claim] + _claim_category_mentions(
        generated_text, unsupported_categories
    )
    publish_blockers: list[str] = []
    if invalid_claims:
        publish_blockers.append("unverified_claim_reference")
    if unsupported_categories:
        publish_blockers.append("unsupported_product_claims")
    if generated_text and not claims:
        publish_blockers.append("missing_claim_evidence_ledger")

    consistency_score = 100
    if invalid_claims:
        consistency_score -= min(40, 20 * len(invalid_claims))
    if unsupported_categories:
        consistency_score -= min(50, 25 * len(unsupported_categories))
    if generated_text and not claims:
        consistency_score -= 35
    if claims and not valid_claims:
        consistency_score -= 25

    return {
        "valid_claims": valid_claims,
        "unsupported_claims": unsupported_claims,
        "unsupported_claim_categories": unsupported_categories,
        "publish_blockers": publish_blockers,
        "product_consistency_score": max(0, min(100, consistency_score)),
    }


def _add_quality_issue(quality: dict[str, Any], issue: str) -> None:
    """Append a blocking quality issue and revoke publication eligibility."""
    issues = quality.setdefault("issues", [])
    if issue not in issues:
        issues.append(issue)
    quality["publish_ready"] = False
    quality["auto_apply_allowed"] = False
    if issue in _BLOCKING_REASON_LABELS:
        quality["final_status"] = "blocked"
        quality["publish_status"] = "blocked"
        reasons = quality.setdefault("blocking_reasons", [])
        reason = _BLOCKING_REASON_LABELS[issue]
        if reason not in reasons:
            reasons.append(reason)
    elif quality.get("final_status") == "publish_ready":
        quality["final_status"] = "ready_for_review"
        quality["publish_status"] = "ready_for_review"


def _keyword_is_covered(query: str, text: str) -> bool:
    """Return whether a content field covers all meaningful terms of a query."""
    query_words = _content_words(query)
    text_words = _content_words(text)
    if not query_words:
        return False
    for query_word in query_words:
        if not any(
            text_word == query_word
            or text_word == f"{query_word}s"
            or text_word == f"{query_word}x"
            or query_word == f"{text_word}s"
            or query_word == f"{text_word}x"
            for text_word in text_words
        ):
            return False
    return True


def _keyword_coverage_query(query: str) -> tuple[str, str]:
    """Return the query to check in content and the coverage mode used."""
    words = _content_word_sequence(query)
    stripped_words = [word for word in words if word not in _COMMERCIAL_INTENT_TERMS]
    if len(stripped_words) >= 2 and len(stripped_words) < len(words):
        return " ".join(stripped_words), "commercial_intent_normalized"
    return query, "exact_terms"


def _keyword_is_naturally_covered(query: str, text: str) -> bool:
    """Return whether content naturally covers a query or its commercial intent."""
    if _keyword_is_covered(query, text):
        return True
    coverage_query, _mode = _keyword_coverage_query(query)
    return coverage_query != query and _keyword_is_covered(coverage_query, text)


def _adapted_keyword_fields(
    keyword: dict[str, Any],
    coverage_fields: dict[str, str],
) -> list[str]:
    """Return the generated fields that match a keyword's intended surface."""
    surface = _coerce_str(keyword.get("keyword_surface", "")).strip()
    if not surface:
        surface = _classify_keyword_surface(keyword)["surface"]
    candidates = {
        "product_page": ("meta_title", "meta_description", "description", "geo"),
        "blog": ("blog",),
        "faq": ("faq", "geo"),
    }.get(surface, ("meta_title", "meta_description", "description", "geo", "blog"))
    return [field for field in candidates if field in coverage_fields]


def _build_keyword_content_guardrail(
    *,
    targets: list[dict[str, Any]],
    keyword_coverage: list[dict[str, Any]],
) -> dict[str, Any]:
    """Validate that selected keyword targets are actually used in generated content."""
    evaluated: list[dict[str, Any]] = []
    for index, target in enumerate(targets[:5]):
        coverage_item = keyword_coverage[index] if index < len(keyword_coverage) else {}
        role = _coerce_str(target.get("target_role", "supporting"), "supporting")
        surface = (
            _coerce_str(target.get("keyword_surface", "")).strip()
            or _classify_keyword_surface(target)["surface"]
        )
        covered_adapted_fields = _coerce_str_list(coverage_item.get("adapted_fields_covered", []))
        meta_fields_covered = [
            field
            for field in _coerce_str_list(coverage_item.get("fields", []))
            if field in {"meta_title", "meta_description"}
        ]
        evaluated.append(
            {
                "query": _coerce_str(target.get("query", "")),
                "target_role": role,
                "surface": surface,
                "coverage_query": _coerce_str(coverage_item.get("coverage_query", "")),
                "coverage_mode": _coerce_str(coverage_item.get("coverage_mode", "exact_terms")),
                "adapted_fields": _coerce_str_list(coverage_item.get("adapted_fields", [])),
                "covered_adapted_fields": covered_adapted_fields,
                "meta_fields_covered": meta_fields_covered,
                "is_covered": bool(covered_adapted_fields),
                "is_metadata_covered": bool(meta_fields_covered),
                "required": role in {"primary", "secondary"},
            }
        )

    primary = next((item for item in evaluated if item["target_role"] == "primary"), None)
    secondary_items = [
        item for item in evaluated if item["target_role"] == "secondary" and item["required"]
    ]
    important_items = [item for item in evaluated if item["required"]]
    covered_secondary = [item for item in secondary_items if item["is_covered"]]
    required_secondary_count = min(3, len(secondary_items))
    if len(secondary_items) >= 3:
        required_secondary_count = 3
    elif len(secondary_items) == 2:
        required_secondary_count = 2
    elif len(secondary_items) == 1:
        required_secondary_count = 1

    issues: list[str] = []
    if primary and not primary["is_covered"]:
        issues.append("primary_keyword_not_used_in_content")
    if len(covered_secondary) < required_secondary_count:
        issues.append("secondary_keyword_coverage_low")
    covered_important_count = sum(1 for item in important_items if item["is_covered"])
    important_ratio = covered_important_count / len(important_items) if important_items else 1.0
    if important_items and important_ratio < 0.8:
        issues.append("important_keyword_coverage_low")
    metadata_uncovered = [item for item in important_items if not item["is_metadata_covered"]]
    if metadata_uncovered:
        issues.append("important_keyword_missing_from_metadata")

    score = round(important_ratio * 100)
    return {
        "status": "blocked" if issues else "pass",
        "score": max(0, min(100, score)),
        "issues": issues,
        "evaluated_keywords": evaluated,
        "covered_important_count": covered_important_count,
        "important_keyword_count": len(important_items),
        "required_secondary_count": required_secondary_count,
        "covered_secondary_count": len(covered_secondary),
        "uncovered_important_keywords": [
            item["query"] for item in important_items if not item["is_covered"]
        ],
        "metadata_uncovered_keywords": [item["query"] for item in metadata_uncovered],
        "blocking_reasons": _blocking_reasons(issues),
        "recommended_next_actions": (
            [
                "Regenerate content so the primary and top secondary keyword targets appear naturally in their intended surfaces."
            ]
            if issues
            else []
        ),
    }


def _has_content(value: Any) -> bool:
    """Return whether a generated field contains publishable content."""
    if isinstance(value, list):
        return any(_has_content(item) for item in value)
    if isinstance(value, dict):
        return any(_has_content(item) for item in value.values())
    return bool(_coerce_str(value).strip())


def _surface_has_content(pack: dict[str, Any], surface: str) -> bool:
    """Check whether a content pack has generated output for one surface."""
    return any(_has_content(pack.get(field)) for field in _SURFACE_OUTPUT_FIELDS.get(surface, ()))


def _surface_issue_prefixes(surface: str) -> tuple[str, ...]:
    """Return issue prefixes tied to one content surface."""
    return {
        "metadata": ("meta_", "metadata_"),
        "product_description": ("description_", "product_description_"),
        "faq": ("faq_", "unjustified_faq"),
        "geo_answer": ("geo_",),
        "blog": ("blog_",),
    }.get(surface, (surface,))


def _build_surface_statuses(
    *,
    plan: dict[str, Any],
    pack: dict[str, Any],
    issues: list[str],
    publish_blockers: list[str],
) -> dict[str, dict[str, Any]]:
    """Assign review/publish/block status to each generated surface."""
    statuses: dict[str, dict[str, Any]] = {}
    blocker_set = set(publish_blockers)
    for surface in _SURFACE_OUTPUT_FIELDS:
        enabled = _enabled_surface(plan, surface, default=surface == "metadata")
        has_content = _surface_has_content(pack, surface)
        reason = ""
        decision = plan.get(surface)
        if isinstance(decision, dict):
            reason = _coerce_str(decision.get("reason", ""))
        surface_issues = [
            issue
            for issue in issues
            if issue.startswith(_surface_issue_prefixes(surface))
            or issue == _SURFACE_BLOCKED_ISSUES.get(surface)
        ]
        if not enabled:
            status = "blocked"
        elif blocker_set:
            status = "blocked"
        elif has_content and not surface_issues:
            status = "publish_ready"
        elif has_content:
            status = "ready_for_review"
        else:
            status = "draft_only"
        statuses[surface] = {
            "status": status,
            "generate": enabled,
            "has_content": has_content,
            "reason": reason,
            "issues": surface_issues,
        }
    return statuses


def _blocking_reasons(issues: list[str]) -> list[str]:
    """Translate blocking issue codes into concise merchant-readable reasons."""
    reasons: list[str] = []
    for issue in issues:
        reason = _BLOCKING_REASON_LABELS.get(issue)
        if reason and reason not in reasons:
            reasons.append(reason)
    return reasons


def _recommended_next_actions(
    *,
    issues: list[str],
    merchant_questions: list[dict[str, Any]],
) -> list[str]:
    """Suggest concrete next actions that can unblock publication readiness."""
    actions: list[str] = []
    if any(
        issue in issues for issue in ("unsupported_product_claims", "unverified_claim_reference")
    ):
        actions.append(
            "Remove unsupported product claims or attach them to confirmed Shopify facts."
        )
    if "faq_blocked_missing_evidence" in issues:
        actions.append("Answer the merchant questions needed before publishing a FAQ.")
    if "product_fact_conflict" in issues:
        actions.append(
            "Validate the conflicting product attributes before generating publishable copy."
        )
    if "product_consistency_below_threshold" in issues:
        actions.append("Regenerate the proposal using only confirmed product facts.")
    if any(
        issue in issues
        for issue in (
            "primary_keyword_not_used_in_content",
            "secondary_keyword_coverage_low",
            "important_keyword_coverage_low",
            "important_keyword_missing_from_metadata",
        )
    ):
        actions.append(
            "Regenerate content so selected keywords are naturally covered in matching surfaces."
        )
    for question in merchant_questions[:3]:
        field_key = _coerce_str(question.get("field_key") or question.get("key", ""))
        if field_key:
            actions.append(f"Complete merchant field: {field_key}.")
    return actions[:6]


def _normalize_merchant_questions(questions: list[dict[str, Any]] | Any) -> list[dict[str, Any]]:
    """Normalize merchant questions with both legacy key and field_key."""
    normalized: list[dict[str, Any]] = []
    source_questions = questions if isinstance(questions, list) else []
    for item in source_questions:
        if not isinstance(item, dict):
            continue
        field_key = _coerce_str(item.get("field_key") or item.get("key", "")).strip()
        if not field_key:
            continue
        normalized.append(
            {
                "key": field_key,
                "field_key": field_key,
                "question": _coerce_str(item.get("question", "")),
                "placeholder": _coerce_str(item.get("placeholder", "")),
                "why_it_matters": _coerce_str(item.get("why_it_matters", "")),
                "target_keyword": _coerce_str(item.get("target_keyword", "")),
                "unlocks_surfaces": _coerce_str_list(item.get("unlocks_surfaces", [])),
            }
        )
    return normalized


def _confirmed_fact_summary(confirmed_facts: list[dict[str, Any]]) -> str:
    """Return a compact confirmed-fact summary for generated FAQ fallbacks."""
    for fact in confirmed_facts:
        if not isinstance(fact, dict) or fact.get("confidence") != "confirmed":
            continue
        if fact.get("key") == "description":
            text = _coerce_str(fact.get("value", "")).strip()
            if text:
                return text[:220]
    for fact in confirmed_facts:
        if not isinstance(fact, dict) or fact.get("confidence") != "confirmed":
            continue
        key = _coerce_str(fact.get("key", "")).strip()
        value = _coerce_str(fact.get("value", "")).strip()
        if key and value:
            return f"{key}: {value[:180]}"
    return ""


def _ensure_mandatory_faq(
    pack: dict[str, Any],
    *,
    confirmed_facts: list[dict[str, Any]],
) -> None:
    """Generate a draft FAQ from GEO/AI questions when the LLM left it empty."""
    existing = _coerce_faq(pack.get("proposed_faq", []))
    questions: list[str] = []
    for item in _coerce_geo_questions(pack.get("geo_questions", [])):
        question = _coerce_str(item.get("question", "")).strip()
        if question and question not in questions:
            questions.append(question)
    for keyword in pack.get("seo_keywords", []) or []:
        if not isinstance(keyword, dict):
            continue
        for question in keyword.get("paa_questions", []) or []:
            question = _coerce_str(question).strip()
            if question and question not in questions:
                questions.append(question)
    primary = next(
        (
            _coerce_str(keyword.get("query", "")).strip()
            for keyword in pack.get("seo_keywords", []) or []
            if isinstance(keyword, dict) and keyword.get("query")
        ),
        "",
    )
    fallback_questions = [
        f"Qu'est-ce que {primary} ?" if primary else "",
        f"Comment choisir {primary} ?" if primary else "",
        f"À qui s'adresse {primary} ?" if primary else "",
        f"Quels faits vérifier avant d'acheter {primary} ?" if primary else "",
        f"Comment utiliser {primary} au quotidien ?" if primary else "",
    ]
    for question in fallback_questions:
        if question and question not in questions:
            questions.append(question)

    fact_summary = _confirmed_fact_summary(confirmed_facts)
    answer_base = (
        f"D'après les informations produit confirmées, {fact_summary}"
        if fact_summary
        else "Cette réponse doit être validée avec des faits produit confirmés avant publication."
    )
    while len(existing) < 5 and questions:
        question = questions.pop(0)
        if any(item["q"].casefold() == question.casefold() for item in existing):
            continue
        existing.append({"q": question, "a": answer_base})
    pack["proposed_faq"] = existing[:8]


def _compose_geo_pack_text(pack: dict[str, Any]) -> str:
    """Flatten the GEO pack so it can be included in the product description."""
    parts: list[str] = []
    answer = _coerce_str(pack.get("proposed_geo_answer_block", "")).strip()
    definition = _coerce_str(pack.get("proposed_geo_definition_block", "")).strip()
    quick_facts = _coerce_str_list(pack.get("proposed_geo_quick_facts", []))
    comparison_rows = [
        row for row in (pack.get("proposed_geo_comparison_table") or []) if isinstance(row, dict)
    ]
    if answer:
        parts.append(f"Réponse courte : {answer}")
    if definition:
        parts.append(definition)
    if quick_facts:
        parts.append("À retenir : " + " ; ".join(quick_facts[:5]) + ".")
    if comparison_rows:
        row_bits = []
        for row in comparison_rows[:4]:
            criterion = _coerce_str(row.get("critère") or row.get("criterion") or "").strip()
            value = _coerce_str(row.get("valeur") or row.get("value") or "").strip()
            if criterion and value:
                row_bits.append(f"{criterion}: {value}")
        if row_bits:
            parts.append("Repères comparatifs : " + " ; ".join(row_bits) + ".")
    return "\n\n".join(parts)


def _ensure_product_description_contains_geo_pack(pack: dict[str, Any]) -> None:
    """Append the generated GEO pack to the product description when available."""
    description = _coerce_str(pack.get("proposed_product_description", "")).strip()
    geo_pack = _compose_geo_pack_text(pack)
    if not description or not geo_pack:
        return
    if geo_pack.casefold() in description.casefold():
        return
    pack["proposed_product_description"] = f"{description}\n\n{geo_pack}"


def _default_blog_outline(keyword: str) -> list[str]:
    """Build a reusable article outline around one keyword intent."""
    label = keyword or "ce produit"
    return [
        f"Comprendre l'intention derrière {label}",
        f"Quand {label} est pertinent",
        "Les critères à vérifier avant de choisir",
        "Les erreurs courantes à éviter",
        "Les faits produit à confirmer",
        "Questions fréquentes des clients",
    ]


def _ensure_blog_ideas(pack: dict[str, Any]) -> None:
    """Ensure at least five blog ideas tied to selected keywords are available."""
    ideas = _coerce_blog_ideas(pack.get("proposed_blog_ideas", []))
    existing_keys = {idea["target_keyword"].casefold() for idea in ideas if idea["target_keyword"]}
    if pack.get("proposed_blog_title"):
        primary_keyword = next(
            (
                _coerce_str(keyword.get("query", "")).strip()
                for keyword in pack.get("seo_keywords", []) or []
                if isinstance(keyword, dict) and keyword.get("query")
            ),
            "",
        )
        if primary_keyword.casefold() not in existing_keys:
            ideas.insert(
                0,
                {
                    "title": _coerce_str(pack.get("proposed_blog_title", "")),
                    "target_keyword": primary_keyword,
                    "intro": _coerce_str(pack.get("proposed_blog_intro", "")),
                    "outline": _coerce_str_list(pack.get("proposed_blog_outline", []))
                    or _default_blog_outline(primary_keyword),
                },
            )
            existing_keys.add(primary_keyword.casefold())
    for keyword in pack.get("seo_keywords", []) or []:
        if len(ideas) >= 5:
            break
        if not isinstance(keyword, dict):
            continue
        query = _clean_keyword_query(keyword.get("query", ""))
        if not query or query.casefold() in existing_keys:
            continue
        ideas.append(
            {
                "title": f"Guide : {query}",
                "target_keyword": query,
                "intro": f"Un guide pour répondre aux questions autour de « {query} » avec des faits vérifiables.",
                "outline": _default_blog_outline(query),
            }
        )
        existing_keys.add(query.casefold())
    for question in _coerce_geo_questions(pack.get("geo_questions", [])):
        if len(ideas) >= 5:
            break
        query = _coerce_str(question.get("question", "")).strip()
        if not query or query.casefold() in existing_keys:
            continue
        ideas.append(
            {
                "title": query.rstrip("?"),
                "target_keyword": query,
                "intro": _coerce_str(question.get("answer_angle", ""))
                or f"Une réponse structurée à la question « {query} ».",
                "outline": _default_blog_outline(query),
            }
        )
        existing_keys.add(query.casefold())
    primary_keyword = next(
        (
            _clean_keyword_query(keyword.get("query", ""))
            for keyword in pack.get("seo_keywords", []) or []
            if isinstance(keyword, dict) and keyword.get("query")
        ),
        "",
    )
    fallback_keywords = [
        f"comment choisir {primary_keyword}" if primary_keyword else "",
        f"{primary_keyword} guide d'achat" if primary_keyword else "",
        f"{primary_keyword} critères de choix" if primary_keyword else "",
        f"{primary_keyword} questions fréquentes" if primary_keyword else "",
        f"{primary_keyword} pour quel besoin" if primary_keyword else "",
    ]
    for query in fallback_keywords:
        if len(ideas) >= 5:
            break
        query = _clean_keyword_query(query)
        if not query or query.casefold() in existing_keys:
            continue
        ideas.append(
            {
                "title": f"Guide : {query}",
                "target_keyword": query,
                "intro": f"Un angle éditorial pour capter l'intention « {query} » sans transformer ce contenu en cible produit principale.",
                "outline": _default_blog_outline(query),
            }
        )
        existing_keys.add(query.casefold())
    pack["proposed_blog_ideas"] = ideas[:5]
    if ideas and not pack.get("proposed_blog_title"):
        first = ideas[0]
        pack["proposed_blog_title"] = first["title"]
        pack["proposed_blog_intro"] = first.get("intro", "")
        pack["proposed_blog_outline"] = first.get("outline", [])


def _normalize_generated_content_pack(
    pack: dict[str, Any],
    *,
    confirmed_facts: list[dict[str, Any]],
) -> dict[str, Any]:
    """Apply deterministic content surface requirements after LLM generation."""
    pack.setdefault("_original_proposed_faq", _coerce_faq(pack.get("proposed_faq", [])))
    _ensure_mandatory_faq(pack, confirmed_facts=confirmed_facts)
    _ensure_product_description_contains_geo_pack(pack)
    _ensure_blog_ideas(pack)
    return pack


def _safe_surface_value(pack: dict[str, Any], surface_plan: dict[str, Any], field: str) -> Any:
    """Return field content only when its surface is allowed by the plan."""
    surface = next(
        (name for name, fields in _SURFACE_OUTPUT_FIELDS.items() if field in fields),
        "",
    )
    if surface and not _enabled_surface(surface_plan, surface, default=surface == "metadata"):
        return [] if isinstance(pack.get(field), list) else ""
    return pack.get(field)


def _build_content_quality(
    pack: dict[str, Any],
    *,
    confirmed_facts: list[dict[str, Any]] | None = None,
    source_product_text: str = "",
    surface_plan: dict[str, Any] | None = None,
    forbidden_phrases: list[str] | None = None,
) -> dict[str, Any]:
    """Validate whether a generated SEO/GEO pack is eligible for auto-publish."""
    facts = (
        confirmed_facts if confirmed_facts is not None else list(pack.get("confirmed_facts") or [])
    )
    plan = surface_plan if surface_plan is not None else dict(pack.get("surface_plan") or {})
    merchant_questions = _normalize_merchant_questions(
        pack.get("merchant_questions")
        or pack.get("pending_questions")
        or pack.get("enrichment_questions", [])
    )
    fact_conflicts = [
        conflict for conflict in pack.get("fact_conflicts", []) if isinstance(conflict, dict)
    ]
    keyword_guardrail = (
        pack.get("keyword_guardrail") if isinstance(pack.get("keyword_guardrail"), dict) else {}
    )
    targets = [
        keyword
        for keyword in (pack.get("seo_keywords") or [])[:5]
        if isinstance(keyword, dict) and keyword.get("query")
    ]
    fields = {
        "meta_title": _coerce_str(pack.get("proposed_meta_title", "")),
        "meta_description": _coerce_str(pack.get("proposed_meta_description", "")),
        "description": _coerce_str(pack.get("proposed_product_description", "")),
        "faq": " ".join(
            f"{item.get('q', '')} {item.get('a', '')}"
            for item in _coerce_faq(pack.get("proposed_faq", []))
        ),
        "geo": _coerce_str(pack.get("proposed_geo_answer_block", "")),
        "blog": " ".join(
            [
                _coerce_str(pack.get("proposed_blog_title", "")),
                _coerce_str(pack.get("proposed_blog_intro", "")),
                *_coerce_str_list(pack.get("proposed_blog_outline", [])),
                *[
                    " ".join(
                        [
                            _coerce_str(idea.get("title", "")),
                            _coerce_str(idea.get("target_keyword", "")),
                            _coerce_str(idea.get("intro", "")),
                            *_coerce_str_list(idea.get("outline", [])),
                        ]
                    )
                    for idea in _coerce_blog_ideas(pack.get("proposed_blog_ideas", []))
                ],
            ]
        ).strip(),
    }
    claims = _coerce_claims(pack.get("claims_used", []))
    evidence_ledger, invalid_claims = _build_evidence_ledger(claims, facts)
    coverage_fields = dict(fields)
    if not _enabled_surface(plan, "metadata", default=True):
        coverage_fields.pop("meta_title", None)
        coverage_fields.pop("meta_description", None)
    if not _enabled_surface(plan, "product_description"):
        coverage_fields.pop("description", None)
    if not _enabled_surface(plan, "faq"):
        coverage_fields.pop("faq", None)
    if not _enabled_surface(plan, "geo_answer"):
        coverage_fields.pop("geo", None)
    if not _enabled_surface(plan, "blog"):
        coverage_fields.pop("blog", None)
    coverage: list[dict[str, Any]] = []
    for target in targets:
        query = str(target["query"])
        coverage_query, coverage_mode = _keyword_coverage_query(query)
        all_covered_fields = [
            field_name
            for field_name, field_text in coverage_fields.items()
            if _keyword_is_naturally_covered(query, field_text)
        ]
        adapted_fields = _adapted_keyword_fields(target, coverage_fields)
        adapted_fields_covered = [
            field_name
            for field_name in adapted_fields
            if _keyword_is_naturally_covered(query, coverage_fields.get(field_name, ""))
        ]
        coverage.append(
            {
                "query": query,
                "coverage_query": coverage_query,
                "coverage_mode": coverage_mode,
                "target_role": target.get("target_role", "supporting"),
                "surface": target.get("keyword_surface")
                or _classify_keyword_surface(target)["surface"],
                "fields": all_covered_fields,
                "adapted_fields": adapted_fields,
                "adapted_fields_covered": adapted_fields_covered,
            }
        )

    issues: list[str] = []
    advisories: list[str] = []
    if keyword_guardrail.get("status") == "blocked":
        issues.append("keyword_guardrail_blocked")
        issues.extend(
            issue
            for issue in _coerce_str_list(keyword_guardrail.get("issues", []))
            if issue not in issues
        )
    for surface, blocked_issue in _SURFACE_BLOCKED_ISSUES.items():
        if _enabled_surface(plan, surface, default=surface == "metadata"):
            continue
        if surface == "faq" or _surface_has_content(pack, surface):
            issues.append(blocked_issue)
    keyword_content_guardrail = _build_keyword_content_guardrail(
        targets=targets,
        keyword_coverage=coverage,
    )
    if keyword_content_guardrail.get("status") == "blocked":
        issues.extend(
            issue
            for issue in _coerce_str_list(keyword_content_guardrail.get("issues", []))
            if issue not in issues
        )

    primary_query = str(targets[0]["query"]) if targets else ""
    if not primary_query:
        issues.append("missing_primary_keyword_target")
    else:
        if not _keyword_is_naturally_covered(primary_query, fields["meta_title"]):
            issues.append("meta_title_missing_primary_target")
        if not _keyword_is_naturally_covered(primary_query, fields["meta_description"]):
            issues.append("meta_description_missing_primary_target")
        if _enabled_surface(plan, "product_description") and not _keyword_is_naturally_covered(
            primary_query, fields["description"]
        ):
            issues.append("description_missing_primary_target")

    if _enabled_surface(plan, "product_description"):
        if not fields["description"]:
            issues.append("missing_recommended_product_description")
        elif _content_word_count(fields["description"]) < 35:
            issues.append("product_description_too_generic")
    elif fields["description"]:
        if "product_description_blocked_missing_evidence" not in issues:
            issues.append("product_description_blocked_missing_evidence")

    paa_questions = [
        question for target in targets for question in target.get("paa_questions", []) if question
    ]
    if _enabled_surface(plan, "faq"):
        if not fields["faq"]:
            issues.append("missing_recommended_faq")
        elif primary_query and not _keyword_is_naturally_covered(primary_query, fields["faq"]):
            issues.append("faq_missing_primary_target")
        elif paa_questions and not any(
            _keyword_is_naturally_covered(question, fields["faq"]) for question in paa_questions
        ):
            issues.append("faq_missing_available_paa_question")
    elif fields["faq"]:
        if "faq_blocked_missing_evidence" not in issues:
            issues.append("faq_blocked_missing_evidence")
    if _enabled_surface(plan, "geo_answer") and not fields["geo"]:
        issues.append("missing_geo_answer_block")
    if not _enabled_surface(plan, "geo_answer") and fields["geo"]:
        if "geo_answer_blocked_missing_evidence" not in issues:
            issues.append("geo_answer_blocked_missing_evidence")
    if _enabled_surface(plan, "blog") and not fields["blog"]:
        issues.append("missing_recommended_blog_support")
    if (
        _enabled_surface(plan, "blog")
        and fields["blog"]
        and primary_query
        and not _keyword_is_naturally_covered(primary_query, fields["blog"])
    ):
        issues.append("blog_missing_primary_target")
    if not _enabled_surface(plan, "blog") and fields["blog"]:
        if "blog_blocked_missing_evidence" not in issues:
            issues.append("blog_blocked_missing_evidence")

    generated_factual_text = " ".join(
        fields[field_name]
        for field_name in ("meta_title", "meta_description", "description", "faq", "geo", "blog")
        if fields[field_name]
    )
    claim_validation = _validate_claims(
        claims=claims,
        confirmed_facts=facts,
        evidence_ledger=evidence_ledger,
        invalid_claims=invalid_claims,
        generated_text=generated_factual_text,
        source_product_text=source_product_text,
    )
    for blocker in claim_validation["publish_blockers"]:
        if blocker not in issues:
            issues.append(blocker)
    ledger_fact_keys = {str(fact["key"]) for entry in evidence_ledger for fact in entry["facts"]}
    factual_surfaces_enabled = any(
        _enabled_surface(plan, surface)
        for surface in ("product_description", "faq", "geo_answer", "blog")
    )
    supported_description = next(
        (
            _coerce_str(fact.get("value", ""))
            for fact in facts
            if isinstance(fact, dict) and fact.get("key") == "description"
        ),
        "",
    )
    has_narrative_evidence = bool(ledger_fact_keys & _NARRATIVE_FACT_KEYS) or (
        "description" in ledger_fact_keys and _content_word_count(supported_description) >= 12
    )
    if factual_surfaces_enabled and not has_narrative_evidence:
        issues.append("missing_informative_confirmed_fact")

    if (
        claim_validation["unsupported_claim_categories"]
        and "unsupported_product_claims" not in issues
    ):
        issues.append("unsupported_product_claims")
    if fact_conflicts:
        issues.append("product_fact_conflict")
    if primary_query and fields["description"].lower().count(primary_query.lower()) > 3:
        issues.append("keyword_stuffing_risk")
    if any(
        phrase.strip().casefold() in generated_factual_text.casefold()
        for phrase in (forbidden_phrases or [])
        if phrase.strip()
    ):
        issues.append("forbidden_promise_detected")
    if fields["meta_title"] and not 30 <= len(fields["meta_title"]) <= 65:
        advisories.append("meta_title_length_outside_guideline")
    if fields["meta_description"] and not 70 <= len(fields["meta_description"]) <= 165:
        advisories.append("meta_description_length_outside_guideline")
    if _coerce_str(pack.get("confidence", "low"), "low") == "low":
        issues.append("low_generation_confidence")

    product_consistency_score = int(claim_validation["product_consistency_score"])
    if any(issue.endswith("_blocked_missing_evidence") for issue in issues):
        product_consistency_score = max(0, product_consistency_score - 15)
    if "missing_informative_confirmed_fact" in issues:
        product_consistency_score = max(0, product_consistency_score - 20)
    if fact_conflicts:
        product_consistency_score = max(0, product_consistency_score - 45)
    if product_consistency_score < 70 and "product_consistency_below_threshold" not in issues:
        issues.append("product_consistency_below_threshold")

    publish_blockers = list(claim_validation["publish_blockers"])
    for critical_issue in (
        "product_consistency_below_threshold",
        "product_fact_conflict",
        "faq_blocked_missing_evidence",
        "keyword_guardrail_blocked",
        "keyword_customer_need_alignment_low",
        "insufficient_product_page_keyword_targets",
        "keyword_targets_too_indirect",
        "primary_keyword_not_used_in_content",
        "secondary_keyword_coverage_low",
        "important_keyword_coverage_low",
        "important_keyword_missing_from_metadata",
    ):
        if critical_issue in issues and critical_issue not in publish_blockers:
            publish_blockers.append(critical_issue)

    coverage_ratio = (
        sum(1 for item in coverage if item["adapted_fields_covered"]) / len(coverage)
        if coverage
        else 0.0
    )
    geo_surface_count = sum(
        1
        for field_name in ("faq", "geo", "blog")
        if fields.get(field_name) and field_name in coverage_fields
    )
    seo_geo_score = max(0, min(100, round(coverage_ratio * 70 + geo_surface_count * 10)))
    publish_ready = not issues
    publish_status = (
        "blocked" if publish_blockers else "publish_ready" if publish_ready else "ready_for_review"
    )
    surface_statuses = _build_surface_statuses(
        plan=plan,
        pack=pack,
        issues=issues,
        publish_blockers=publish_blockers,
    )
    blocking_reasons = _blocking_reasons(issues)
    next_actions = _recommended_next_actions(
        issues=issues,
        merchant_questions=merchant_questions,
    )

    return {
        "publish_ready": publish_ready,
        "auto_apply_allowed": publish_ready and publish_status == "publish_ready",
        "final_status": publish_status,
        "publish_status": publish_status,
        "blocking_reasons": blocking_reasons,
        "issues": issues,
        "advisories": advisories,
        "covered_target_count": sum(1 for item in coverage if item["adapted_fields_covered"]),
        "target_count": len(targets),
        "keyword_coverage": coverage,
        "keyword_content_guardrail": keyword_content_guardrail,
        "seo_geo_score": seo_geo_score,
        "product_consistency_score": product_consistency_score,
        "surface_statuses": surface_statuses,
        "valid_claims": claim_validation["valid_claims"],
        "unsupported_claims": claim_validation["unsupported_claims"],
        "evidence_ledger": evidence_ledger,
        "invalid_claims": invalid_claims,
        "unsupported_claim_categories": claim_validation["unsupported_claim_categories"],
        "publish_blockers": publish_blockers,
        "fact_conflicts": fact_conflicts,
        "keyword_guardrail": keyword_guardrail,
        "merchant_questions": merchant_questions,
        "pending_questions": merchant_questions,
        "recommended_next_actions": next_actions,
        "surface_plan": plan,
        "skipped_surfaces": [
            surface
            for surface in ("metadata", "product_description", "faq", "geo_answer", "blog")
            if not _enabled_surface(plan, surface, default=surface == "metadata")
        ],
    }


def _pack_generated_text(pack: dict[str, Any]) -> str:
    """Flatten generated content surfaces for lightweight reflection checks."""
    faq_text = " ".join(
        f"{item.get('q', '')} {item.get('a', '')}"
        for item in _coerce_faq(pack.get("proposed_faq", []))
    )
    return " ".join(
        part
        for part in [
            _coerce_str(pack.get("proposed_meta_title", "")),
            _coerce_str(pack.get("proposed_meta_description", "")),
            _coerce_str(pack.get("proposed_product_description", "")),
            faq_text,
            _coerce_str(pack.get("proposed_geo_answer_block", "")),
            _coerce_str(pack.get("proposed_geo_definition_block", "")),
            " ".join(_coerce_str_list(pack.get("proposed_geo_quick_facts", []))),
            _coerce_str(pack.get("proposed_blog_title", "")),
            _coerce_str(pack.get("proposed_blog_intro", "")),
            " ".join(_coerce_str_list(pack.get("proposed_blog_outline", []))),
            " ".join(
                " ".join(
                    [
                        _coerce_str(idea.get("title", "")),
                        _coerce_str(idea.get("target_keyword", "")),
                        _coerce_str(idea.get("intro", "")),
                        " ".join(_coerce_str_list(idea.get("outline", []))),
                    ]
                )
                for idea in _coerce_blog_ideas(pack.get("proposed_blog_ideas", []))
            ),
        ]
        if part
    )


def _reflection_item(
    *,
    key: str,
    question: str,
    score: int,
    status: str,
    evidence: list[str],
    recommendation: str,
) -> dict[str, Any]:
    return {
        "key": key,
        "question": question,
        "score": max(0, min(100, int(score))),
        "status": status,
        "evidence": evidence[:5],
        "recommendation": recommendation,
    }


def _build_content_reflection_attempt(
    pack: dict[str, Any],
    *,
    fields: dict[str, Any],
    business_context: str,
    business_profile: dict[str, Any] | None,
    niche_summary: str,
) -> dict[str, Any]:
    """Score generated content against business, product, SEO, GEO and actionability gates."""
    quality = (
        pack.get("content_quality")
        if isinstance(pack.get("content_quality"), dict)
        else _build_content_quality(
            pack,
            confirmed_facts=fields.get("confirmed_facts", []),
            source_product_text=fields.get("source_product_text", ""),
            surface_plan=pack.get("surface_plan", {}),
        )
    )
    generated_text = _pack_generated_text(pack)
    generated_words = _content_words(generated_text)
    product_words = _content_words(
        " ".join(
            [
                fields.get("source_product_text", ""),
                fields.get("product_title", ""),
                fields.get("merchant_label", ""),
                str(fields.get("handle", "")).replace("-", " "),
            ]
        )
    )
    overlap = len(generated_words & product_words)

    primary_keyword = next(
        (
            str(keyword.get("query", "")).strip()
            for keyword in (pack.get("seo_keywords") or [])
            if isinstance(keyword, dict) and keyword.get("target_role") == "primary"
        ),
        "",
    ) or next(
        (
            str(keyword.get("query", "")).strip()
            for keyword in (pack.get("seo_keywords") or [])
            if isinstance(keyword, dict) and keyword.get("query")
        ),
        "",
    )
    target_count = int(quality.get("target_count", 0) or 0)
    covered_count = int(quality.get("covered_target_count", 0) or 0)
    coverage_ratio = covered_count / target_count if target_count else 0.0
    issues = [str(issue) for issue in quality.get("issues", [])]
    blocking_fact_issues = {
        "missing_claim_evidence_ledger",
        "unverified_claim_reference",
        "unsupported_product_claims",
        "forbidden_promise_detected",
        "product_consistency_below_threshold",
        "product_fact_conflict",
        "faq_blocked_missing_evidence",
    }
    blocking_keyword_issues = {
        "primary_keyword_not_used_in_content",
        "secondary_keyword_coverage_low",
        "important_keyword_coverage_low",
        "important_keyword_missing_from_metadata",
    }

    business_terms = _content_words(
        " ".join(
            [
                business_context,
                niche_summary,
                _coerce_str((business_profile or {}).get("brand_voice", "")),
                " ".join(_coerce_str_list((business_profile or {}).get("key_themes", []))),
            ]
        )
    )
    business_overlap = len(generated_words & business_terms)
    if not business_terms:
        business_score = 70
        business_status = "needs_review"
        business_evidence = [
            "No validated business context available for strong alignment scoring."
        ]
    else:
        business_score = 85 if business_overlap >= 3 else 68 if business_overlap >= 1 else 45
        business_status = "pass" if business_score >= _REFLECTION_THRESHOLD else "needs_review"
        business_evidence = [
            f"{business_overlap} business context terms found in generated content.",
            f"Niche context: {niche_summary or 'not set'}",
        ]

    product_score = 88 if overlap >= 4 else 70 if overlap >= 2 else 45
    product_score = min(product_score, int(quality.get("product_consistency_score", product_score)))
    if any(issue in blocking_fact_issues for issue in issues):
        product_score = min(product_score, 45)
    if product_score < 70:
        product_score = min(product_score, 45)
    product_status = (
        "blocked"
        if any(issue in blocking_fact_issues for issue in issues) or product_score < 70
        else ("pass" if product_score >= _REFLECTION_THRESHOLD else "needs_review")
    )

    seo_score = round(45 + coverage_ratio * 45)
    if primary_keyword and (
        _keyword_is_naturally_covered(
            primary_keyword, _coerce_str(pack.get("proposed_meta_title", ""))
        )
        or _keyword_is_naturally_covered(
            primary_keyword, _coerce_str(pack.get("proposed_meta_description", ""))
        )
    ):
        seo_score += 10
    if any(issue in blocking_keyword_issues for issue in issues):
        seo_score = min(seo_score, 60)
    seo_score = max(0, min(100, seo_score))

    geo_surfaces = [
        bool(_coerce_faq(pack.get("proposed_faq", []))),
        bool(_coerce_str(pack.get("proposed_geo_answer_block", ""))),
        bool(_coerce_str(pack.get("proposed_geo_definition_block", ""))),
        bool(_coerce_str_list(pack.get("proposed_geo_quick_facts", []))),
    ]
    geo_score = 35 + sum(geo_surfaces) * 15
    if any(
        keyword.get("serp_feature_targets")
        for keyword in (pack.get("seo_keywords") or [])
        if isinstance(keyword, dict)
    ):
        geo_score += 5
    geo_score = max(0, min(100, geo_score))

    actionability_score = 50
    if pack.get("proposed_meta_title") and pack.get("proposed_meta_description"):
        actionability_score += 20
    if pack.get("recommended_content_actions"):
        actionability_score += 15
    if not issues:
        actionability_score += 15
    actionability_score = max(0, min(100, actionability_score))

    items = [
        _reflection_item(
            key="business_alignment",
            question=_REFLECTION_QUESTIONS[0]["question"],
            score=business_score,
            status=business_status,
            evidence=business_evidence,
            recommendation=(
                "Use the validated business profile vocabulary and strategic angles more explicitly."
                if business_score < _REFLECTION_THRESHOLD
                else "Business alignment is sufficient."
            ),
        ),
        _reflection_item(
            key="product_consistency",
            question=_REFLECTION_QUESTIONS[1]["question"],
            score=product_score,
            status=product_status,
            evidence=[
                f"{overlap} product terms found in generated content.",
                f"Quality issues: {', '.join(issues) if issues else 'none'}",
            ],
            recommendation=(
                "Rewrite using only product facts and remove unsupported claims."
                if product_score < _REFLECTION_THRESHOLD
                else "Product consistency is sufficient."
            ),
        ),
        _reflection_item(
            key="seo_potential",
            question=_REFLECTION_QUESTIONS[2]["question"],
            score=seo_score,
            status="pass" if seo_score >= _REFLECTION_THRESHOLD else "needs_review",
            evidence=[
                f"{covered_count}/{target_count} keyword targets covered.",
                f"Primary keyword: {primary_keyword or 'missing'}",
            ],
            recommendation=(
                "Use the primary and top secondary targets naturally in their intended surfaces."
                if seo_score < _REFLECTION_THRESHOLD
                else "SEO target coverage is sufficient."
            ),
        ),
        _reflection_item(
            key="geo_potential",
            question=_REFLECTION_QUESTIONS[3]["question"],
            score=geo_score,
            status="pass" if geo_score >= _REFLECTION_THRESHOLD else "needs_review",
            evidence=[f"{sum(geo_surfaces)}/4 GEO surfaces present."],
            recommendation=(
                "Add extractable FAQ, definition, quick facts or answer blocks."
                if geo_score < _REFLECTION_THRESHOLD
                else "GEO extractability is sufficient."
            ),
        ),
        _reflection_item(
            key="merchant_actionability",
            question=_REFLECTION_QUESTIONS[4]["question"],
            score=actionability_score,
            status="pass" if actionability_score >= _REFLECTION_THRESHOLD else "needs_review",
            evidence=[
                "Metadata present."
                if pack.get("proposed_meta_title") and pack.get("proposed_meta_description")
                else "Metadata incomplete.",
                f"Recommended actions: {len(pack.get('recommended_content_actions') or [])}",
            ],
            recommendation=(
                "Make the proposal more concrete and reviewable for the merchant."
                if actionability_score < _REFLECTION_THRESHOLD
                else "Merchant actionability is sufficient."
            ),
        ),
    ]
    final_score = round(sum(item["score"] for item in items) / len(items))
    critical_block = (
        product_score < 70
        or quality.get("publish_status") == "blocked"
        or bool(quality.get("publish_blockers"))
    )
    final_status = (
        "blocked"
        if critical_block or any(item["status"] == "blocked" for item in items)
        else "pass"
        if final_score >= _REFLECTION_THRESHOLD
        else "needs_retry"
    )
    return {
        "score": final_score,
        "status": final_status,
        "questions": items,
        "quality_issues": issues,
        "seo_geo_score": quality.get("seo_geo_score", seo_score),
        "product_consistency_score": product_score,
        "publish_status": quality.get("publish_status", "blocked"),
        "blocking_reasons": quality.get("blocking_reasons", []),
        "next_actions": quality.get("recommended_next_actions", []),
    }


def _build_reflection_retry_prompt(
    *,
    product_title: str,
    niche_summary: str,
    pack: dict[str, Any],
    reflection_attempt: dict[str, Any],
    confirmed_facts: list[dict[str, Any]],
    surface_plan: dict[str, Any],
) -> str:
    """Build a targeted retry prompt from the failed reflection attempt."""
    keywords = [
        str(keyword.get("query", "")).strip()
        for keyword in (pack.get("seo_keywords") or [])[:6]
        if isinstance(keyword, dict) and keyword.get("query")
    ]
    failed_questions = [
        item
        for item in reflection_attempt.get("questions", [])
        if isinstance(item, dict) and item.get("score", 100) < _REFLECTION_THRESHOLD
    ]
    failed_lines = [
        f"- {item.get('key')}: score {item.get('score')}/100; {item.get('recommendation')}"
        for item in failed_questions
    ]
    facts_text = (
        "; ".join(
            f"{fact.get('key')}: {_coerce_str(fact.get('value', ''))[:140]}"
            for fact in confirmed_facts
            if isinstance(fact, dict) and fact.get("key")
        )
        or "no confirmed facts"
    )
    return (
        "You are improving an existing Shopify SEO/GEO content proposal after a quality reflection.\n"
        f"PRODUCT: {product_title}\n"
        f"NICHE: {niche_summary or 'not set'}\n"
        f"TARGET KEYWORDS: {', '.join(keywords) if keywords else 'none'}\n"
        "KEYWORD COVERAGE RULE: use the primary and top secondary targets naturally in their intended surfaces. "
        "For commercial modifiers like 'acheter', cover the buying intent with product-page copy instead of forcing the exact word.\n"
        f"CONFIRMED FACTS ONLY: {facts_text}\n"
        f"SURFACE PLAN: {json.dumps(surface_plan, ensure_ascii=False)}\n\n"
        "PREVIOUS PROPOSAL:\n"
        f"{json.dumps({k: pack.get(k) for k in _PASS2_KEYS}, ensure_ascii=False)[:6000]}\n\n"
        "FAILED REFLECTION POINTS TO FIX WITHOUT INTRODUCING NEW UNSUPPORTED CLAIMS:\n"
        + ("\n".join(failed_lines) if failed_lines else "- Improve clarity and keyword coverage.")
        + "\n\nReturn valid JSON only with the same content keys. Keep factual claims grounded in confirmed facts."
    )


def _run_reflection_test_loop(
    pack: dict[str, Any],
    *,
    llm_router: Any,
    fields: dict[str, Any],
    business_context: str,
    business_profile: dict[str, Any] | None,
    niche_summary: str,
    forbidden_phrases: list[str],
) -> dict[str, Any]:
    """Run post-generation reflection and at most one targeted regeneration."""
    attempts: list[dict[str, Any]] = []
    retry_count = 0

    for attempt_idx in range(_REFLECTION_MAX_RETRIES + 1):
        pack = _normalize_generated_content_pack(
            pack,
            confirmed_facts=fields.get("confirmed_facts", []),
        )
        pack["content_quality"] = _build_content_quality(
            pack,
            confirmed_facts=fields.get("confirmed_facts", []),
            source_product_text=fields.get("source_product_text", ""),
            surface_plan=pack.get("surface_plan", {}),
            forbidden_phrases=forbidden_phrases,
        )
        attempt = _build_content_reflection_attempt(
            pack,
            fields=fields,
            business_context=business_context,
            business_profile=business_profile,
            niche_summary=niche_summary,
        )
        attempt["attempt"] = attempt_idx + 1
        attempts.append(attempt)
        needs_retry = (
            attempt["status"] != "pass"
            or attempt["score"] < _REFLECTION_THRESHOLD
            or not pack["content_quality"].get("publish_ready", False)
        )
        if not needs_retry or attempt_idx >= _REFLECTION_MAX_RETRIES or llm_router is None:
            break
        retry_prompt = _build_reflection_retry_prompt(
            product_title=fields["product_title"],
            niche_summary=niche_summary,
            pack=pack,
            reflection_attempt=attempt,
            confirmed_facts=fields.get("confirmed_facts", []),
            surface_plan=pack.get("surface_plan", {}),
        )
        pack = _complete_json(
            llm_router,
            retry_prompt,
            _PASS2_KEYS,
            pack,
            fields["product_title"],
            max_tokens=8192,
            temperature=0.0,
        )
        pack = _normalize_generated_content_pack(
            pack,
            confirmed_facts=fields.get("confirmed_facts", []),
        )
        retry_count += 1

    final_attempt = attempts[-1] if attempts else {"score": 0, "status": "blocked"}
    pack["content_guardrail_reflection"] = {
        "enabled": True,
        "threshold": _REFLECTION_THRESHOLD,
        "max_retries": _REFLECTION_MAX_RETRIES,
        "retry_count": retry_count,
        "final_score": final_attempt.get("score", 0),
        "final_status": final_attempt.get("status", "blocked"),
        "seo_geo_score": final_attempt.get("seo_geo_score", 0),
        "product_consistency_score": final_attempt.get("product_consistency_score", 0),
        "publish_status": final_attempt.get("publish_status", "blocked"),
        "blocking_reasons": final_attempt.get("blocking_reasons", []),
        "next_actions": final_attempt.get("next_actions", []),
        "questions": list(_REFLECTION_QUESTIONS),
        "attempts": attempts,
    }
    return pack


def _apply_catalog_content_conflicts(
    product_results: list[dict[str, Any]],
    active_products: list[dict[str, Any]],
) -> None:
    """Block auto-publication for duplicated proposals and competing primary targets."""
    seen_proposed: dict[tuple[str, str], str] = {}
    existing_metadata: dict[tuple[str, str], str] = {}
    for product in active_products:
        product_id = str(product.get("id", ""))
        seo = product.get("seo") if isinstance(product.get("seo"), dict) else {}
        for field_name, value in (
            ("meta_title", seo.get("title")),
            ("meta_description", seo.get("description")),
        ):
            normalized = _coerce_str(value).strip().casefold()
            if normalized:
                existing_metadata[(field_name, normalized)] = product_id

    primary_owner: dict[str, str] = {}
    sorted_results = sorted(
        product_results,
        key=lambda result: int(result.get("opportunity_score", 0) or 0),
        reverse=True,
    )
    for result in sorted_results:
        product_id = str(result.get("product_id", ""))
        pack = result.get("content_test_pack", {})
        quality = pack.get("content_quality")
        if not isinstance(quality, dict):
            continue

        primary_keywords = [
            keyword
            for keyword in result.get("seo_keywords", [])
            if isinstance(keyword, dict) and keyword.get("target_role") == "primary"
        ]
        if primary_keywords:
            primary_query = str(primary_keywords[0].get("query", "")).strip().casefold()
            if primary_query in primary_owner and primary_owner[primary_query] != product_id:
                _add_quality_issue(quality, "primary_target_cannibalization_risk")
            else:
                primary_owner[primary_query] = product_id

        for field_name, value in (
            ("meta_title", pack.get("proposed_meta_title")),
            ("meta_description", pack.get("proposed_meta_description")),
        ):
            normalized = _coerce_str(value).strip().casefold()
            if not normalized:
                continue
            existing_owner = existing_metadata.get((field_name, normalized))
            if existing_owner and existing_owner != product_id:
                _add_quality_issue(quality, f"duplicate_existing_{field_name}")
            proposed_key = (field_name, normalized)
            proposed_owner = seen_proposed.get(proposed_key)
            if proposed_owner and proposed_owner != product_id:
                _add_quality_issue(quality, f"duplicate_proposed_{field_name}")
            else:
                seen_proposed[proposed_key] = product_id

    seen_descriptions: list[tuple[str, frozenset[str]]] = []
    for result in sorted_results:
        product_id = str(result.get("product_id", ""))
        pack = result.get("content_test_pack", {})
        quality = pack.get("content_quality")
        if not isinstance(quality, dict):
            continue
        words = _content_words(_coerce_str(pack.get("proposed_product_description", "")))
        if len(words) < 15:
            continue
        for existing_id, existing_words in seen_descriptions:
            overlap = len(words & existing_words) / max(len(words | existing_words), 1)
            if product_id != existing_id and overlap >= 0.8:
                _add_quality_issue(quality, "near_duplicate_product_description")
                break
        seen_descriptions.append((product_id, words))


def _sync_result_quality_fields(product_results: list[dict[str, Any]]) -> None:
    """Mirror content quality gates onto stable top-level product output fields."""
    for product in product_results:
        pack = product.get("content_test_pack")
        if not isinstance(pack, dict):
            continue
        quality = pack.get("content_quality")
        if not isinstance(quality, dict):
            continue
        publish_ready = bool(quality.get("publish_ready", False))
        final_status = _coerce_str(quality.get("final_status", "blocked"), "blocked")
        if not publish_ready and final_status == "publish_ready":
            final_status = "ready_for_review"
            quality["final_status"] = final_status
            quality["publish_status"] = final_status
        auto_apply_allowed = bool(quality.get("auto_apply_allowed", False)) and publish_ready
        quality["auto_apply_allowed"] = auto_apply_allowed
        product["publish_ready"] = publish_ready
        product["auto_apply_allowed"] = auto_apply_allowed
        product["final_status"] = final_status
        product["blocking_reasons"] = quality.get("blocking_reasons", [])
        product["surface_statuses"] = quality.get("surface_statuses", {})
        product["unsupported_claims"] = quality.get("unsupported_claims", [])
        product["recommended_next_actions"] = quality.get("recommended_next_actions", [])


def _impressions_bucket(impressions: int) -> int:
    """Quick demand-score bucket from GSC impressions (free proxy)."""
    if impressions >= 10000:
        return 95
    if impressions >= 5000:
        return 85
    if impressions >= 1000:
        return 75
    if impressions >= 500:
        return 65
    if impressions >= 100:
        return 50
    if impressions >= 10:
        return 35
    return 20


def _volume_bucket(volume: int) -> int:
    """Demand-score bucket from a real monthly search volume."""
    if volume >= 100000:
        return 100
    if volume >= 10000:
        return 90
    if volume >= 1000:
        return 75
    if volume >= 100:
        return 55
    if volume >= 10:
        return 30
    return 10


def _fallback_pack(
    product_title: str, current_meta_title: str, current_meta_description: str
) -> dict[str, Any]:
    # proposed_* fields are intentionally empty: using current Shopify values here would
    # make truncated/failed LLM responses look like successful proposals in the UI.
    return {
        "product_summary": "",
        "target_customer": "",
        "buying_intents": [],
        "seo_keywords": [],
        "geo_questions": [],
        "proposed_meta_title": "",
        "proposed_meta_description": "",
        "proposed_image_alts": [],
        "proposed_product_title_if_different": product_title,
        "proposed_product_description": "",
        "proposed_faq": [],
        "proposed_geo_answer_block": "",
        "proposed_blog_title": "",
        "proposed_blog_outline": [],
        "proposed_blog_intro": "",
        "recommended_content_actions": [],
        "facts_used": [],
        "facts_missing": [],
        "claims_used": [],
        "confidence": "low",
    }


def _build_product_result(
    product: dict[str, Any],
    opportunity: dict[str, Any],
    llm_pack: dict[str, Any],
    shop: str,
    business_profile_context_hash: str | None = None,
) -> dict[str, Any]:
    product_id = str(product.get("id", ""))
    product_title = product.get("title", "")
    handle = product.get("handle", "")
    raw_seo = product.get("seo")
    seo: dict[str, Any] = raw_seo if isinstance(raw_seo, dict) else {}
    current_meta_title = seo.get("title") or product_title
    current_meta_description = seo.get("description") or ""
    body_html = (
        product.get("body_html")
        or product.get("descriptionHtml")
        or product.get("description")
        or ""
    )
    description_summary = _strip_html(body_html)[:200]

    surface_plan = dict(llm_pack.get("surface_plan") or {})
    content_quality = (
        llm_pack.get("content_quality") if isinstance(llm_pack.get("content_quality"), dict) else {}
    )
    merchant_questions = _normalize_merchant_questions(
        llm_pack.get("merchant_questions")
        or llm_pack.get("pending_questions")
        or llm_pack.get("enrichment_questions", [])
    )
    keyword_surface_mapping = (
        llm_pack.get("keyword_surface_mapping")
        if isinstance(llm_pack.get("keyword_surface_mapping"), list)
        else _build_keyword_surface_mapping(_coerce_seo_keywords(llm_pack.get("seo_keywords", [])))
    )
    proposed_meta_title = _coerce_str(
        _safe_surface_value(llm_pack, surface_plan, "proposed_meta_title")
    )
    proposed_meta_description = _coerce_str(
        _safe_surface_value(llm_pack, surface_plan, "proposed_meta_description")
    )
    proposed_product_description = _coerce_str(
        _safe_surface_value(llm_pack, surface_plan, "proposed_product_description")
    )
    proposed_faq = _coerce_faq(_safe_surface_value(llm_pack, surface_plan, "proposed_faq"))
    proposed_blog_ideas = _coerce_blog_ideas(
        _safe_surface_value(llm_pack, surface_plan, "proposed_blog_ideas")
    )
    product_images = _extract_product_images(product)
    sorted_keywords = sorted(
        _coerce_seo_keywords(llm_pack.get("seo_keywords", [])),
        key=lambda k: int(k.get("target_rank", 999) or 999),
    )
    keyword_queries = [
        query for k in sorted_keywords if (query := _coerce_str(k.get("query", "")).strip())
    ][:8]
    proposed_image_alts = _fill_image_alts(
        _safe_surface_value(llm_pack, surface_plan, "proposed_image_alts"),
        product_images,
        product_title,
        keyword_queries,
    )
    confirmed_facts_list = llm_pack.get("confirmed_facts", []) or []
    schema_jsonld: dict[str, Any] = {}
    try:
        from app.market_analysis import schema_builder as _sb  # noqa: PLC0415

        product_schema = _sb.build_product_schema(
            product=product,
            confirmed_facts=confirmed_facts_list,
            shop=shop,
            meta_description=proposed_meta_description,
        )
        faq_schema = _sb.build_faq_schema(
            _coerce_faq(llm_pack.get("_original_proposed_faq", proposed_faq))
        )
        schema_jsonld = {"product": product_schema}
        if faq_schema is not None:
            schema_jsonld["faq"] = faq_schema
    except Exception as exc:
        logger.warning("Skipping market analysis JSON-LD for product %s: %s", product_id, exc)

    publish_ready = bool(content_quality.get("publish_ready", False))
    final_status = _coerce_str(content_quality.get("final_status", "blocked"), "blocked")
    auto_apply_allowed = bool(content_quality.get("auto_apply_allowed", False)) and publish_ready
    blocking_reasons = _coerce_str_list(content_quality.get("blocking_reasons", []))
    fact_conflicts = [
        conflict for conflict in llm_pack.get("fact_conflicts", []) if isinstance(conflict, dict)
    ]
    competitor_crawl_insights = (
        llm_pack.get("competitor_crawl_insights")
        if isinstance(llm_pack.get("competitor_crawl_insights"), dict)
        else {
            "enabled": False,
            "sample_size": 0,
            "top_urls": [],
            "dominant_patterns": {},
            "merchant_gaps": [],
            "priority_boost_total": 0,
            "prompt_summary": "",
        }
    )

    # GEO readiness score: current state vs. what it becomes once the proposed
    # meta title / meta description / product description are applied. The
    # products page shows this and interpolates current→potential as fields are
    # validated, so the score rises with each applied optimization.
    from app.geo.readiness import score_product_readiness  # noqa: PLC0415

    # Merchant-confirmed fact keys (from enrichment form answers) are injected so
    # the score reflects what the merchant has validated, not only the Shopify snapshot.
    _merchant_fact_keys: set[str] = {
        str(f.get("key"))
        for f in confirmed_facts_list
        if isinstance(f, dict) and f.get("key") and f.get("source") != "shopify_snapshot"
    }
    _readiness = score_product_readiness(product, extra_fact_keys=_merchant_fact_keys or None)
    geo_score = _readiness["readiness_score"]
    geo_score_components = _readiness.get("components", {})
    improved_product = {
        **product,
        "seo": {
            **seo,
            "title": proposed_meta_title or current_meta_title,
            "description": proposed_meta_description or current_meta_description,
        },
        "body_html": proposed_product_description or body_html,
    }
    geo_score_potential = max(
        geo_score,
        score_product_readiness(improved_product, extra_fact_keys=_merchant_fact_keys or None)[
            "readiness_score"
        ],
    )

    # Per-field readiness contribution: how much each applied field alone lifts
    # the score over the current state. The products page sums the deltas of the
    # fields actually validated, so the displayed score moves by each field's
    # real value instead of a diluted count fraction. image_alts is omitted (it
    # does not feed the readiness scorer).
    def _field_delta(merged: dict[str, Any]) -> int:
        return max(
            0,
            score_product_readiness(merged, extra_fact_keys=_merchant_fact_keys or None)[
                "readiness_score"
            ]
            - geo_score,
        )

    geo_score_field_deltas = {
        "meta_title": _field_delta(
            {**product, "seo": {**seo, "title": proposed_meta_title or current_meta_title}}
        )
        if proposed_meta_title
        else 0,
        "meta_description": _field_delta(
            {
                **product,
                "seo": {**seo, "description": proposed_meta_description or current_meta_description},
            }
        )
        if proposed_meta_description
        else 0,
        "description": _field_delta(
            {**product, "body_html": proposed_product_description or body_html}
        )
        if proposed_product_description
        else 0,
    }

    return {
        "product_id": product_id,
        "product_title": product_title,
        "product_handle": handle,
        "product_url": f"/products/{handle}",
        "product_summary": _coerce_str(llm_pack.get("product_summary", "")),
        "target_customer": _coerce_str(llm_pack.get("target_customer", "")),
        "buying_intents": _coerce_str_list(llm_pack.get("buying_intents", [])),
        "seo_keywords": _coerce_seo_keywords(llm_pack.get("seo_keywords", [])),
        "geo_questions": _coerce_geo_questions(llm_pack.get("geo_questions", [])),
        "publish_ready": publish_ready,
        "auto_apply_allowed": auto_apply_allowed,
        "final_status": final_status,
        "blocking_reasons": blocking_reasons,
        "surface_statuses": content_quality.get("surface_statuses", {}),
        "unsupported_claims": content_quality.get("unsupported_claims", []),
        "fact_conflicts": fact_conflicts,
        "merchant_questions": merchant_questions,
        "recommended_next_actions": content_quality.get("recommended_next_actions", []),
        "keyword_surface_mapping": keyword_surface_mapping,
        "keyword_guardrail": llm_pack.get("keyword_guardrail", {}),
        "keyword_content_guardrail": content_quality.get("keyword_content_guardrail", {}),
        "trend_signals": opportunity.get("trend_signals", []),
        "competitor_signals": opportunity.get("signals", []),
        "competitor_crawl_insights": competitor_crawl_insights,
        "competitor_pattern_boost": int(
            competitor_crawl_insights.get("priority_boost_total", 0) or 0
        ),
        "competitor_pattern_gaps": competitor_crawl_insights.get("merchant_gaps", []),
        "content_test_pack": {
            "current_meta_title": current_meta_title,
            "proposed_meta_title": proposed_meta_title,
            "current_meta_description": current_meta_description,
            "proposed_meta_description": proposed_meta_description,
            "current_product_images": product_images,
            "proposed_image_alts": proposed_image_alts,
            "current_product_title": product_title,
            "proposed_product_title": _coerce_str(
                llm_pack.get("proposed_product_title_if_different", product_title)
            ),
            "current_product_description_summary": description_summary,
            "proposed_product_description": proposed_product_description,
            "proposed_faq": proposed_faq,
            "proposed_geo_answer_block": _coerce_str(
                _safe_surface_value(llm_pack, surface_plan, "proposed_geo_answer_block")
            ),
            "proposed_geo_definition_block": _coerce_str(
                _safe_surface_value(llm_pack, surface_plan, "proposed_geo_definition_block")
            ),
            "proposed_geo_quick_facts": _coerce_str_list(
                _safe_surface_value(llm_pack, surface_plan, "proposed_geo_quick_facts")
            ),
            "proposed_geo_comparison_table": [
                {
                    "critère": _coerce_str(row.get("critère") or row.get("criterion") or ""),
                    "valeur": _coerce_str(row.get("valeur") or row.get("value") or ""),
                }
                for row in (
                    _safe_surface_value(
                        llm_pack,
                        surface_plan,
                        "proposed_geo_comparison_table",
                    )
                    or []
                )
                if isinstance(row, dict)
                and (row.get("critère") or row.get("criterion"))
                and (row.get("valeur") or row.get("value"))
            ],
            "proposed_schema_jsonld": schema_jsonld,
            "proposed_blog_title": _coerce_str(
                _safe_surface_value(llm_pack, surface_plan, "proposed_blog_title")
            ),
            "proposed_blog_outline": _coerce_str_list(
                _safe_surface_value(llm_pack, surface_plan, "proposed_blog_outline")
            ),
            "proposed_blog_intro": _coerce_str(
                _safe_surface_value(llm_pack, surface_plan, "proposed_blog_intro")
            ),
            "proposed_blog_ideas": proposed_blog_ideas,
            "proposed_comparison_or_buying_guide": "",
            "recommended_internal_links": [],
            "content_risks": [],
            "facts_used": _coerce_str_list(llm_pack.get("facts_used", [])),
            "facts_missing": _coerce_str_list(llm_pack.get("facts_missing", [])),
            "claims_used": _coerce_claims(llm_pack.get("claims_used", [])),
            "confirmed_facts": confirmed_facts_list,
            "eeat_signals": llm_pack.get("eeat_signals", []),
            "surface_plan": surface_plan,
            "surface_statuses": content_quality.get("surface_statuses", {}),
            "enrichment_questions": merchant_questions,
            "merchant_questions": merchant_questions,
            "pending_questions": merchant_questions,
            "keyword_surface_mapping": keyword_surface_mapping,
            "keyword_guardrail": llm_pack.get("keyword_guardrail", {}),
            "keyword_content_guardrail": content_quality.get("keyword_content_guardrail", {}),
            "confidence": _normalize_confidence(llm_pack.get("confidence", "")) or "low",
            "content_quality": content_quality,
            "content_guardrail_reflection": llm_pack.get("content_guardrail_reflection", {}),
            "competitor_crawl_insights": competitor_crawl_insights,
            "competitor_pattern_boost": int(
                competitor_crawl_insights.get("priority_boost_total", 0) or 0
            ),
            "competitor_pattern_gaps": competitor_crawl_insights.get("merchant_gaps", []),
        },
        "recommended_content_actions": _coerce_str_list(
            llm_pack.get("recommended_content_actions", [])
        ),
        "keyword_clusters": llm_pack.get("keyword_clusters", []),
        "confidence": (
            _normalize_confidence(llm_pack.get("confidence", ""))
            or _coerce_str(opportunity.get("confidence", "low"), "low")
        ),
        "opportunity_score": opportunity.get("opportunity_score", 0),
        "geo_score": geo_score,
        "geo_score_potential": geo_score_potential,
        "geo_score_field_deltas": geo_score_field_deltas,
        "geo_score_components": geo_score_components,
        "sources_used": opportunity.get("sources_used", []),
        "business_profile_context_hash": business_profile_context_hash,
        "business_profile_context_status": (
            "current" if business_profile_context_hash else "missing_profile"
        ),
    }


def _score_active_products(
    active_products: list[dict[str, Any]],
    gsc_query_rows: list[dict[str, Any]],
    ga4_page_rows: dict[str, dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Lightweight deterministic scorer with GSC, GA4, stock and field signals.

    Returns all active products sorted by descending opportunity score.
    """
    gsc_queries = [str(r.get("query", "")).lower() for r in gsc_query_rows if r.get("query")]
    ga4 = ga4_page_rows or {}

    scored: list[tuple[int, dict[str, Any]]] = []
    for product in active_products:
        if not isinstance(product, dict):
            continue
        try:
            score = 0
            title = str(product.get("title") or "").lower()
            body = str(
                product.get("body_html")
                or product.get("descriptionHtml")
                or product.get("description")
                or ""
            )
            seo = product.get("seo") if isinstance(product.get("seo"), dict) else {}
            seo_title = str(seo.get("title", ""))
            seo_desc = str(seo.get("description", ""))
            handle = str(product.get("handle") or "")
            variants = _coerce_list(product.get("variants"))
            first_variant = variants[0] if variants else {}

            # ── SEO field signals (existing) ───────────────────────────────
            if not seo_title or len(seo_title) < 10:
                score += 30
            if not seo_desc or len(seo_desc) < 50:
                score += 20
            if len(_strip_html(body)) < 100:
                score += 20

            # ── GSC overlap ────────────────────────────────────────────────
            if any(word in q for q in gsc_queries for word in title.split() if len(word) > 3):
                score += 15

            # ── GA4 signals ────────────────────────────────────────────────
            page_path = f"/products/{handle}"
            ga4_row = ga4.get(page_path) or ga4.get(f"/{handle}") or {}
            if ga4_row:
                sessions = int(ga4_row.get("sessions", 0))
                conv_rate = float(ga4_row.get("conversion_rate", 0.0))
                revenue = float(ga4_row.get("revenue", 0.0))
                # Traffic but very low conversion → high SEO opportunity
                if sessions >= 50 and conv_rate < 0.01:
                    score += 25
                # Revenue generated → worth optimizing
                if revenue > 0:
                    score += 10
                # Has some traffic but no conversions at all
                if sessions > 0 and conv_rate == 0.0:
                    score += 15
                # Graduated organic-traffic magnitude — differentiates products that
                # otherwise share the same flags, so the score is not flat.
                if sessions >= 500:
                    score += 15
                elif sessions >= 100:
                    score += 10
                elif sessions >= 20:
                    score += 5
            else:
                # No GA4 data for this page = completely untapped organically
                score += 10

            # ── Stock signals ──────────────────────────────────────────────
            stock_qty, stock_status = _read_stock(product)
            if stock_qty is not None and stock_qty <= 0:
                # Out of stock — deprioritize
                score -= 15
            elif stock_qty is not None and stock_qty < 10:
                # Low stock — slight urgency boost
                score += 5

            # ── Basic product signals ──────────────────────────────────────
            if isinstance(first_variant, dict) and first_variant.get("price"):
                score += 5
            if product.get("collections"):
                score += 5
            if product.get("images"):
                score += 5

            scored.append((max(score, 0), product))
        except Exception:
            continue

    scored.sort(key=lambda x: x[0], reverse=True)

    results = []
    for score, product in scored:
        product_id = str(product.get("id", ""))
        title = product.get("title", "")
        handle = str(product.get("handle") or "")
        title_words = set(title.lower().split())
        matched = [
            str(r.get("query", ""))
            for r in gsc_query_rows
            if any(w in str(r.get("query", "")).lower() for w in title_words if len(w) > 3)
        ][:5]

        page_path = f"/products/{handle}"
        ga4_row = ga4.get(page_path) or ga4.get(f"/{handle}") or {}

        src: list[str] = ["shopify_snapshot"]
        if gsc_queries:
            src.append("gsc")
        if ga4_row:
            src.append("ga4")

        results.append(
            {
                "product_id": product_id,
                "opportunity_score": min(score, 100),
                "confidence": "high" if score >= 60 else "medium" if score >= 35 else "low",
                "signals": [],
                "matched_queries": matched,
                "ga4_metrics": ga4_row,
                "sources_used": src,
            }
        )
    return results


def _complete_json(
    llm_router: Any,
    prompt: str,
    keys: tuple[str, ...],
    fallback: dict[str, Any],
    product_title: str,
    *,
    max_tokens: int = 4096,
    temperature: float = 0.3,
    json_mode: bool = True,
) -> dict[str, Any]:
    """Run one LLM completion and merge the parsed `keys` into a copy of `fallback`.

    Defaults to deterministic JSON mode (json_mode=True) so the LLM returns a
    parseable object and consecutive runs of the same product stay consistent.
    On any LLM/parse failure returns `fallback` unchanged (logged).
    """
    pack = dict(fallback)
    if llm_router is None:
        return pack
    raw = ""
    try:
        completion = llm_router.complete(
            prompt,
            system=_SYSTEM_PROMPT,
            max_tokens=max_tokens,
            temperature=temperature,
            json_mode=json_mode,
        )
        raw = completion.text.strip()
        if raw.startswith("```"):
            raw = re.sub(r"^```[a-z]*\n?", "", raw)
            raw = re.sub(r"\n?```$", "", raw)
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            present = [k for k in keys if k in parsed]
            missing = [k for k in keys if k not in parsed]
            if missing:
                logger.warning(
                    "Pass2 partial for %r — present=%s missing=%s (raw_len=%d)",
                    product_title,
                    present,
                    missing,
                    len(raw),
                )
            for k in keys:
                if k in parsed:
                    pack[k] = parsed[k]
        else:
            logger.warning(
                "Pass2 non-dict response for %r: type=%s raw[:100]=%s",
                product_title,
                type(parsed).__name__,
                raw[:100],
            )
    except json.JSONDecodeError as exc:
        logger.warning(
            "JSON parse failed for %r — likely truncated (%d chars): %s | raw[:300]=%s",
            product_title,
            len(raw),
            exc,
            raw[:300],
        )
    except LLMError as exc:
        logger.warning("LLM call failed for %r: %s", product_title, exc)
    except Exception as exc:
        logger.warning("Unexpected error for %r: %s", product_title, exc)
    return pack


def _extract_product_fields(
    product: dict[str, Any],
    opp: dict[str, Any],
    product_labels: dict[str, str] | None,
    trend_signals: list[Any],
    merchant_facts: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Pull every field both prompts need out of a Shopify product dict."""
    product_id = str(product.get("id", ""))
    try:
        product_title = product.get("title", "")
        body_html = (
            product.get("body_html")
            or product.get("descriptionHtml")
            or product.get("description")
            or ""
        )
        raw_seo = product.get("seo")
        seo: dict[str, Any] = raw_seo if isinstance(raw_seo, dict) else {}
        raw_collections = _coerce_list(product.get("collections"))
        raw_tags = product.get("tags") or ""
        variants = _coerce_list(product.get("variants"))
        first_variant = variants[0] if variants else {}
        stock_qty, stock_status = _read_stock(product)
        trend_top, trend_rising = _match_trends(product_title, trend_signals)
        facts_analysis = analyze_product_facts(product)
        confirmed_facts = _merge_merchant_confirmed_facts(
            facts_analysis.get("confirmed_facts", []),
            merchant_facts,
        )
        confirmed_keys = {fact.get("key") for fact in confirmed_facts}
        missing_facts = [
            fact
            for fact in facts_analysis.get("missing_facts", [])
            if fact.get("key") not in confirmed_keys
        ]
        return {
            "product_title": product_title,
            "merchant_label": (product_labels or {}).get(product_id, ""),
            "handle": product.get("handle", ""),
            "description": _strip_html(body_html),
            "current_meta_title": seo.get("title") or product_title,
            "current_meta_description": seo.get("description") or "",
            "product_images": _extract_product_images(product),
            "collections": [
                c.get("title", "") if isinstance(c, dict) else str(c) for c in raw_collections if c
            ],
            "tags": ", ".join(raw_tags) if isinstance(raw_tags, list) else str(raw_tags),
            "price": str(first_variant.get("price", "")) if isinstance(first_variant, dict) else "",
            "nb_variants": len(variants),
            "stock_qty": stock_qty,
            "stock_status": stock_status,
            "ga4_metrics": opp.get("ga4_metrics", {}),
            "trend_top": trend_top,
            "trend_rising": trend_rising,
            "matched_queries": opp.get("matched_queries", []),
            "opportunity_score": opp.get("opportunity_score", 0),
            "confirmed_facts": confirmed_facts,
            "missing_facts": missing_facts,
            "fact_conflicts": facts_analysis.get("fact_conflicts", []),
            "fact_completeness_score": facts_analysis.get("completeness_score", 0.0),
            "source_product_text": " ".join(
                value
                for value in [
                    product_title,
                    _strip_html(body_html),
                    str(raw_tags),
                    " ".join(
                        c.get("title", "") if isinstance(c, dict) else str(c)
                        for c in raw_collections
                    ),
                ]
                if value
            ),
        }
    except Exception:
        title = product.get("title", "") if isinstance(product, dict) else ""
        return {
            "product_title": title,
            "merchant_label": "",
            "handle": product.get("handle", "") if isinstance(product, dict) else "",
            "description": title,
            "current_meta_title": title,
            "current_meta_description": "",
            "collections": [],
            "tags": "",
            "price": "",
            "nb_variants": 0,
            "stock_qty": None,
            "stock_status": "inconnu",
            "ga4_metrics": {},
            "trend_top": [],
            "trend_rising": [],
            "matched_queries": [],
            "opportunity_score": opp.get("opportunity_score", 0) if isinstance(opp, dict) else 0,
            "confirmed_facts": [],
            "missing_facts": [],
            "fact_conflicts": [],
            "fact_completeness_score": 0.0,
            "source_product_text": title,
        }


def _merge_merchant_confirmed_facts(
    extracted_facts: list[dict[str, Any]],
    merchant_facts: dict[str, str] | None,
) -> list[dict[str, Any]]:
    """Merge explicitly confirmed merchant answers into extracted Shopify facts."""
    accepted = {
        key: value.strip()[:500]
        for key, value in (merchant_facts or {}).items()
        if key in _MERCHANT_FACT_LABELS and isinstance(value, str) and value.strip()
    }
    if not accepted:
        return list(extracted_facts)
    facts = [
        fact
        for fact in extracted_facts
        if isinstance(fact, dict) and fact.get("key") not in accepted
    ]
    for key, value in accepted.items():
        facts.append(
            {
                "key": key,
                "label": _MERCHANT_FACT_LABELS[key],
                "value": value,
                "source": "merchant_confirmation",
                "confidence": "confirmed",
            }
        )
    return facts


def _run_competitor_crawl_analysis(
    *,
    shop: str,
    merchant_domains: list[str],
    pass1_states: list[dict[str, Any]],
    serp_intel: dict[str, dict[str, Any]],
    config: CompetitorCrawlConfig,
) -> tuple[dict[str, dict[str, Any]], int]:
    """Run optional competitor crawling and return insights keyed by product id."""
    if not config.enabled or not serp_intel or config.max_urls_per_run <= 0:
        _record_competitor_crawl_run_fail_open(
            shop=shop,
            enabled=config.enabled,
            urls_selected=0,
            results=[],
            summary={"reason": "disabled_or_no_serp"},
        )
        return {}, 0

    targets_by_product: dict[str, list[CompetitorCrawlTarget]] = {}
    global_targets: list[CompetitorCrawlTarget] = []
    seen_urls: set[str] = set()
    for state in pass1_states:
        product_id = str(state["product"].get("id", ""))
        targets = select_competitor_urls_for_product(
            state["pack"].get("seo_keywords", []) or [],
            serp_intel,
            shop,
            config.max_urls_per_product,
            merchant_domains=merchant_domains,
        )
        if not targets:
            continue
        targets_by_product[product_id] = targets
        for target in targets:
            if target.url in seen_urls or len(global_targets) >= config.max_urls_per_run:
                continue
            seen_urls.add(target.url)
            global_targets.append(target)

    if not global_targets:
        _record_competitor_crawl_run_fail_open(
            shop=shop,
            enabled=True,
            urls_selected=0,
            results=[],
            summary={"reason": "no_targets_selected"},
        )
        return {}, 0

    try:
        crawl_results = fetch_competitor_targets(global_targets, config)
    except Exception as exc:
        logger.warning("Competitor crawl failed open for %s: %s", shop, exc)
        _record_competitor_crawl_run_fail_open(
            shop=shop,
            enabled=True,
            urls_selected=len(global_targets),
            results=[],
            summary={"error": str(exc)},
        )
        return {}, 0

    features_by_url: dict[str, dict[str, Any]] = {}
    for result in crawl_results:
        if result.features and not result.error:
            serp_entry = (
                serp_intel.get(result.target.keyword.lower())
                or serp_intel.get(result.target.keyword)
                or {}
            )
            feature = dict(result.features)
            feature.update(
                {
                    "url": result.target.url,
                    "final_url": result.final_url or result.target.url,
                    "domain": result.target.domain,
                    "rank": result.target.rank,
                    "keyword": result.target.keyword,
                    "title": result.target.title or feature.get("title", ""),
                    "from_cache": result.from_cache,
                    "serp_paa_questions": list(serp_entry.get("paa", []) or [])[:10],
                    "serp_featured_snippet": serp_entry.get("featured_snippet"),
                }
            )
            features_by_url[result.target.url] = feature

    insights_by_product: dict[str, dict[str, Any]] = {}
    for state in pass1_states:
        product_id = str(state["product"].get("id", ""))
        keyword_meta = {
            str(keyword.get("query", "")).strip().lower(): keyword
            for keyword in state["pack"].get("seo_keywords", []) or []
            if isinstance(keyword, dict)
        }
        target_features: list[dict[str, Any]] = []
        for target in targets_by_product.get(product_id, []):
            if target.url not in features_by_url:
                continue
            feature = dict(features_by_url[target.url])
            keyword = keyword_meta.get(target.keyword.lower(), {})
            feature["keyword_intent_type"] = keyword.get("intent_type", "")
            feature["serp_feature_targets"] = list(keyword.get("serp_feature_targets", []) or [])
            target_features.append(feature)
        if not target_features:
            continue
        try:
            merchant_features = extract_merchant_product_features(state["product"])
            insights = build_competitor_crawl_insights(
                state["pack"],
                target_features,
                merchant_features,
            )
            insights_by_product[product_id] = insights
            state["pack"]["competitor_crawl_insights"] = insights
            state["pack"]["competitor_crawl_summary"] = format_competitor_crawl_for_prompt(insights)
            state["pack"]["competitor_pattern_boost"] = int(
                insights.get("priority_boost_total", 0) or 0
            )
            state["pack"]["competitor_pattern_gaps"] = insights.get("merchant_gaps", [])
        except Exception as exc:
            logger.debug("Competitor insight build failed for product %s: %s", product_id, exc)

    _record_competitor_crawl_run_fail_open(
        shop=shop,
        enabled=True,
        urls_selected=len(global_targets),
        results=crawl_results,
        summary={
            "products_with_insights": len(insights_by_product),
            "features_extracted": len(features_by_url),
        },
    )
    return insights_by_product, len(features_by_url)


def _record_competitor_crawl_run_fail_open(
    *,
    shop: str,
    enabled: bool,
    urls_selected: int,
    results: list[Any],
    summary: dict[str, Any],
) -> None:
    """Persist competitor crawl run stats without blocking analysis."""
    try:
        record_competitor_crawl_run(
            shop=shop,
            enabled=enabled,
            urls_selected=urls_selected,
            urls_fetched=sum(1 for result in results if not getattr(result, "from_cache", False)),
            urls_from_cache=sum(1 for result in results if getattr(result, "from_cache", False)),
            errors_count=sum(
                1
                for result in results
                if getattr(result, "error", None) or not getattr(result, "allowed_by_robots", True)
            ),
            summary=summary,
        )
    except Exception as exc:
        logger.debug("Competitor crawl run persistence failed for %s: %s", shop, exc)


def _apply_competitor_pack_recommendations(pack: dict[str, Any]) -> None:
    """Add explainable recommended actions from competitor structural gaps."""
    insights = pack.get("competitor_crawl_insights")
    if not isinstance(insights, dict):
        return
    actions = _coerce_str_list(pack.get("recommended_content_actions", []))
    for gap in insights.get("merchant_gaps", []) or []:
        if not isinstance(gap, dict):
            continue
        action = _competitor_gap_action(gap)
        if action and action not in actions:
            actions.append(action)
    pack["recommended_content_actions"] = actions[:8]


def _competitor_gap_action(gap: dict[str, Any]) -> str:
    gap_key = str(gap.get("gap") or "")
    return {
        "missing_faq_block": "Prioriser une FAQ structurée, car elle domine chez les concurrents SERP crawlés.",
        "missing_product_schema": "Ajouter ou renforcer le Product schema avec les faits produit confirmés.",
        "missing_breadcrumb_schema": "Ajouter un Breadcrumb schema pour clarifier la structure de page.",
        "missing_geo_answer_block": "Ajouter un bloc réponse court GEO/AEO basé uniquement sur les faits confirmés.",
        "weak_internal_linking": "Renforcer le maillage interne depuis et vers cette fiche produit.",
        "thin_product_description": "Étoffer la description produit avec des sections utiles et vérifiables.",
    }.get(gap_key, "")


def _apply_competitor_result_boost(product_result: dict[str, Any]) -> None:
    """Apply a capped competitor-pattern opportunity boost to the product result."""
    insights = product_result.get("competitor_crawl_insights")
    if not isinstance(insights, dict):
        return
    boost = max(0, min(20, int(insights.get("priority_boost_total", 0) or 0)))
    product_result["competitor_pattern_boost"] = boost
    product_result["competitor_pattern_gaps"] = insights.get("merchant_gaps", [])
    pack = product_result.setdefault("content_test_pack", {})
    if isinstance(pack, dict):
        pack["competitor_crawl_insights"] = insights
        pack["competitor_pattern_boost"] = boost
        pack["competitor_pattern_gaps"] = insights.get("merchant_gaps", [])
    if boost <= 0:
        return
    product_result["opportunity_score_before_competitor_boost"] = product_result.get(
        "opportunity_score",
        0,
    )
    product_result["opportunity_score"] = min(
        100,
        int(product_result.get("opportunity_score", 0) or 0) + boost,
    )


def run_market_analysis(
    products: list[dict[str, Any]],
    shop: str,
    gsc_page_rows: dict[str, dict[str, Any]],
    gsc_query_rows: list[dict[str, Any]],
    *,
    ga4_page_rows: dict[str, dict[str, Any]] | None = None,
    niche_hypothesis: dict[str, Any] | None = None,
    crawl_findings: list[dict[str, Any]] | None = None,
    max_products: int = 0,
    product_labels: dict[str, str] | None = None,
    plan: str | None = None,
    merchant_facts_by_product: dict[str, dict[str, str]] | None = None,
    retired_questions_by_product: dict[str, list[str]] | None = None,
    business_profile: dict[str, Any] | None = None,
    progress_callback: Callable[..., None] | None = None,
    collections: list[dict[str, Any]] | None = None,
    articles: list[dict[str, Any]] | None = None,
    reflection_test: bool = False,
    db_path: Path | None = None,
    fetch_realtime: bool = False,
    fetch_realtime_force: bool = False,
) -> dict[str, Any]:
    """Run a two-pass SEO/GEO market analysis for active products.

    Pass 1 (targeting): a real candidate keyword pool is built per product from
    GSC matched queries, DataForSEO keyword ideas, Google Suggest and Trends, then
    enriched with real volumes/difficulty. The LLM SELECTS and qualifies keywords
    from that pool (intent, product fit) instead of inventing them, and may add at
    most a couple of clearly-flagged gap long-tails. SERP intelligence (competitor
    angles + PAA questions) is fetched once for the whole run. Pass 2 (content): the
    LLM writes the content pack informed by real volumes, competitor angles, PAA
    questions and crawl findings.

    Sources: Shopify snapshot, GSC queries, GA4 page metrics, Google Trends,
    stock/inventory, DataForSEO (when enabled), crawl findings. Read-only.

    Args:
        max_products: Cap on products to analyse. 0 = no cap (all active products).
        plan: Merchant plan, used to resolve the monthly LLM budget. None → default.
        progress_callback: Called with (done, total, partial_results, phase) where
            phase is "targeting" (pass 1) or "content" (pass 2).
        reflection_test: When true, run a post-generation guardrail reflection and
            at most one targeted retry per product. Intended for experimental analysis.
        db_path: Optional override for the GEO ledger / learning store database path,
            used to surface past applied optimizations in the prompts (Task 6).
        fetch_realtime: When true, fetch a grounded real-time market signal
            (events, rising queries, competitor moves) once for this job.
            Callers must set this only for full-catalog runs (never a
            single/multi-product targeted analysis) — the signal is niche-wide,
            not product-specific, so re-fetching it per targeted call would add
            cost with no extra value. Still gated internally to the "agency"
            plan and a configured GEMINI_API_KEY, so it is always a safe no-op
            to pass True for a free/pro shop.
        fetch_realtime_force: Bypasses the "agency" plan gate inside the
            fetcher (still requires GEMINI_API_KEY). Only for the internal
            Pro/Grande boutique comparison tool — never set this from a
            regular analysis path, and it never touches the shop's real
            billing state.
    """
    active_products = filter_products_by_scope(products, "active")
    opportunities = _score_active_products(active_products, gsc_query_rows, ga4_page_rows)
    if max_products and max_products > 0:
        opportunities = opportunities[:max_products]
    total = len(opportunities)

    product_by_id: dict[str, dict[str, Any]] = {str(p.get("id", "")): p for p in active_products}

    sources_used: list[str] = ["shopify_snapshot"]
    if gsc_query_rows:
        sources_used.append("gsc")
    if ga4_page_rows:
        sources_used.append("ga4")
    if niche_hypothesis:
        sources_used.append("niche_hypothesis")
    niche_summary: str = niche_hypothesis.get("primary_niche", "") if niche_hypothesis else ""
    forbidden_phrases = _forbidden_phrases_from_niche(niche_hypothesis)
    business_context = _format_business_profile_context(business_profile)
    business_profile_context = build_business_profile_context_meta(business_profile)
    business_profile_context_hash = business_profile_context.get("hash")
    merchant_domains = _merchant_public_domains(shop, gsc_page_rows=gsc_page_rows)
    merchant_terms = _merchant_brand_terms(shop, business_profile=business_profile)
    competitor_brand_markers = _competitor_brand_markers(
        business_profile=business_profile,
        merchant_terms=merchant_terms,
    )
    if business_context:
        sources_used.append("business_profile")

    # Fetch Google Trends once — use top-5 product titles as seeds
    top_titles = [
        product_by_id.get(opp["product_id"], {}).get("title", "")
        for opp in opportunities[:5]
        if opp.get("product_id") in product_by_id
    ]
    trends_status: dict[str, Any] = {}
    trend_signals = _fetch_trends_once([t for t in top_titles if t], status_out=trends_status)
    if trend_signals:
        sources_used.append("trends")

    # Grounded calls now run once PER PRODUCT (events/trends + keyword market
    # verification), not once for the whole catalog — see the per-product
    # accumulators + budget gate below, and the calls inside the Pass 1 loop.
    # `per_product_realtime_signals` collects each product's own signal dict
    # for the final merge+persist; `_grounding_budget_exhausted` (checked once,
    # before the loop) skips ALL per-product grounded calls for this job if the
    # shop is already over its monthly LLM budget — protects against a large
    # catalog (up to 35 products × 2 calls) draining the whole budget on
    # grounding alone.
    per_product_realtime_signals: list[dict[str, Any]] = []
    realtime_products_attempted = 0
    realtime_products_ok = 0
    verify_products_attempted = 0
    verify_products_ok = 0
    keywords_verified_count = 0
    last_realtime_status = "not_attempted"
    last_verify_status = "not_attempted"
    _grounding_budget_exhausted = False
    if fetch_realtime:
        _budget_usd = _PLAN_BUDGETS_USD.get(plan or "", _DEFAULT_BUDGET_USD)
        _grounding_budget_exhausted = check_budget(shop, _budget_usd, days=30)["over_budget"]
        if _grounding_budget_exhausted:
            last_realtime_status = "budget_skipped"
            last_verify_status = "budget_skipped"

    try:
        llm_router = get_router(shop=shop)
    except LLMError:
        llm_router = None

    free_provider = FreeProvider(gsc_query_rows=gsc_query_rows, trend_signals=trend_signals)
    dataforseo_provider = DataForSEOProvider()
    google_ads_provider = GoogleAdsKeywordProvider()
    paid_providers = [p for p in (dataforseo_provider, google_ads_provider) if p.available]
    competitor_crawl_config = CompetitorCrawlConfig.for_market_analysis()

    provider_status: dict[str, Any] = {
        "free": True,
        "dataforseo": dataforseo_provider.available,
        "google_ads": google_ads_provider.available,
        "trends": trends_status or {"status": "empty", "detail": "no seeds", "count": 0},
    }
    if dataforseo_provider.available:
        sources_used.append("dataforseo")
    if google_ads_provider.available:
        sources_used.append("google_ads")
    if reflection_test:
        sources_used.append("content_guardrail_reflection")

    # ── PASS 1: targeting (understanding + candidate keywords) ───────────────
    pass1_states: list[dict[str, Any]] = []
    for idx, opp in enumerate(opportunities):
        product = product_by_id.get(opp.get("product_id", ""))
        if not product:
            continue
        fields = _extract_product_fields(
            product,
            opp,
            product_labels,
            trend_signals,
            (merchant_facts_by_product or {}).get(str(product.get("id", ""))),
        )

        # Real-data-first: build a candidate pool from GSC + DataForSEO ideas +
        # Google Suggest + Trends BEFORE the LLM, enrich it with real volumes, then
        # let the LLM SELECT from observed demand instead of inventing keywords.
        candidate_pool = _build_keyword_candidate_pool(
            fields,
            gsc_query_rows,
            dataforseo=dataforseo_provider,
            competitor_markers=competitor_brand_markers,
            merchant_terms=merchant_terms,
            use_suggest=True,
        )
        if candidate_pool:
            candidate_pool = _enrich_keyword_dicts(
                candidate_pool, free_provider, paid_providers, shop=shop
            )
            if "keyword_candidate_pool" not in sources_used:
                sources_used.append("keyword_candidate_pool")

        optimization_history = build_optimization_history(
            shop, str(product.get("id", "")), db_path=db_path
        )
        optimization_history_block = format_optimization_history(optimization_history)
        if optimization_history_block and "optimization_history" not in sources_used:
            sources_used.append("optimization_history")

        # Grounded real-time signal for THIS product only (agency plan / force,
        # gated internally; no-op + zero cost otherwise). One call per product,
        # never persisted individually — merged + saved once after the loop.
        product_realtime_signal: dict[str, Any] | None = None
        if fetch_realtime and not _grounding_budget_exhausted:
            realtime_products_attempted += 1
            _rt_status: dict[str, Any] = {}
            product_realtime_signal = _fetch_realtime_signals_once(
                shop,
                niche_hypothesis,
                [fields["product_title"]],
                db_path,
                force=fetch_realtime_force,
                status_out=_rt_status,
                persist=False,
            )
            last_realtime_status = _rt_status.get("status", "llm_error")
            if product_realtime_signal:
                realtime_products_ok += 1
                per_product_realtime_signals.append(product_realtime_signal)
        realtime_text = _format_realtime_signals(product_realtime_signal)

        prompt = _build_pass1_prompt(
            product_title=fields["product_title"],
            handle=fields["handle"],
            description=fields["description"],
            collections=fields["collections"],
            tags=fields["tags"],
            price=fields["price"],
            nb_variants=fields["nb_variants"],
            current_meta_title=fields["current_meta_title"],
            current_meta_description=fields["current_meta_description"],
            matched_queries=fields["matched_queries"],
            opportunity_score=fields["opportunity_score"],
            niche_summary=niche_summary,
            ga4_metrics=fields["ga4_metrics"],
            trend_top=fields["trend_top"],
            trend_rising=fields["trend_rising"],
            stock_qty=fields["stock_qty"],
            stock_status=fields["stock_status"],
            merchant_label=fields["merchant_label"],
            business_context=business_context,
            candidate_pool=candidate_pool,
            optimization_history_block=optimization_history_block,
            realtime_text=realtime_text,
        )
        fallback = _fallback_pack(
            fields["product_title"],
            fields["current_meta_title"],
            fields["current_meta_description"],
        )
        # If the LLM fails, keep the real pool rather than an empty keyword list.
        if candidate_pool:
            fallback["seo_keywords"] = [dict(c) for c in candidate_pool]
        pack = _complete_json(
            llm_router,
            prompt,
            _PASS1_KEYS,
            fallback,
            fields["product_title"],
            temperature=0.0,
        )
        pack["confirmed_facts"] = fields["confirmed_facts"]
        pack["fact_conflicts"] = fields.get("fact_conflicts", [])

        if candidate_pool:
            # Map the LLM selection back onto the real metrics; enrich any LLM-added gaps.
            pack["seo_keywords"] = _merge_pass1_selection(
                pack.get("seo_keywords", []) or [], candidate_pool
            )
            added = [k for k in pack["seo_keywords"] if k.get("data_source") == "llm_proposed"]
            if added:
                enriched = _enrich_keyword_dicts(added, free_provider, paid_providers, shop=shop)
                by_query = {str(k.get("query", "")).strip().lower(): k for k in enriched}
                pack["seo_keywords"] = [
                    by_query.get(str(k.get("query", "")).strip().lower(), k)
                    for k in pack["seo_keywords"]
                ]
        elif pack.get("seo_keywords"):
            # Degraded path: no real pool, enrich the LLM-proposed keywords as best-effort.
            pack["seo_keywords"] = _enrich_keyword_dicts(
                pack["seo_keywords"], free_provider, paid_providers, shop=shop
            )

        # Grounded market verification for THIS product's just-selected
        # keywords only. One call per product (capped at _MAX_VERIFY_KEYWORDS
        # inside verify_keywords_against_market) — structurally cannot starve
        # other products of verification budget, unlike the old catalog-wide
        # single call this replaces.
        if fetch_realtime and not _grounding_budget_exhausted:
            verify_products_attempted += 1
            _verify_status: dict[str, Any] = {}
            product_keywords = [
                str(kw.get("query") or "")
                for kw in (pack.get("seo_keywords") or [])
                if isinstance(kw, dict) and kw.get("query")
            ]
            verifications = _verify_keywords_once(
                shop,
                product_keywords,
                niche_summary,
                force=fetch_realtime_force,
                status_out=_verify_status,
            )
            last_verify_status = _verify_status.get("status", "llm_error")
            if verifications:
                verify_products_ok += 1
                keywords_verified_count += _apply_market_verification([{"pack": pack}], verifications)

        pass1_states.append(
            {
                "product": product,
                "opp": opp,
                "fields": fields,
                "pack": pack,
                "candidate_pool": candidate_pool,
                "optimization_history_block": optimization_history_block,
            }
        )

        if progress_callback is not None:
            try:
                partial = [
                    _build_product_result(
                        s["product"],
                        s["opp"],
                        s["pack"],
                        shop,
                        business_profile_context_hash,
                    )
                    for s in pass1_states
                ]
                progress_callback(idx + 1, total, partial, "targeting")
            except Exception:
                pass

    # DataForSEO keyword ideas are now fetched inside the candidate pool (per product,
    # seeded from real product terms) rather than from the LLM's top guesses.
    if dataforseo_provider.available and "dataforseo_keyword_ideas" not in sources_used:
        sources_used.append("dataforseo_keyword_ideas")

    serp_keywords: list[str] = []
    for state in pass1_states:
        fields = state["fields"]
        product_words = _content_words(
            " ".join(
                [
                    fields.get("source_product_text", "") or fields.get("product_title", ""),
                    fields.get("merchant_label", ""),
                    str(fields.get("handle", "")).replace("-", " "),
                ]
            )
        )
        repaired_keywords = _repair_keyword_selection_for_customer_need(
            state["pack"].get("seo_keywords", []) or [],
            state.get("candidate_pool", []) or [],
            source_text=[
                fields.get("merchant_label", ""),
                fields.get("product_title", ""),
                str(fields.get("handle", "")).replace("-", " "),
            ],
            product_words=product_words,
            buying_intents=_coerce_str_list(state["pack"].get("buying_intents", [])),
            target_customer=str(state["pack"].get("target_customer", "")),
        )
        filtered_keywords = _filter_competitor_brand_keywords(
            repaired_keywords,
            competitor_markers=competitor_brand_markers,
            merchant_terms=merchant_terms,
        )
        repaired_keywords = filtered_keywords
        ranked = _assign_keyword_targets(repaired_keywords, product_words)
        state["pack"]["keyword_guardrail"] = _build_keyword_guardrail(
            ranked,
            product_words=product_words,
        )
        state["pack"]["seo_keywords"] = ranked
        for keyword in ranked[:2]:
            query = str(keyword.get("query", "")).strip()
            if query and query not in serp_keywords:
                serp_keywords.append(query)

    serp_intel: dict[str, dict[str, Any]] = {}
    if dataforseo_provider.available and serp_keywords:
        serp_intel = dataforseo_provider.fetch_serp_intelligence(serp_keywords)
        if serp_intel:
            sources_used.append("dataforseo_serp")

    from app.market_analysis import cannibalization as cn
    from app.market_analysis import intent_classifier as ic
    from app.market_analysis import keyword_normalization as kn

    for state in pass1_states:
        state["pack"]["seo_keywords"] = _attach_serp_evidence(
            state["pack"].get("seo_keywords", []) or [],
            serp_intel,
        )
        state["pack"]["surface_plan"] = _build_surface_plan(
            state["pack"].get("seo_keywords", []) or [],
            state["fields"].get("confirmed_facts", []),
            state["pack"].get("geo_questions", []) or [],
        )
        merchant_questions = _build_enrichment_questions(
            state["pack"].get("seo_keywords", []) or [],
            state["fields"].get("missing_facts", []),
            state["pack"]["surface_plan"],
        )
        _pid = str(state.get("product_id") or state["fields"].get("product_id") or "")
        _retired = frozenset((retired_questions_by_product or {}).get(_pid) or [])
        # A question is answered once its fact is confirmed (merchant answer or
        # extracted from the product) or saved in the merchant facts file. Drop it
        # so it does not reappear — this makes both fact and editorial questions
        # persistent across analyses instead of only the manually "Retired" ones.
        _answered = {
            str(fact.get("key"))
            for fact in state["fields"].get("confirmed_facts", [])
            if isinstance(fact, dict) and fact.get("key")
        }
        _answered |= set((merchant_facts_by_product or {}).get(_pid) or {})
        merchant_questions = [
            q
            for q in merchant_questions
            if q.get("key") not in _retired and q.get("key") not in _answered
        ]
        state["pack"]["enrichment_questions"] = merchant_questions
        state["pack"]["merchant_questions"] = merchant_questions
        state["pack"]["pending_questions"] = merchant_questions
        state["pack"]["fact_conflicts"] = state["fields"].get("fact_conflicts", [])
        for keyword in state["pack"].get("seo_keywords", []) or []:
            query = str(keyword.get("query") or "").strip()
            if not query:
                continue
            serp_entry = serp_intel.get(query.lower()) if serp_intel else None
            classification = ic.classify_intent(
                query=query,
                serp=serp_entry,
                llm_intent=str(keyword.get("intent_type") or "") or None,
            )
            keyword["intent_type"] = classification["intent_type"]
            keyword["intent_type_source"] = classification["intent_type_source"]
            keyword["serp_feature_targets"] = classification["serp_feature_targets"]
            surface = _classify_keyword_surface(keyword)
            keyword["keyword_surface"] = surface["surface"]
            keyword["surface_reason"] = surface["reason"]
            keyword["product_primary_allowed"] = surface["product_primary_allowed"]
        state["pack"]["keyword_clusters"] = kn.build_clusters(
            state["pack"].get("seo_keywords", []) or []
        )
        state["pack"]["keyword_surface_mapping"] = _build_keyword_surface_mapping(
            state["pack"].get("seo_keywords", []) or []
        )

    # Domains the merchant excluded must feed neither the crawl nor the signals.
    excluded_competitor_domains = load_excluded_competitors(shop)

    competitor_crawl_feature_count = 0
    if competitor_crawl_config.enabled:
        _, competitor_crawl_feature_count = _run_competitor_crawl_analysis(
            shop=shop,
            merchant_domains=merchant_domains + sorted(excluded_competitor_domains),
            pass1_states=pass1_states,
            serp_intel=serp_intel,
            config=competitor_crawl_config,
        )
        if competitor_crawl_feature_count > 0 and "competitor_crawl" not in sources_used:
            sources_used.append("competitor_crawl")

    pass1_product_views = [
        {
            "product_id": str(state["product"].get("id", "")),
            "product_title": state["product"].get("title", ""),
            "product_url": f"/products/{state['product'].get('handle', '')}",
            "seo_keywords": state["pack"].get("seo_keywords", []) or [],
            "opportunity_score": state["opp"].get("opportunity_score", 0),
        }
        for state in pass1_states
    ]

    # Aggregate the per-product grounded calls made during the Pass 1 loop
    # above into one catalog-wide status + one merged, deduplicated signal
    # snapshot, persisted once (see `fetch_realtime_signals(persist=False)`).
    realtime_signals = _merge_realtime_signals(per_product_realtime_signals)
    if realtime_signals:
        sources_used.append("realtime_grounding")
        from app.niche.signals.realtime_trends import persist_realtime_signals  # noqa: PLC0415

        persist_realtime_signals(shop, realtime_signals, db_path=db_path)
    if keywords_verified_count > 0:
        sources_used.append("realtime_market_verification")

    realtime_status: dict[str, Any] = {
        "status": last_realtime_status,
        "products_attempted": realtime_products_attempted,
        "products_ok": realtime_products_ok,
        "detail": "",
    }
    if realtime_products_attempted > 0 and 0 < realtime_products_ok < realtime_products_attempted:
        realtime_status["status"] = "partial"
    verify_status: dict[str, Any] = {
        "status": last_verify_status,
        "products_attempted": verify_products_attempted,
        "products_ok": verify_products_ok,
        "detail": "",
    }
    if verify_products_attempted > 0 and 0 < verify_products_ok < verify_products_attempted:
        verify_status["status"] = "partial"

    cannibalization_alerts = cn.detect_alerts(pass1_product_views)
    cannibalization_hints_by_product: dict[str, dict[str, Any]] = {}
    for state in pass1_states:
        pid = str(state["product"].get("id", ""))
        hint = cn.get_reorientation_hint(cannibalization_alerts, product_id=pid)
        if hint is not None:
            cannibalization_hints_by_product[pid] = hint
    if cannibalization_alerts and "cannibalization_detector" not in sources_used:
        sources_used.append("cannibalization_detector")

    competitor_signals = build_competitor_signals(shop, keywords=serp_keywords or None)
    if competitor_signals:
        sources_used.append("competitors_manual")
    if dataforseo_provider.available and serp_keywords:
        serp_signals = dataforseo_provider.fetch_serp_competitors(serp_keywords)
        if serp_signals:
            competitor_signals = list(competitor_signals) + serp_signals

    # Fetch domain competitors early so they can be injected into each Pass 2 prompt
    domain_competitor_signals: list[dict[str, Any]] = []
    if dataforseo_provider.available and shop:
        raw_domain_signals = dataforseo_provider.fetch_domain_competitors(shop)
        if raw_domain_signals:
            domain_competitor_signals = _filter_domain_competitors(raw_domain_signals)
            competitor_signals = list(competitor_signals) + raw_domain_signals
            if "dataforseo_domain_competitors" not in sources_used:
                sources_used.append("dataforseo_domain_competitors")

    if excluded_competitor_domains:
        competitor_signals = _drop_excluded_signals(
            competitor_signals, excluded_competitor_domains
        )
        domain_competitor_signals = _drop_excluded_signals(
            domain_competitor_signals, excluded_competitor_domains
        )

    # ── Budget gate: skip pass 2 (content) when over the monthly LLM budget ──
    budget_usd = _PLAN_BUDGETS_USD.get(plan or "", _DEFAULT_BUDGET_USD)
    budget_status = check_budget(shop, budget_usd, days=30)
    run_pass2 = not budget_status["over_budget"]
    if not run_pass2 and "budget_skipped_pass2" not in sources_used:
        sources_used.append("budget_skipped_pass2")

    # ── PASS 2: content (informed by real SERP/PAA/crawl data) ───────────────
    product_results: list[dict[str, Any]] = []
    for idx, state in enumerate(pass1_states):
        fields = state["fields"]
        pack = state["pack"]
        keyword_guardrail_blocked = (
            isinstance(pack.get("keyword_guardrail"), dict)
            and pack["keyword_guardrail"].get("status") == "blocked"
        )
        if keyword_guardrail_blocked and "keyword_guardrail" not in sources_used:
            sources_used.append("keyword_guardrail")
        if run_pass2 and not keyword_guardrail_blocked:
            from app.market_analysis import eeat as _eeat_mod  # noqa: PLC0415

            product_eeat_signals = _eeat_mod.detect_signals(
                confirmed_facts=fields.get("confirmed_facts", []) or [],
                business_profile=business_profile,
            )
            pack["eeat_signals"] = product_eeat_signals
            prompt = _build_pass2_prompt(
                product_title=fields["product_title"],
                handle=fields["handle"],
                niche_summary=niche_summary,
                pass1=pack,
                enriched_keywords=pack.get("seo_keywords", []) or [],
                serp_intel=serp_intel,
                crawl_findings=_crawl_for_handle(fields["handle"], crawl_findings),
                current_meta_title=fields["current_meta_title"],
                current_meta_description=fields["current_meta_description"],
                merchant_label=fields["merchant_label"],
                ga4_metrics=fields.get("ga4_metrics"),
                domain_competitors=domain_competitor_signals or None,
                confirmed_facts=fields.get("confirmed_facts", []),
                missing_facts=fields.get("missing_facts", []),
                surface_plan=pack.get("surface_plan", {}),
                forbidden_phrases=forbidden_phrases,
                business_context=business_context,
                cannibalization_hint=cannibalization_hints_by_product.get(
                    str(state["product"].get("id", ""))
                ),
                eeat_signals=product_eeat_signals,
                product_images=fields.get("product_images", []),
                competitor_crawl_summary=pack.get("competitor_crawl_summary"),
                optimization_history_block=state.get("optimization_history_block", ""),
            )
            pack = _complete_json(
                llm_router, prompt, _PASS2_KEYS, pack, fields["product_title"], max_tokens=8192
            )
            pack = _normalize_generated_content_pack(
                pack,
                confirmed_facts=fields.get("confirmed_facts", []),
            )

            # Retry once when the essential content fields are missing — the LLM sometimes
            # returns a valid but incomplete JSON (e.g. only meta fields, no description/FAQ).
            _essential = ["proposed_meta_title", "proposed_meta_description"]
            if _enabled_surface(pack.get("surface_plan", {}), "product_description"):
                _essential.append("proposed_product_description")
            if not all(pack.get(k) for k in _essential):
                logger.warning(
                    "Pass 2 missing essential fields for %r, retrying with simplified prompt",
                    fields["product_title"],
                )
                retry_prompt = _build_pass2_retry_prompt(
                    product_title=fields["product_title"],
                    niche_summary=niche_summary,
                    keywords=[
                        kw["query"]
                        for kw in (pack.get("seo_keywords") or [])[:6]
                        if isinstance(kw, dict) and kw.get("query")
                    ],
                    current_meta_title=fields["current_meta_title"],
                    current_meta_description=fields["current_meta_description"],
                    confirmed_facts=fields.get("confirmed_facts", []),
                    surface_plan=pack.get("surface_plan", {}),
                )
                pack = _complete_json(
                    llm_router,
                    retry_prompt,
                    _PASS2_KEYS,
                    pack,
                    fields["product_title"],
                    max_tokens=4096,
                )
                pack = _normalize_generated_content_pack(
                    pack,
                    confirmed_facts=fields.get("confirmed_facts", []),
                )

        if reflection_test and run_pass2 and not keyword_guardrail_blocked:
            pack = _run_reflection_test_loop(
                pack,
                llm_router=llm_router,
                fields=fields,
                business_context=business_context,
                business_profile=business_profile,
                niche_summary=niche_summary,
                forbidden_phrases=forbidden_phrases,
            )
        else:
            pack = _normalize_generated_content_pack(
                pack,
                confirmed_facts=fields.get("confirmed_facts", []),
            )
            _apply_competitor_pack_recommendations(pack)
            pack["content_quality"] = _build_content_quality(
                pack,
                confirmed_facts=fields.get("confirmed_facts", []),
                source_product_text=fields.get("source_product_text", ""),
                surface_plan=pack.get("surface_plan", {}),
                forbidden_phrases=forbidden_phrases,
            )
        _apply_competitor_pack_recommendations(pack)
        product_result = _build_product_result(
            state["product"],
            state["opp"],
            pack,
            shop,
            business_profile_context_hash,
        )
        _apply_competitor_result_boost(product_result)
        product_results.append(product_result)
        if progress_callback is not None:
            try:
                progress_callback(idx + 1, total, list(product_results), "content")
            except Exception:
                pass

    _apply_catalog_content_conflicts(product_results, active_products)
    _sync_result_quality_fields(product_results)

    orphan_products: list[str] = []
    blog_gap_suggestions: list[dict[str, Any]] = []
    try:
        from app.market_analysis import internal_linking as _il  # noqa: PLC0415

        collections_input = list(collections or [])
        articles_input = list(articles or [])
        link_recs = _il.build_recommendations(
            products=product_results,
            collections=collections_input,
            articles=articles_input,
            pages=[],
            shop=shop,
        )
        for product in product_results:
            pid = str(product.get("product_id") or "")
            suggestions = link_recs.get(pid, [])
            if suggestions:
                pack = product.setdefault("content_test_pack", {})
                pack["recommended_internal_links"] = suggestions
        orphan_products = _il.detect_orphan_products(
            products=product_results,
            collections=collections_input,
            articles=articles_input,
        )
        blog_gap_suggestions = _il.detect_blog_gaps(
            products=product_results, articles=articles_input
        )
        if link_recs or orphan_products or blog_gap_suggestions:
            if "internal_linking_engine" not in sources_used:
                sources_used.append("internal_linking_engine")
    except Exception as exc:
        logger.warning("Skipping market analysis internal linking for %s: %s", shop, exc)

    total_opportunity_count = sum(
        len(r.get("seo_keywords", [])) + len(r.get("geo_questions", [])) for r in product_results
    )
    try:
        from app.learning.policy import enrich_market_products  # noqa: PLC0415

        enrich_market_products(shop, product_results)
        if "learning_engine" not in sources_used:
            sources_used.append("learning_engine")
    except Exception as exc:
        logger.warning("Skipping market analysis learning enrichment for %s: %s", shop, exc)

    return {
        "shop": shop,
        "analyzed_at": datetime.now(UTC).isoformat(),
        "active_product_count": len(active_products),
        "analyzed_product_count": len(product_results),
        "total_opportunity_count": total_opportunity_count,
        "sources_used": sources_used,
        "provider_status": provider_status,
        "competitor_signals": competitor_signals,
        "cannibalization_alerts": cannibalization_alerts,
        "orphan_products": orphan_products,
        "blog_gap_suggestions": blog_gap_suggestions,
        "business_profile_context": business_profile_context,
        "products": product_results,
        "budget": budget_status,
        # Real-time grounding (agency plan) diagnostics — always present so a
        # silent no-op (missing key, wrong plan, LLM error) is inspectable
        # instead of only showing up as an absence in `sources_used`.
        "realtime_signals": realtime_signals,
        "realtime_status": realtime_status,
        "market_verification_status": verify_status,
        "keywords_with_market_verification": keywords_verified_count,
    }
