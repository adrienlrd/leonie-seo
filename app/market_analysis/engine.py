"""Market analysis engine — per-product SEO/GEO opportunity + content pack generation."""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from app.llm import LLMError, get_router
from app.market_analysis.competitors import build_competitor_signals
from app.market_analysis.providers.dataforseo_provider import DataForSEOProvider
from app.market_analysis.providers.free_provider import (
    FreeProvider,
    signals_from_llm_keywords,
)
from app.market_analysis.providers.google_ads_provider import GoogleAdsKeywordProvider
from app.market_analysis.providers.types import KeywordSignal
from app.observability.metrics import check_budget
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
    "proposed_product_title_if_different",
    "proposed_product_description",
    "proposed_faq",
    "proposed_geo_answer_block",
    "proposed_blog_title",
    "proposed_blog_outline",
    "proposed_blog_intro",
    "recommended_content_actions",
    "facts_used",
    "facts_missing",
    "confidence",
)

_JSON_KEYS = _PASS1_KEYS + _PASS2_KEYS

# Per-plan monthly LLM budget (USD). Two LLM passes per product double the cost,
# so the engine gates pass 2 on remaining budget. Free keeps a small non-zero
# budget so it still gets content (degraded, no DataForSEO). Provisional until
# real billing wires the plan through.
_PLAN_BUDGETS_USD = {"free": 2.0, "starter": 5.0, "pro": 20.0, "agency": 50.0}
_DEFAULT_BUDGET_USD = 20.0


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


def _coerce_seo_keywords(value: Any) -> list[dict[str, Any]]:
    """Ensure every seo_keyword item has plain-string scalar fields."""
    if not isinstance(value, list):
        return []
    out = []
    for kw in value:
        if not isinstance(kw, dict):
            continue
        kw = dict(kw)
        for field in ("query", "intent_type", "reason"):
            kw[field] = _coerce_str(kw.get(field, ""))
        out.append(kw)
    return out


def _coerce_geo_questions(value: Any) -> list[dict[str, Any]]:
    """Ensure every geo_question item has plain-string scalar fields."""
    if not isinstance(value, list):
        return []
    out = []
    for q in value:
        if not isinstance(q, dict):
            continue
        q = dict(q)
        for field in ("question", "answer_angle", "content_block_type", "confidence"):
            q[field] = _coerce_str(q.get(field, ""))
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


def _fetch_trends_once(top_titles: list[str]) -> list[Any]:
    """Call Google Trends once with up to 5 product title seeds. Returns [] on any error."""
    if not top_titles:
        return []
    try:
        from app.niche.signals.trends import fetch_related_queries  # noqa: PLC0415
        return fetch_related_queries(top_titles[:5], geo="FR", timeframe="today 12-m")
    except Exception as exc:
        logger.debug("Google Trends unavailable: %s", exc)
        return []


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

    stock_text = (
        f"{stock_qty} unités ({stock_status})"
        if stock_qty is not None
        else stock_status
    )

    trend_text = ""
    if trend_top:
        trend_text += f"Top tendances : {', '.join(trend_top)}. "
    if trend_rising:
        trend_text += f"En hausse : {', '.join(trend_rising)}."
    if not trend_text:
        trend_text = "aucune donnée Trends disponible"

    merchant_label_text = (
        f"LABEL SEO MARCHAND: {merchant_label}\n" if merchant_label else ""
    )

    return (
        f"DATE_ACTUELLE: {today} (année {current_year})\n"
        f"NICHE: {niche_summary or 'Non définie'}\n"
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
        f"STOCK: {stock_text}\n"
        f"SCORE OPPORTUNITÉ: {opportunity_score}/100\n\n"
        f"IMPORTANT: nous sommes en {current_year}. "
        "N'utilise jamais d'années passées dans les titres, exemples ou références. "
        "Toutes les propositions doivent être actuelles et pertinentes pour l'année en cours.\n\n"
        "ÉTAPE 1/2 — CIBLAGE. Identifie le produit et les cibles de recherche. "
        "Ne rédige PAS encore de contenu (meta, description, FAQ) : cela viendra à l'étape 2 "
        "avec des données réelles de marché.\n"
        "Réponds uniquement en JSON valide avec exactement ces clés : "
        "product_summary, target_customer, buying_intents (liste de strings), "
        "seo_keywords (5-8 objets avec query/intent_type/demand_score/competition_score/product_fit_score/reason), "
        "geo_questions (5-8 objets avec question/answer_angle/content_block_type/confidence)."
    )


def _crawl_for_handle(handle: str, crawl_findings: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    """Return crawl findings whose URL points at this product (keyed by URL only)."""
    if not handle or not crawl_findings:
        return []
    needle = f"/products/{handle}"
    return [
        f for f in crawl_findings
        if isinstance(f, dict) and needle in str(f.get("url", ""))
    ]


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
) -> str:
    """Build the pass-2 (content) prompt, informed by real market data.

    Each context block is omitted when empty so free mode (no DataForSEO) degrades
    cleanly to crawl + GSC-enriched keywords only.
    """
    today = datetime.now(UTC).strftime("%d/%m/%Y")
    current_year = datetime.now(UTC).year

    sorted_kws = sorted(
        [k for k in enriched_keywords if isinstance(k, dict)],
        key=lambda k: k.get("demand_score", 0),
        reverse=True,
    )

    # ── Targeted keywords (real volume/difficulty) ──────────────────────────
    target_lines: list[str] = []
    for kw in sorted_kws[:8]:
        vol = kw.get("search_volume")
        vol_text = f"{vol}/mois" if vol is not None else "volume n/a"
        target_lines.append(
            f'- "{kw.get("query", "")}" — {vol_text}, '
            f'difficulté {kw.get("competition_score", "?")}/100 '
            f'({kw.get("difficulty_source", "free_estimated")}), '
            f'intent {kw.get("intent_type", "?")}'
        )
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
            joined = "; ".join(
                f'{c.get("domain", "")} — "{c.get("title", "")}"' for c in comps
            )
            competitor_lines.append(f'"{key}": {joined}')
        fs = intel.get("featured_snippet")
        if fs and fs not in featured_snippets:
            featured_snippets.append(fs)

    # ── Crawl findings ──────────────────────────────────────────────────────
    crawl_lines = [
        f'- {f.get("issue_type", "?")} ({f.get("severity", "?")}): {f.get("detail", "")}'
        for f in crawl_findings[:8]
    ]

    merchant_label_text = f"LABEL SEO MARCHAND: {merchant_label}\n" if merchant_label else ""

    parts: list[str] = [
        f"DATE_ACTUELLE: {today} (année {current_year})",
        f"NICHE: {niche_summary or 'Non définie'}",
        f"PRODUIT: {product_title} | handle: {handle}",
        merchant_label_text.rstrip("\n") if merchant_label_text else "",
        f"META TITLE ACTUEL: {current_meta_title or 'absent'}",
        f"META DESCRIPTION ACTUELLE: {current_meta_description or 'absente'}",
        "",
        "COMPRÉHENSION (étape 1):",
        f"  Résumé: {pass1.get('product_summary', '')}",
        f"  Client cible: {pass1.get('target_customer', '')}",
        f"  Intentions d'achat: {', '.join(pass1.get('buying_intents', []) or [])}",
    ]

    if target_lines:
        parts.append("\nMOTS-CLÉS CIBLES (données réelles):")
        parts.extend(target_lines)
    if related_ideas:
        parts.append("\nAUTRES IDÉES DE MOTS-CLÉS LIÉS: " + ", ".join(related_ideas[:15]))
    if competitor_lines:
        parts.append("\nCONCURRENTS SERP (titres/angles réels — différencie-toi, ne copie pas):")
        parts.extend(competitor_lines)
    if featured_snippets:
        parts.append("Featured snippets concurrents: " + " | ".join(featured_snippets[:3]))
    if paa_questions:
        parts.append("\nQUESTIONS PAA Google (utilise-les pour proposed_faq ET geo_questions):")
        parts.extend(f"- {q}" for q in paa_questions[:10])
    if crawl_lines:
        parts.append("\nPROBLÈMES TECHNIQUES DÉTECTÉS (crawl):")
        parts.extend(crawl_lines)

    parts.append(
        f"\nIMPORTANT: nous sommes en {current_year}. "
        "N'utilise jamais d'années passées dans les titres, exemples ou références.\n"
        "ÉTAPE 2/2 — CONTENU. Rédige le contenu en t'appuyant sur les données réelles ci-dessus. "
        "proposed_faq DOIT couvrir les questions PAA pertinentes ; "
        "geo_questions doit refléter les intentions réelles. "
        "Ne jamais inventer de faits : liste-les dans facts_missing.\n"
        "Réponds uniquement en JSON valide avec exactement ces clés : "
        "proposed_meta_title, proposed_meta_description, proposed_product_title_if_different, "
        "proposed_product_description, proposed_faq (5-8 objets {q, a}), "
        "proposed_geo_answer_block (40-80 mots, factuel), "
        "proposed_blog_title, proposed_blog_outline (liste strings), proposed_blog_intro, "
        "recommended_content_actions (liste strings), facts_used (liste strings), "
        "facts_missing (liste strings), confidence (high/medium/low)."
    )

    return "\n".join(p for p in parts if p != "")


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
        if sig:
            # Real free signals override LLM estimates when available
            if sig.get("source") == "gsc":
                impressions = sig.get("impressions") or 0
                merged["demand_score"] = _impressions_bucket(int(impressions))
                merged["competition_score"] = int(sig.get("difficulty_score", merged.get("competition_score", 50)))
                merged["gsc_impressions"] = sig.get("impressions")
                merged["gsc_clicks"] = sig.get("clicks")
                merged["gsc_position"] = sig.get("avg_position")
            # Paid-provider overrides (DataForSEO) — replace estimates with real volume/CPC
            if sig.get("source") == "dataforseo" and sig.get("search_volume") is not None:
                merged["demand_score"] = _volume_bucket(int(sig["search_volume"]))
                merged["competition_score"] = int(sig.get("difficulty_score", merged.get("competition_score", 50)))
            merged["data_source"] = sig.get("source", "llm_estimated")
            merged["difficulty_source"] = sig.get("difficulty_source", "free_estimated")
            merged["search_volume"] = sig.get("search_volume")  # None in free mode — UI shows "missing"
            merged["cpc"] = sig.get("cpc")
            merged["ads_competition"] = sig.get("ads_competition")
            merged["confidence"] = sig.get("confidence", "low")
            merged["notes"] = sig.get("notes", [])
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
        w for w in text.lower().split()
        if len(w) >= 3 and w not in _FR_STOP_WORDS
    )


def _idea_is_relevant(idea_query: str, seed_queries: list[str], min_overlap: int = 2) -> bool:
    """Return True if the idea shares ≥min_overlap content words with any seed keyword.

    Filters out DataForSEO Keyword Ideas that are semantically unrelated to the
    product context (e.g. 'fable de la fontaine' when seeds are about cat fountains).
    """
    idea_words = _content_words(idea_query)
    if not idea_words:
        return False
    seed_words = frozenset().union(*(_content_words(s) for s in seed_queries))
    return len(idea_words & seed_words) >= min_overlap


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


def _fallback_pack(product_title: str, current_meta_title: str, current_meta_description: str) -> dict[str, Any]:
    return {
        "product_summary": "",
        "target_customer": "",
        "buying_intents": [],
        "seo_keywords": [],
        "geo_questions": [],
        "proposed_meta_title": current_meta_title,
        "proposed_meta_description": current_meta_description,
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
        "confidence": "low",
    }


def _build_product_result(
    product: dict[str, Any],
    opportunity: dict[str, Any],
    llm_pack: dict[str, Any],
    shop: str,
) -> dict[str, Any]:
    product_id = str(product.get("id", ""))
    product_title = product.get("title", "")
    handle = product.get("handle", "")
    raw_seo = product.get("seo")
    seo: dict[str, Any] = raw_seo if isinstance(raw_seo, dict) else {}
    current_meta_title = seo.get("title") or product_title
    current_meta_description = seo.get("description") or ""
    body_html = product.get("body_html") or product.get("description") or ""
    description_summary = _strip_html(body_html)[:200]

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
        "trend_signals": opportunity.get("trend_signals", []),
        "competitor_signals": opportunity.get("signals", []),
        "content_test_pack": {
            "current_meta_title": current_meta_title,
            "proposed_meta_title": _coerce_str(llm_pack.get("proposed_meta_title", "")),
            "current_meta_description": current_meta_description,
            "proposed_meta_description": _coerce_str(llm_pack.get("proposed_meta_description", "")),
            "current_product_title": product_title,
            "proposed_product_title": _coerce_str(llm_pack.get("proposed_product_title_if_different", product_title)),
            "current_product_description_summary": description_summary,
            "proposed_product_description": _coerce_str(llm_pack.get("proposed_product_description", "")),
            "proposed_faq": _coerce_faq(llm_pack.get("proposed_faq", [])),
            "proposed_geo_answer_block": _coerce_str(llm_pack.get("proposed_geo_answer_block", "")),
            "proposed_blog_title": _coerce_str(llm_pack.get("proposed_blog_title", "")),
            "proposed_blog_outline": _coerce_str_list(llm_pack.get("proposed_blog_outline", [])),
            "proposed_blog_intro": _coerce_str(llm_pack.get("proposed_blog_intro", "")),
            "proposed_comparison_or_buying_guide": "",
            "recommended_internal_links": [],
            "content_risks": [],
            "facts_used": _coerce_str_list(llm_pack.get("facts_used", [])),
            "facts_missing": _coerce_str_list(llm_pack.get("facts_missing", [])),
            "confidence": _coerce_str(llm_pack.get("confidence", "low"), "low"),
        },
        "recommended_content_actions": _coerce_str_list(llm_pack.get("recommended_content_actions", [])),
        "confidence": _coerce_str(llm_pack.get("confidence", opportunity.get("confidence", "low")), "low"),
        "opportunity_score": opportunity.get("opportunity_score", 0),
        "sources_used": opportunity.get("sources_used", []),
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
            body = str(product.get("body_html") or product.get("description") or "")
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

        results.append({
            "product_id": product_id,
            "opportunity_score": min(score, 100),
            "confidence": "high" if score >= 60 else "medium" if score >= 35 else "low",
            "signals": [],
            "matched_queries": matched,
            "ga4_metrics": ga4_row,
            "sources_used": src,
        })
    return results


def _complete_json(
    llm_router: Any,
    prompt: str,
    keys: tuple[str, ...],
    fallback: dict[str, Any],
    product_title: str,
) -> dict[str, Any]:
    """Run one LLM completion and merge the parsed `keys` into a copy of `fallback`.

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
            max_tokens=4096,
            temperature=0.3,
        )
        raw = completion.text.strip()
        if raw.startswith("```"):
            raw = re.sub(r"^```[a-z]*\n?", "", raw)
            raw = re.sub(r"\n?```$", "", raw)
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            for k in keys:
                if k in parsed:
                    pack[k] = parsed[k]
    except json.JSONDecodeError as exc:
        logger.warning(
            "JSON parse failed for %r — likely truncated (%d chars): %s | start: %s",
            product_title, len(raw), exc, raw[:200],
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
) -> dict[str, Any]:
    """Pull every field both prompts need out of a Shopify product dict."""
    product_id = str(product.get("id", ""))
    try:
        product_title = product.get("title", "")
        body_html = product.get("body_html") or product.get("description") or ""
        raw_seo = product.get("seo")
        seo: dict[str, Any] = raw_seo if isinstance(raw_seo, dict) else {}
        raw_collections = _coerce_list(product.get("collections"))
        raw_tags = product.get("tags") or ""
        variants = _coerce_list(product.get("variants"))
        first_variant = variants[0] if variants else {}
        stock_qty, stock_status = _read_stock(product)
        trend_top, trend_rising = _match_trends(product_title, trend_signals)
        return {
            "product_title": product_title,
            "merchant_label": (product_labels or {}).get(product_id, ""),
            "handle": product.get("handle", ""),
            "description": _strip_html(body_html),
            "current_meta_title": seo.get("title") or product_title,
            "current_meta_description": seo.get("description") or "",
            "collections": [
                c.get("title", "") if isinstance(c, dict) else str(c)
                for c in raw_collections if c
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
        }
    except Exception:
        title = product.get("title", "") if isinstance(product, dict) else ""
        return {
            "product_title": title, "merchant_label": "",
            "handle": product.get("handle", "") if isinstance(product, dict) else "",
            "description": title, "current_meta_title": title, "current_meta_description": "",
            "collections": [], "tags": "", "price": "", "nb_variants": 0,
            "stock_qty": None, "stock_status": "inconnu",
            "ga4_metrics": {}, "trend_top": [], "trend_rising": [],
            "matched_queries": [],
            "opportunity_score": opp.get("opportunity_score", 0) if isinstance(opp, dict) else 0,
        }


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
    progress_callback: Callable[..., None] | None = None,
) -> dict[str, Any]:
    """Run a two-pass SEO/GEO market analysis for active products.

    Pass 1 (targeting): the LLM produces product understanding + candidate
    keywords. Those keywords are enriched (GSC + DataForSEO volumes/difficulty),
    and SERP intelligence (competitor angles + PAA questions) is fetched once for
    the whole run. Pass 2 (content): the LLM writes the content pack informed by
    real volumes, competitor angles, PAA questions and crawl findings.

    Sources: Shopify snapshot, GSC queries, GA4 page metrics, Google Trends,
    stock/inventory, DataForSEO (when enabled), crawl findings. Read-only.

    Args:
        max_products: Cap on products to analyse. 0 = no cap (all active products).
        plan: Merchant plan, used to resolve the monthly LLM budget. None → default.
        progress_callback: Called with (done, total, partial_results, phase) where
            phase is "targeting" (pass 1) or "content" (pass 2).
    """
    active_products = filter_products_by_scope(products, "active")
    opportunities = _score_active_products(active_products, gsc_query_rows, ga4_page_rows)
    if max_products and max_products > 0:
        opportunities = opportunities[:max_products]
    total = len(opportunities)

    product_by_id: dict[str, dict[str, Any]] = {
        str(p.get("id", "")): p for p in active_products
    }

    sources_used: list[str] = ["shopify_snapshot"]
    if gsc_query_rows:
        sources_used.append("gsc")
    if ga4_page_rows:
        sources_used.append("ga4")
    if niche_hypothesis:
        sources_used.append("niche_hypothesis")
    niche_summary: str = niche_hypothesis.get("primary_niche", "") if niche_hypothesis else ""

    # Fetch Google Trends once — use top-5 product titles as seeds
    top_titles = [
        product_by_id.get(opp["product_id"], {}).get("title", "")
        for opp in opportunities[:5]
        if opp.get("product_id") in product_by_id
    ]
    trend_signals = _fetch_trends_once([t for t in top_titles if t])
    if trend_signals:
        sources_used.append("trends")

    try:
        llm_router = get_router(shop=shop)
    except LLMError:
        llm_router = None

    free_provider = FreeProvider(gsc_query_rows=gsc_query_rows, trend_signals=trend_signals)
    dataforseo_provider = DataForSEOProvider()
    google_ads_provider = GoogleAdsKeywordProvider()
    paid_providers = [p for p in (dataforseo_provider, google_ads_provider) if p.available]

    provider_status: dict[str, Any] = {
        "free": True,
        "dataforseo": dataforseo_provider.available,
        "google_ads": google_ads_provider.available,
    }
    if dataforseo_provider.available:
        sources_used.append("dataforseo")
    if google_ads_provider.available:
        sources_used.append("google_ads")

    # ── PASS 1: targeting (understanding + candidate keywords) ───────────────
    pass1_states: list[dict[str, Any]] = []
    for idx, opp in enumerate(opportunities):
        product = product_by_id.get(opp.get("product_id", ""))
        if not product:
            continue
        fields = _extract_product_fields(product, opp, product_labels, trend_signals)

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
        )
        fallback = _fallback_pack(
            fields["product_title"], fields["current_meta_title"], fields["current_meta_description"]
        )
        pack = _complete_json(llm_router, prompt, _PASS1_KEYS, fallback, fields["product_title"])

        # Enrich candidate keywords: free first, then each enabled paid provider
        if pack.get("seo_keywords"):
            signals = signals_from_llm_keywords(pack["seo_keywords"])
            signals = free_provider.enrich(signals, shop=shop)
            for paid in paid_providers:
                signals = paid.enrich(signals, shop=shop)
            pack["seo_keywords"] = _apply_signals_to_keywords(pack["seo_keywords"], signals)

        pass1_states.append({"product": product, "opp": opp, "fields": fields, "pack": pack})

        if progress_callback is not None:
            try:
                partial = [_build_product_result(s["product"], s["opp"], s["pack"], shop) for s in pass1_states]
                progress_callback(idx + 1, total, partial, "targeting")
            except Exception:
                pass

    # ── Global batch: SERP intelligence, keyword ideas, competitor signals ───
    serp_keywords: list[str] = []
    for state in pass1_states:
        kws = state["pack"].get("seo_keywords", []) or []
        top = sorted(
            [k for k in kws if isinstance(k, dict)],
            key=lambda k: k.get("demand_score", 0),
            reverse=True,
        )[:2]
        for k in top:
            q = k.get("query")
            if q and q not in serp_keywords:
                serp_keywords.append(str(q))

    serp_intel: dict[str, dict[str, Any]] = {}
    if dataforseo_provider.available and serp_keywords:
        serp_intel = dataforseo_provider.fetch_serp_intelligence(serp_keywords)
        if serp_intel:
            sources_used.append("dataforseo_serp")

    # Keyword Ideas — add DataForSEO suggestions to top-5 products by opportunity_score
    if dataforseo_provider.available:
        top_states = sorted(
            pass1_states,
            key=lambda s: s["pack"].get("opportunity_score", s["opp"].get("opportunity_score", 0)),
            reverse=True,
        )[:5]
        for state in top_states:
            kws = state["pack"].get("seo_keywords", []) or []
            seeds = [
                k["query"] for k in sorted(kws, key=lambda k: k.get("demand_score", 0), reverse=True)[:3]
                if isinstance(k, dict) and k.get("query")
            ]
            if not seeds:
                continue
            ideas = dataforseo_provider.fetch_keyword_ideas(seeds, limit=15)
            if ideas:
                existing = {k.get("query", "").lower() for k in kws if isinstance(k, dict)}
                new_ideas = [
                    i for i in ideas
                    if i.get("query", "").lower() not in existing
                    and _idea_is_relevant(i.get("query", ""), seeds)
                ]
                state["pack"]["seo_keywords"] = list(kws) + new_ideas
                if "dataforseo_keyword_ideas" not in sources_used:
                    sources_used.append("dataforseo_keyword_ideas")

    competitor_signals = build_competitor_signals(shop, keywords=serp_keywords or None)
    if competitor_signals:
        sources_used.append("competitors_manual")
    if dataforseo_provider.available and serp_keywords:
        serp_signals = dataforseo_provider.fetch_serp_competitors(serp_keywords)
        if serp_signals:
            competitor_signals = list(competitor_signals) + serp_signals
    if dataforseo_provider.available and shop:
        domain_signals = dataforseo_provider.fetch_domain_competitors(shop)
        if domain_signals:
            competitor_signals = list(competitor_signals) + domain_signals
            if "dataforseo_domain_competitors" not in sources_used:
                sources_used.append("dataforseo_domain_competitors")

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
        if run_pass2:
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
            )
            pack = _complete_json(llm_router, prompt, _PASS2_KEYS, pack, fields["product_title"])

        product_results.append(_build_product_result(state["product"], state["opp"], pack, shop))
        if progress_callback is not None:
            try:
                progress_callback(idx + 1, total, list(product_results), "content")
            except Exception:
                pass

    total_opportunity_count = sum(
        len(r.get("seo_keywords", [])) + len(r.get("geo_questions", []))
        for r in product_results
    )

    return {
        "shop": shop,
        "analyzed_at": datetime.now(UTC).isoformat(),
        "active_product_count": len(active_products),
        "analyzed_product_count": len(product_results),
        "total_opportunity_count": total_opportunity_count,
        "sources_used": sources_used,
        "provider_status": provider_status,
        "competitor_signals": competitor_signals,
        "products": product_results,
        "budget": budget_status,
    }
