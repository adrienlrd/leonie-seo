"""Engine for the competitor profile page.

Two layers:
  1. aggregate_competitors_from_serp() — SYNCHRONOUS, instant. Reads the SERP
     cache (no API call), groups by competitor domain, and returns a profile per
     competitor: ranked keywords, strength, sample titles, PAA questions. This is
     what the page shows immediately.
  2. run_competitor_serp_crawl() — background job. Crawls ONE top-ranked page per
     competitor, then asks the LLM to synthesize what each competitor does well
     and what the merchant can exploit. Enriches the profiles in place.
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import replace
from datetime import UTC, datetime
from statistics import mean
from typing import Any
from urllib.parse import urlsplit

from app.business_profile.jobs import load_business_profile
from app.llm import LLMError, get_router
from app.market_analysis import keyword_cache
from app.market_analysis.competitor_crawl.config import CompetitorCrawlConfig
from app.market_analysis.competitor_crawl.fetcher import fetch_competitor_targets
from app.market_analysis.competitor_crawl.insights import url_to_competitor_top_url
from app.market_analysis.competitor_crawl.models import CompetitorCrawlTarget
from app.market_analysis.competitor_crawl.url_selection import canonicalize_competitor_url
from app.market_analysis.jobs import load_latest_result

logger = logging.getLogger(__name__)

_LOCATION_CODE = 2250
_LANGUAGE_CODE = "fr"
_BLOCKED_PATH_PARTS = ("/cart", "/checkout", "/account", "/search", "/login", "/register")
_MAX_COMPETITORS = 8

_SYNTHESIS_SYSTEM = (
    "Tu es un expert SEO/GEO francophone qui aide un marchand Shopify à comprendre "
    "ce que font ses concurrents pour s'en inspirer. Tu réponds UNIQUEMENT en JSON "
    "valide, en français, sans copier le texte des concurrents — tu décris des "
    "patterns et des actions concrètes."
)


def build_config_for_serp_job() -> CompetitorCrawlConfig:
    """Build a crawl config for the enrichment job: 1 page per competitor."""
    base = CompetitorCrawlConfig.from_env()
    return replace(base, enabled=True, max_urls_per_run=_MAX_COMPETITORS)


# ── Layer 1: instant SERP aggregation ─────────────────────────────────────────


def aggregate_competitors_from_serp(
    shop: str, *, max_competitors: int = _MAX_COMPETITORS
) -> dict[str, Any]:
    """Build one profile per competitor domain from the cached SERP intel.

    Synchronous and fast (cache reads only). No crawl, no LLM. Used by the
    /preview endpoint so the page renders immediately.
    """
    result = load_latest_result(shop)
    if not result:
        return _empty_result(shop, error="no_market_analysis")

    merchant_domains = _collect_merchant_domains(shop)
    all_keywords = _collect_all_keywords(result)
    serp_cache = keyword_cache.get_many(
        keyword_cache.SERP,
        list(all_keywords),
        location_code=_LOCATION_CODE,
        language_code=_LANGUAGE_CODE,
    )
    missing = len(all_keywords) - len(serp_cache)
    if missing > 0:
        logger.warning(
            "competitor_serp: %d/%d keywords missing from SERP cache", missing, len(all_keywords)
        )

    by_domain: dict[str, dict[str, Any]] = {}
    for kw_norm, intel in serp_cache.items():
        paa = [str(q) for q in (intel.get("paa") or []) if str(q).strip()]
        for comp in intel.get("top_competitors") or []:
            if not isinstance(comp, dict):
                continue
            domain = _normalize_domain(str(comp.get("domain", "")))
            if not domain or _is_merchant(domain, merchant_domains):
                continue
            url = str(comp.get("url", "")).strip()
            canonical = canonicalize_competitor_url(url) if url else ""
            if canonical and _is_blocked_path(canonical):
                canonical = ""
            rank = int(comp.get("rank") or 99)
            entry = by_domain.setdefault(
                domain,
                {"domain": domain, "ranked_keywords": [], "_paa": set(), "_urls": []},
            )
            entry["ranked_keywords"].append({
                "keyword": kw_norm,
                "rank": rank,
                "title": str(comp.get("title", "")).strip(),
                "url": canonical or url,
            })
            entry["_paa"].update(paa)
            if canonical:
                entry["_urls"].append((rank, canonical, str(comp.get("title", "")).strip()))

    competitors = [_finalize_profile(entry) for entry in by_domain.values()]
    competitors.sort(key=lambda c: (-c["estimated_strength"], c["domain"]))
    competitors = competitors[:max_competitors]

    return {
        "created_at": datetime.now(UTC).isoformat(),
        "shop": shop,
        "competitors": competitors,
        "keywords_used": len(serp_cache),
        "enriched": False,
    }


def _finalize_profile(entry: dict[str, Any]) -> dict[str, Any]:
    ranked = sorted(entry["ranked_keywords"], key=lambda k: k["rank"])
    ranks = [k["rank"] for k in ranked] or [99]
    best_rank = min(ranks)
    avg_rank = round(mean(ranks), 1)
    count = len(ranked)
    # Strength: better rank + more keywords ranked → stronger competitor.
    strength = max(10, min(100, int((100 - best_rank * 5) + min(30, count * 3))))
    top_urls = sorted(entry["_urls"], key=lambda u: u[0])
    top_page_url = top_urls[0][1] if top_urls else ""
    top_page_title = top_urls[0][2] if top_urls else (ranked[0]["title"] if ranked else "")
    sample_titles = []
    for k in ranked:
        title = k["title"]
        if title and title not in sample_titles:
            sample_titles.append(title)
        if len(sample_titles) >= 5:
            break
    return {
        "domain": entry["domain"],
        "estimated_strength": strength,
        "strength_label": _strength_label(strength),
        "ranked_keyword_count": count,
        "best_rank": best_rank,
        "avg_rank": avg_rank,
        "ranked_keywords": ranked[:15],
        "sample_titles": sample_titles,
        "paa_questions": sorted(entry["_paa"])[:10],
        "top_page_url": top_page_url,
        "top_page_title": top_page_title,
        "top_page": None,
        "synthesis": None,
    }


def _strength_label(strength: int) -> str:
    if strength >= 75:
        return "élevée"
    if strength >= 45:
        return "moyenne"
    return "faible"


# ── Layer 2: enrichment (crawl 1 page + LLM synthesis) ────────────────────────


def run_competitor_serp_crawl(shop: str, config: CompetitorCrawlConfig) -> dict[str, Any]:
    """Aggregate, crawl one page per competitor, synthesize, and return the result."""
    preview = aggregate_competitors_from_serp(shop)
    if preview.get("error") or not preview["competitors"]:
        return preview

    competitors = preview["competitors"]
    targets = [
        CompetitorCrawlTarget(
            keyword=(c["ranked_keywords"][0]["keyword"] if c["ranked_keywords"] else ""),
            rank=c["best_rank"],
            domain=c["domain"],
            url=c["top_page_url"],
            title=c["top_page_title"],
        )
        for c in competitors
        if c["top_page_url"]
    ]
    crawl_results = fetch_competitor_targets(targets, config)
    features_by_domain: dict[str, dict[str, Any]] = {}
    for res in crawl_results:
        if res.features and res.status_code and res.status_code < 400 and not res.error:
            features_by_domain[res.target.domain] = res.features

    business_profile = load_business_profile(shop)
    llm_router = _get_router_safe(shop)

    total_crawled = 0
    for competitor in competitors:
        features = features_by_domain.get(competitor["domain"])
        if features:
            total_crawled += 1
            competitor["top_page"] = url_to_competitor_top_url({
                "url": competitor["top_page_url"],
                "domain": competitor["domain"],
                "rank": competitor["best_rank"],
                "keyword": competitor["ranked_keywords"][0]["keyword"] if competitor["ranked_keywords"] else "",
                "title": features.get("title") or competitor["top_page_title"],
                "page_type": features.get("page_type", "unknown"),
                "final_url": competitor["top_page_url"],
                **features,
            })
        competitor["synthesis"] = _synthesize_competitor(
            competitor, features, business_profile, llm_router
        )

    preview["enriched"] = True
    preview["total_pages_crawled"] = total_crawled
    preview["created_at"] = datetime.now(UTC).isoformat()
    return preview


def _synthesize_competitor(
    competitor: dict[str, Any],
    page_features: dict[str, Any] | None,
    business_profile: dict[str, Any] | None,
    llm_router: Any | None,
) -> dict[str, Any] | None:
    """One LLM call per competitor. Fail-open: returns None on any LLM failure."""
    if llm_router is None:
        return None
    prompt = _build_synthesis_prompt(competitor, page_features, business_profile)
    try:
        completion = llm_router.complete(
            prompt,
            system=_SYNTHESIS_SYSTEM,
            max_tokens=700,
            temperature=0.4,
            json_mode=True,
        )
    except LLMError as exc:
        logger.warning("competitor_serp: LLM synthesis failed for %s (%s)", competitor["domain"], exc)
        return None
    raw = completion.text.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```[a-z]*\n?", "", raw)
        raw = re.sub(r"\n?```$", "", raw)
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("competitor_serp: unparseable LLM JSON for %s", competitor["domain"])
        return None
    if not isinstance(parsed, dict):
        return None
    return {
        "title_style": str(parsed.get("title_style", "")).strip(),
        "strengths": _coerce_str_list(parsed.get("strengths")),
        "opportunities": _coerce_str_list(parsed.get("opportunities")),
        "inspiration": _coerce_str_list(parsed.get("inspiration")),
    }


def _build_synthesis_prompt(
    competitor: dict[str, Any],
    page_features: dict[str, Any] | None,
    business_profile: dict[str, Any] | None,
) -> str:
    titles = "\n".join(f"  - {t}" for t in competitor["sample_titles"][:5]) or "  (aucun)"
    keywords = "\n".join(
        f"  - {k['keyword']} (rank {k['rank']})" for k in competitor["ranked_keywords"][:10]
    ) or "  (aucun)"
    paa = "\n".join(f"  - {q}" for q in competitor["paa_questions"][:6]) or "  (aucune)"
    page_summary = _format_page_features(page_features)
    merchant = _format_merchant_context(business_profile)
    return (
        f"Concurrent : {competitor['domain']} (force SEO estimée : "
        f"{competitor['strength_label']}, {competitor['ranked_keyword_count']} mots-clés rankés)\n\n"
        f"Titres SEO du concurrent :\n{titles}\n\n"
        f"Mots-clés sur lesquels il apparaît :\n{keywords}\n\n"
        f"Questions People-Also-Ask autour de ces mots-clés :\n{paa}\n\n"
        f"Structure de sa page la mieux classée :\n{page_summary}\n\n"
        f"Contexte de la boutique du marchand :\n{merchant}\n\n"
        "Analyse ce concurrent et réponds en JSON avec EXACTEMENT ces clés :\n"
        '{\n'
        '  "title_style": "1 phrase décrivant le style/structure de ses titres SEO",\n'
        '  "strengths": ["3-4 choses que ce concurrent fait bien en SEO/contenu"],\n'
        '  "opportunities": ["2-3 angles qu\'il néglige et que le marchand peut exploiter"],\n'
        '  "inspiration": ["2-3 actions concrètes et activables pour le marchand"]\n'
        '}\n'
        "Sois concret et spécifique au secteur du marchand. Pas de généralités vagues."
    )


def _format_page_features(features: dict[str, Any] | None) -> str:
    if not features:
        return "  (page non crawlée)"
    bits = [
        f"  - Longueur : {features.get('word_count', 0)} mots",
        f"  - FAQ visible : {'oui' if features.get('has_faq_block') else 'non'}",
        f"  - Schema Product : {'oui' if features.get('has_product_schema') else 'non'}",
        f"  - Tableau comparatif : {'oui' if features.get('has_comparison_table') else 'non'}",
        f"  - Blocs réponse courte : {'oui' if features.get('has_short_answer_block') else 'non'}",
        f"  - Liens internes : {features.get('internal_link_count', 0)}",
        f"  - H2 : {', '.join((features.get('h2_texts') or [])[:5]) or '—'}",
    ]
    return "\n".join(bits)


def _format_merchant_context(business_profile: dict[str, Any] | None) -> str:
    if not business_profile:
        return "  (profil marchand non renseigné)"
    bits = []
    for key, label in (
        ("brand_name", "Marque"),
        ("niche_summary", "Niche"),
        ("brand_voice", "Voix de marque"),
    ):
        value = str(business_profile.get(key) or "").strip()
        if value:
            bits.append(f"  - {label} : {value}")
    themes = business_profile.get("key_themes")
    if isinstance(themes, list):
        joined = ", ".join(str(t).strip() for t in themes if str(t).strip())
        if joined:
            bits.append(f"  - Thèmes clés : {joined}")
    personas = business_profile.get("target_personas")
    if isinstance(personas, list):
        names = ", ".join(
            str(p.get("name", "")).strip()
            for p in personas[:3]
            if isinstance(p, dict) and str(p.get("name", "")).strip()
        )
        if names:
            bits.append(f"  - Cibles : {names}")
    return "\n".join(bits) or "  (profil marchand vide)"


# ── Helpers ───────────────────────────────────────────────────────────────────


def _get_router_safe(shop: str) -> Any | None:
    try:
        return get_router(shop=shop)
    except LLMError as exc:
        logger.warning("competitor_serp: no LLM provider configured (%s)", exc)
        return None


def _coerce_str_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(v).strip() for v in value if str(v).strip()][:5]


def _empty_result(shop: str, *, error: str) -> dict[str, Any]:
    return {
        "created_at": datetime.now(UTC).isoformat(),
        "shop": shop,
        "competitors": [],
        "keywords_used": 0,
        "enriched": False,
        "error": error,
    }


def _collect_merchant_domains(shop: str) -> set[str]:
    return {_normalize_domain(shop)} - {""}


def _collect_all_keywords(result: dict[str, Any]) -> set[str]:
    keywords: set[str] = set()
    for product in result.get("products") or []:
        for kw in product.get("seo_keywords") or []:
            if isinstance(kw, dict):
                query = str(kw.get("query", "")).strip().lower()
                if query:
                    keywords.add(query)
    return keywords


def _normalize_domain(value: str) -> str:
    raw = value.strip().lower()
    if not raw:
        return ""
    if "://" in raw:
        raw = urlsplit(raw).netloc.lower()
    raw = raw.split("/")[0].split(":")[0]
    return raw[4:] if raw.startswith("www.") else raw


def _is_merchant(domain: str, merchant_domains: set[str]) -> bool:
    return any(domain == m or domain.endswith(f".{m}") for m in merchant_domains)


def _is_blocked_path(url: str) -> bool:
    path = urlsplit(url).path.lower().rstrip("/")
    return any(path == part or path.startswith(f"{part}/") for part in _BLOCKED_PATH_PARTS)
