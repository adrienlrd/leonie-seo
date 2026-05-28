"""Market analysis engine — per-product SEO/GEO opportunity + content pack generation."""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from app.business_profile.context import build_business_profile_context_meta
from app.geo.facts import analyze_product_facts
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
        "targets",
        "properties",
        "warranty",
        "delivery",
        "returns",
        "care",
        "dimensions",
        "compatibility",
        "size_recommendation",
        "use_cases",
        "selection_criteria",
    }
)
_NARRATIVE_FACT_KEYS = _INFORMATIVE_FACT_KEYS - {"description", "price"}
_MERCHANT_FACT_LABELS = {
    "materials": "Materials",
    "origins": "Manufacturing origin",
    "certifications": "Certifications",
    "warranty": "Warranty",
    "care": "Care instructions",
    "dimensions": "Dimensions",
    "compatibility": "Compatibility",
    "size_recommendation": "Size recommendation",
    "use_cases": "Confirmed use cases",
    "selection_criteria": "Selection criteria",
}

_CLAIM_PATTERNS: tuple[tuple[str, str], ...] = (
    ("materials", r"\b(coton|nylon|cuir|acier|inox|bois|silicone|bambou|polyester)\b"),
    ("origins", r"\b(fabriqu[ée]?\s+en|made\s+in|origine|france|europ[ée]en)\b"),
    ("certifications", r"\b(certifi[ée]?|bio|organic|fsc|oeko|gots)\b"),
    ("warranty", r"\b(garantie|garanti|warranty|satisfait\s+ou\s+rembours)\b"),
    ("delivery", r"\b(livraison|exp[ée]dition|delivery|shipping)\b"),
    ("returns", r"\b(retours?|remboursement|refund|returns?)\b"),
    ("care", r"\b(lavable|nettoyage|entretien|washable|cleaning)\b"),
    ("dimensions", r"\b\d+(?:[.,]\d+)?\s?(?:cm|mm|ml|l|kg|g)\b"),
    ("compatibility", r"\b(compatible|adapt[ée]\s+[àa]|convient\s+[àa])\b"),
    ("performance", r"\b(silencieu(?:x|se)|ultra[- ]?silencieu(?:x|se)|anti[- ]?fuite)\b"),
    (
        "sustainability",
        r"\b([ée]cologique|[ée]co[- ]?responsable|durable|recycl[ée]?|biod[ée]gradable)\b",
    ),
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
    business_context: str = "",
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
        f"STOCK: {stock_text}\n"
        f"SCORE OPPORTUNITÉ: {opportunity_score}/100\n\n"
        f"IMPORTANT: nous sommes en {current_year}. "
        "N'utilise jamais d'années passées dans les titres, exemples ou références. "
        "Toutes les propositions doivent être actuelles et pertinentes pour l'année en cours.\n\n"
        "ÉTAPE 1/2 — CIBLAGE. Identifie le produit et les cibles de recherche. "
        "Ne rédige PAS encore de contenu (meta, description, FAQ) : cela viendra à l'étape 2 "
        "avec des données réelles de marché.\n"
        "RÈGLE MOTS-CLÉS : priorité absolue aux requêtes mid-tail (2-4 mots) avec volume réel en France. "
        "Les 2-3 premiers seo_keywords doivent être mid-tail (ex. 'croquettes chat senior', 'fontaine eau chat'). "
        "Les longues traînes (5+ mots) sont autorisées uniquement en fin de liste comme support FAQ/GEO "
        "(ex. 'comment choisir fontaine eau chat', 'quelle croquette chaton 2 mois'). "
        "Ne génère jamais de requête ultra-spécifique impossible à trouver dans Google Ads France.\n"
        "Réponds uniquement en JSON valide avec exactement ces clés : "
        "product_summary, target_customer, buying_intents (liste de strings), "
        "seo_keywords (5-8 objets avec query/intent_type/demand_score/competition_score/product_fit_score/reason), "
        "geo_questions (5-8 objets avec question/answer_angle/content_block_type/confidence)."
    )


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
            "\nAUTRES MOTS-CLÉS LIÉS (utilise-en au moins 2 dans description/FAQ/blog): "
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
    if crawl_lines:
        parts.append("\n=== PROBLÈMES TECHNIQUES DÉTECTÉS (crawl) ===")
        parts.extend(crawl_lines)
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
    if forbidden_phrases:
        parts.append("\n=== FORMULATIONS INTERDITES ===")
        parts.extend(f"  - {phrase}" for phrase in forbidden_phrases)

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

    parts.append(
        f"\n═══════════════════════════════════════════════════════════════════\n"
        f"ÉTAPE 2/2 — RÈGLES STRICTES PAR CHAMP (RESPECT OBLIGATOIRE)\n"
        f"═══════════════════════════════════════════════════════════════════\n"
        f"\nTOP 5 mots-clés à utiliser : {top_kw_list}\n"
        f"Les cibles sont classées selon demande, concurrence, adéquation produit et niveau de preuve. "
        f"Les mots-clés guident l'intention, jamais des affirmations. "
        f"Utilise uniquement les faits confirmés pour parler du produit.\n"
        f"\n▶ proposed_meta_title (45-60 caractères) :\n"
        f'   • Contient naturellement le mot-clé #1 ("{top_kw_1}") OU une variation proche.\n'
        f"   • Différenciant vs CONCURRENTS SERP listés (jamais copier leur formulation).\n"
        f"\n▶ proposed_meta_description (120-160 caractères) :\n"
        f"   • Contient naturellement le mot-clé #1 ; ajoute une cible secondaire seulement si la phrase reste utile et lisible.\n"
        f"   • Bénéfice produit ou CTA seulement s'il est confirmé par les données produit fournies.\n"
        f"   • Si des concurrents sont listés, adopte une formulation propre sans prétendre couvrir un manque non vérifié.\n"
        f"\n▶ proposed_product_description (200-300 mots, plusieurs paragraphes) :\n"
        f"   • Si la surface est marquée NE PAS GÉNÉRER, retourne une chaîne vide.\n"
        f"   • Couvre l'intention principale puis des sujets secondaires uniquement lorsqu'ils apportent une information vérifiée.\n"
        f"   • Première phrase peut contenir le mot-clé #1 si cela reste naturel.\n"
        f"   • Explique seulement les caractéristiques et usages confirmés dans le contexte produit.\n"
        f"\n▶ proposed_faq (5-8 entrées) :\n"
        f"   • Si la surface est marquée NE PAS GÉNÉRER, retourne une liste vide.\n"
        f"   • Si des QUESTIONS PAA Google sont présentes : reprends les plus pertinentes (reformulation autorisée).\n"
        f"   • Sinon : réponds aux intentions utiles du produit sans inventer une question issue de Google.\n"
        f"   • Utilise les mots-clés naturellement, sans répétition forcée dans chaque question.\n"
        f"   • Réponses 2-4 phrases factuelles ; pas de blabla marketing.\n"
        f"\n▶ proposed_geo_answer_block :\n"
        f"   • Si la surface est marquée NE PAS GÉNÉRER, retourne une chaîne vide.\n"
        f"   • Fournit une réponse courte uniquement à partir des faits confirmés.\n"
        f"\n▶ proposed_blog_title :\n"
        f"   • Si la surface blog est marquée NE PAS GÉNÉRER, retourne title/intro vides et outline vide.\n"
        f"   • S'il est généré, contient un mot-clé longue traîne ou un intent informationnel depuis la liste.\n"
        f"   • Différent des titres concurrents SERP ET des domaines concurrents listés.\n"
        f"\n▶ proposed_blog_intro (2-3 phrases) :\n"
        f"   • Seulement si le blog est généré : introduit naturellement l'intention ciblée.\n"
        f"\n▶ proposed_blog_outline (5-7 sections H2) :\n"
        f"   • Seulement si le blog est généré : chaque H2 couvre une intention ou question pertinente.\n"
        f"   • Si des concurrents sont présents, différencie le cadrage sans affirmer ce qu'ils ne traitent pas.\n"
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
        f"- Si GSC réel montre un keyword en position 4-20 et que le blog est autorisé, traite cette intention en priorité.\n"
        f"- Si des CONCURRENTS DE DOMAINE sont listés : différencie uniquement les champs autorisés de leurs formulations.\n"
        f"\nRéponds UNIQUEMENT en JSON valide avec ces clés exactes : "
        f"proposed_meta_title, proposed_meta_description, proposed_product_title_if_different, "
        f"proposed_product_description, proposed_faq (5-8 objets {{q, a}}), "
        f"proposed_geo_answer_block (40-80 mots, factuel, cite 1 mot-clé), "
        f"proposed_blog_title, proposed_blog_outline (liste strings), proposed_blog_intro, "
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
            merged["data_source"] = sig.get("source", "llm_estimated")
            merged["difficulty_source"] = sig.get("difficulty_source", "free_estimated")
            merged["search_volume"] = sig.get(
                "search_volume"
            )  # None in free mode — UI shows "missing"
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
        w
        for w in re.findall(r"[a-zàâäéèêëîïôùûüç]+", text.lower())
        if len(w) >= 3 and w not in _FR_STOP_WORDS
    )


def _content_word_count(text: str) -> int:
    """Count meaningful words while preserving repetitions for length checks."""
    return sum(
        1
        for word in re.findall(r"[a-zàâäéèêëîïôùûüç]+", text.lower())
        if len(word) >= 3 and word not in _FR_STOP_WORDS
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


def _score_idea_fit(idea_query: str, product_words: frozenset[str]) -> int:
    """Heuristic product_fit_score for DataForSEO keyword ideas (no extra LLM call).

    Counts content-word overlap between the idea and the product's own text
    (title + handle + tags + collections). Ideas already passed _idea_is_relevant,
    so they share words with the seed keywords; a 0-overlap result here still gets
    a non-zero floor (50) rather than the misleading 0 from the provider.
    """
    idea_words = _content_words(idea_query)
    overlap = len(idea_words & product_words)
    if overlap >= 3:
        return 90
    if overlap >= 2:
        return 75
    if overlap >= 1:
        return 60
    return 50


def _keyword_priority_score(keyword: dict[str, Any]) -> int:
    """Score a keyword target using demand, competition and product relevance.

    Evidence raises confidence slightly without allowing a low-fit keyword to
    become the primary target only because a paid provider returned volume.
    """
    demand = max(0.0, min(100.0, float(keyword.get("demand_score", 0) or 0)))
    competition = max(0.0, min(100.0, float(keyword.get("competition_score", 50) or 50)))
    product_fit = max(0.0, min(100.0, float(keyword.get("product_fit_score", 0) or 0)))
    score = 0.45 * demand + 0.20 * (100.0 - competition) + 0.35 * product_fit

    source = str(keyword.get("data_source", "llm_estimated"))
    if source == "gsc":
        score += 5.0
    elif source in {"dataforseo", "google_ads"}:
        score += 3.0
    return max(0, min(100, round(score)))


def _assign_keyword_targets(keywords: list[dict[str, Any]]) -> list[dict[str, Any]]:
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
        candidate["priority_score"] = _keyword_priority_score(candidate)
        ranked.append(candidate)

    ranked.sort(
        key=lambda keyword: (
            -int(keyword.get("priority_score", 0)),
            -int(keyword.get("product_fit_score", 0) or 0),
            -int(keyword.get("demand_score", 0) or 0),
        )
    )
    for index, keyword in enumerate(ranked, start=1):
        keyword["target_rank"] = index
        if index == 1:
            keyword["target_role"] = "primary"
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
            "generate": has_informative_fact and (has_paa or has_merchant_faq_basis),
            "reason": (
                "verified_paa_and_product_facts_available"
                if has_paa and has_informative_fact
                else "merchant_confirmed_faq_basis_available"
                if has_informative_fact and has_merchant_faq_basis
                else "insufficient_question_or_fact_evidence"
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

    Always returns the 2 editorial questions (benefit + selection guide) so every
    product card offers a way to enrich the analysis.  Up to 2 additional fact-based
    questions are prepended when specific facts are genuinely missing.
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
    }
    questions: list[dict[str, Any]] = []
    for key in (
        "warranty",
        "compatibility",
        "dimensions",
        "care",
        "materials",
        "origins",
        "certifications",
        "size_recommendation",
    ):
        if key not in available_missing:
            continue
        question, placeholder = templates[key]
        questions.append(
            {
                "key": key,
                "question": question,
                "placeholder": placeholder,
                "why_it_matters": (
                    f"Permet une réponse factuelle liée à « {paa_question or primary_query} »."
                ),
                "target_keyword": primary_query,
                "unlocks_surfaces": ["faq", "geo_answer"],
            }
        )
        if len(questions) == 2:
            break
    questions.extend(
        [
            {
                "key": "use_cases",
                "question": f"Quel bénéfice concret « {primary_query} » apporte-t-il à vos clients, et quel problème résout-il ?",
                "placeholder": "Ex. tient chaud aux petits chiens frileux en hiver, évite les frissons après le bain.",
                "why_it_matters": "Fournit l'angle éditorial central pour un article ou une FAQ qui accroche.",
                "target_keyword": primary_query,
                "unlocks_surfaces": ["faq", "blog"],
            },
            {
                "key": "selection_criteria",
                "question": f"Comment un client non-expert devrait-il choisir entre plusieurs « {primary_query} » ?",
                "placeholder": "Ex. selon la race, le poids, la météo ou le niveau d'activité.",
                "why_it_matters": "Structure un guide d'achat naturellement optimisé pour les requêtes de comparaison.",
                "target_keyword": primary_query,
                "unlocks_surfaces": ["blog"],
            },
        ]
    )
    return questions[:4]


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
    unsupported: list[str] = []
    for category, pattern in _CLAIM_PATTERNS:
        if not re.search(pattern, generated_text, flags=re.IGNORECASE):
            continue
        supported_by_source = bool(re.search(pattern, source_text, flags=re.IGNORECASE))
        if category not in confirmed_keys and not supported_by_source:
            unsupported.append(category)
    return unsupported


def _add_quality_issue(quality: dict[str, Any], issue: str) -> None:
    """Append a blocking quality issue and revoke publication eligibility."""
    issues = quality.setdefault("issues", [])
    if issue not in issues:
        issues.append(issue)
    quality["publish_ready"] = False


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
            ]
        ).strip(),
    }
    claims = _coerce_claims(pack.get("claims_used", []))
    evidence_ledger, invalid_claims = _build_evidence_ledger(claims, facts)
    coverage: list[dict[str, Any]] = []
    for target in targets:
        query = str(target["query"])
        coverage.append(
            {
                "query": query,
                "target_role": target.get("target_role", "supporting"),
                "fields": [
                    field_name
                    for field_name, field_text in fields.items()
                    if _keyword_is_covered(query, field_text)
                ],
            }
        )

    issues: list[str] = []
    advisories: list[str] = []
    primary_query = str(targets[0]["query"]) if targets else ""
    if not primary_query:
        issues.append("missing_primary_keyword_target")
    else:
        if not _keyword_is_covered(primary_query, fields["meta_title"]):
            issues.append("meta_title_missing_primary_target")
        if not _keyword_is_covered(primary_query, fields["meta_description"]):
            issues.append("meta_description_missing_primary_target")
        if _enabled_surface(plan, "product_description") and not _keyword_is_covered(
            primary_query, fields["description"]
        ):
            issues.append("description_missing_primary_target")

    if _enabled_surface(plan, "product_description"):
        if not fields["description"]:
            issues.append("missing_recommended_product_description")
        elif _content_word_count(fields["description"]) < 35:
            issues.append("product_description_too_generic")
    elif fields["description"]:
        issues.append("unjustified_product_description_surface")

    paa_questions = [
        question for target in targets for question in target.get("paa_questions", []) if question
    ]
    if _enabled_surface(plan, "faq"):
        if not fields["faq"]:
            issues.append("missing_recommended_faq")
        elif primary_query and not _keyword_is_covered(primary_query, fields["faq"]):
            issues.append("faq_missing_primary_target")
        elif paa_questions and not any(
            _keyword_is_covered(question, fields["faq"]) for question in paa_questions
        ):
            issues.append("faq_missing_available_paa_question")
    elif fields["faq"]:
        issues.append("unjustified_faq_surface")
    if _enabled_surface(plan, "geo_answer") and not fields["geo"]:
        issues.append("missing_geo_answer_block")
    if not _enabled_surface(plan, "geo_answer") and fields["geo"]:
        issues.append("unjustified_geo_answer_surface")
    if _enabled_surface(plan, "blog") and not fields["blog"]:
        issues.append("missing_recommended_blog_support")
    if (
        _enabled_surface(plan, "blog")
        and fields["blog"]
        and primary_query
        and not _keyword_is_covered(primary_query, fields["blog"])
    ):
        issues.append("blog_missing_primary_target")
    if not _enabled_surface(plan, "blog") and fields["blog"]:
        issues.append("unjustified_blog_surface")

    generated_factual_text = " ".join(
        fields[field_name]
        for field_name in ("meta_title", "meta_description", "description", "faq", "geo", "blog")
        if fields[field_name]
    )
    if generated_factual_text and not claims:
        issues.append("missing_claim_evidence_ledger")
    if invalid_claims:
        issues.append("unverified_claim_reference")
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

    unsupported_claims = _detect_unsupported_claim_categories(
        generated_factual_text,
        source_product_text,
        facts,
    )
    if unsupported_claims:
        issues.append("unsupported_product_claims")
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

    return {
        "publish_ready": not issues,
        "issues": issues,
        "advisories": advisories,
        "covered_target_count": sum(1 for item in coverage if item["fields"]),
        "target_count": len(targets),
        "keyword_coverage": coverage,
        "evidence_ledger": evidence_ledger,
        "invalid_claims": invalid_claims,
        "unsupported_claim_categories": unsupported_claims,
        "surface_plan": plan,
        "skipped_surfaces": [
            surface
            for surface in ("product_description", "faq", "geo_answer", "blog")
            if not _enabled_surface(plan, surface)
        ],
    }


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
            "proposed_product_title": _coerce_str(
                llm_pack.get("proposed_product_title_if_different", product_title)
            ),
            "current_product_description_summary": description_summary,
            "proposed_product_description": _coerce_str(
                llm_pack.get("proposed_product_description", "")
            ),
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
            "claims_used": _coerce_claims(llm_pack.get("claims_used", [])),
            "confirmed_facts": llm_pack.get("confirmed_facts", []),
            "surface_plan": llm_pack.get("surface_plan", {}),
            "enrichment_questions": llm_pack.get("enrichment_questions", []),
            "confidence": _coerce_str(llm_pack.get("confidence", "low"), "low"),
            "content_quality": llm_pack.get("content_quality", {}),
        },
        "recommended_content_actions": _coerce_str_list(
            llm_pack.get("recommended_content_actions", [])
        ),
        "confidence": _coerce_str(
            llm_pack.get("confidence", opportunity.get("confidence", "low")), "low"
        ),
        "opportunity_score": opportunity.get("opportunity_score", 0),
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
            max_tokens=max_tokens,
            temperature=0.3,
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
    business_profile: dict[str, Any] | None = None,
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
    if business_context:
        sources_used.append("business_profile")

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
        fields = _extract_product_fields(
            product,
            opp,
            product_labels,
            trend_signals,
            (merchant_facts_by_product or {}).get(str(product.get("id", ""))),
        )

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
        )
        fallback = _fallback_pack(
            fields["product_title"],
            fields["current_meta_title"],
            fields["current_meta_description"],
        )
        pack = _complete_json(llm_router, prompt, _PASS1_KEYS, fallback, fields["product_title"])
        pack["confirmed_facts"] = fields["confirmed_facts"]

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

    # ── Global batch: ideas first, then select the final SERP targets ─────────
    # An idea must be part of the final ranked set before we pay for SERP/PAA
    # evidence; otherwise content may target an idea never checked in the SERP.
    if dataforseo_provider.available:
        for state in pass1_states:
            kws = state["pack"].get("seo_keywords", []) or []
            seeds = [
                k["query"]
                for k in sorted(kws, key=lambda k: k.get("demand_score", 0), reverse=True)[:3]
                if isinstance(k, dict) and k.get("query")
            ]
            if not seeds:
                continue
            ideas = dataforseo_provider.fetch_keyword_ideas(seeds, limit=15)
            if ideas:
                existing = {k.get("query", "").lower() for k in kws if isinstance(k, dict)}
                fields = state["fields"]
                product_text = " ".join(
                    filter(
                        None,
                        [
                            fields.get("product_title", ""),
                            fields.get("handle", "").replace("-", " "),
                            str(fields.get("tags", "")),
                            " ".join(fields.get("collections", [])),
                        ],
                    )
                )
                product_words = _content_words(product_text)
                new_ideas = [
                    {**i, "product_fit_score": _score_idea_fit(i.get("query", ""), product_words)}
                    for i in ideas
                    if i.get("query", "").lower() not in existing
                    and _idea_is_relevant(i.get("query", ""), seeds)
                ]
                state["pack"]["seo_keywords"] = list(kws) + new_ideas
                if "dataforseo_keyword_ideas" not in sources_used:
                    sources_used.append("dataforseo_keyword_ideas")

    serp_keywords: list[str] = []
    for state in pass1_states:
        ranked = _assign_keyword_targets(state["pack"].get("seo_keywords", []) or [])
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

    for state in pass1_states:
        state["pack"]["seo_keywords"] = _attach_serp_evidence(
            state["pack"].get("seo_keywords", []) or [],
            serp_intel,
        )
        state["pack"]["surface_plan"] = _build_surface_plan(
            state["pack"].get("seo_keywords", []) or [],
            state["fields"].get("confirmed_facts", []),
        )
        state["pack"]["enrichment_questions"] = _build_enrichment_questions(
            state["pack"].get("seo_keywords", []) or [],
            state["fields"].get("missing_facts", []),
            state["pack"]["surface_plan"],
        )

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
                ga4_metrics=fields.get("ga4_metrics"),
                domain_competitors=domain_competitor_signals or None,
                confirmed_facts=fields.get("confirmed_facts", []),
                missing_facts=fields.get("missing_facts", []),
                surface_plan=pack.get("surface_plan", {}),
                forbidden_phrases=forbidden_phrases,
                business_context=business_context,
            )
            pack = _complete_json(
                llm_router, prompt, _PASS2_KEYS, pack, fields["product_title"], max_tokens=8192
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

        pack["content_quality"] = _build_content_quality(
            pack,
            confirmed_facts=fields.get("confirmed_facts", []),
            source_product_text=fields.get("source_product_text", ""),
            surface_plan=pack.get("surface_plan", {}),
            forbidden_phrases=forbidden_phrases,
        )
        product_results.append(
            _build_product_result(
                state["product"],
                state["opp"],
                pack,
                shop,
                business_profile_context_hash,
            )
        )
        if progress_callback is not None:
            try:
                progress_callback(idx + 1, total, list(product_results), "content")
            except Exception:
                pass

    _apply_catalog_content_conflicts(product_results, active_products)

    total_opportunity_count = sum(
        len(r.get("seo_keywords", [])) + len(r.get("geo_questions", [])) for r in product_results
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
        "business_profile_context": business_profile_context,
        "products": product_results,
        "budget": budget_status,
    }
