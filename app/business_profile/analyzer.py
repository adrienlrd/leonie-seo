"""Business profile analyzer — extracts niche, brand voice, personas, and content style via LLM."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any

logger = logging.getLogger(__name__)

_BLOG_URL_MARKERS = ("/blog/", "/article/", "/guide/", "/conseil/", "/tuto/", "/how-to/", "/comment-")


def _extract_products_summary(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    raw_products = snapshot.get("products", [])
    products = (raw_products if isinstance(raw_products, list) else [])[:30]
    summary = []
    for p in products:
        if not isinstance(p, dict):
            continue
        raw_coll = p.get("collections")
        coll_list = raw_coll if isinstance(raw_coll, list) else []
        collections = [c.get("title", "") for c in coll_list[:5] if isinstance(c, dict)]

        raw_tags = p.get("tags")
        tags = (raw_tags if isinstance(raw_tags, list) else [])[:10]

        summary.append({
            "title": str(p.get("title", ""))[:120],
            "collections": collections,
            "tags": [str(t) for t in tags],
        })
    return summary


def _top_gsc_queries(gsc_query_rows: list[dict[str, Any]], max_count: int = 20) -> list[dict[str, Any]]:
    sorted_rows = sorted(gsc_query_rows, key=lambda r: r.get("impressions", 0), reverse=True)
    return sorted_rows[:max_count]


def _fetch_serp_data(seeds: list[str]) -> dict[str, Any]:
    """Fetch competitor domains, PAA questions, and blog content from DataForSEO SERP."""
    empty: dict[str, Any] = {"competitor_domains": [], "paa_questions": [], "blog_results": []}
    try:
        from app.market_analysis.providers.dataforseo_provider import (  # noqa: PLC0415
            DataForSEOProvider,
        )

        provider = DataForSEOProvider()
        if not provider.available:
            return empty

        domains: dict[str, int] = {}
        paa: list[str] = []
        blog_results: list[dict[str, Any]] = []

        for seed in seeds[:5]:
            intelligence = provider.fetch_serp_intelligence([seed])
            for _kw, data in intelligence.items():
                for paa_q in data.get("paa", []) or []:
                    if paa_q and paa_q not in paa:
                        paa.append(paa_q)
                for comp in data.get("top_competitors", []):
                    domain = str(comp.get("domain") or "").strip()
                    if domain:
                        domains[domain] = domains.get(domain, 0) + 1
                    url = str(comp.get("url", ""))
                    if any(marker in url for marker in _BLOG_URL_MARKERS) and len(blog_results) < 10:
                        blog_results.append({
                            "title": comp.get("title", ""),
                            "snippet": comp.get("snippet", ""),
                            "url": url,
                        })

        sorted_domains = sorted(domains.items(), key=lambda x: x[1], reverse=True)
        return {
            "competitor_domains": [d for d, _ in sorted_domains[:10]],
            "paa_questions": paa[:15],
            "blog_results": blog_results,
        }
    except Exception as exc:
        logger.warning("DataForSEO SERP fetch failed (non-fatal): %s", exc)
        return empty


def _resolve_brand_name(shop: str, snapshot: dict[str, Any]) -> str:
    """Extract the brand name from snapshot: shop.name → product.vendor → stripped domain."""
    shop_info = snapshot.get("shop") or {}
    name = str(shop_info.get("name") or "").strip()
    if name:
        return name
    raw_products = snapshot.get("products", [])
    for p in (raw_products if isinstance(raw_products, list) else [])[:10]:
        if isinstance(p, dict):
            vendor = str(p.get("vendor") or "").strip()
            if vendor:
                return vendor
    return shop.removesuffix(".myshopify.com")


def _load_market_analysis_competitors(shop: str) -> list[str]:
    """Extract unique competitor domains from the latest market analysis result."""
    try:
        from app.market_analysis.jobs import load_latest_result  # noqa: PLC0415

        result = load_latest_result(shop)
        if not result:
            return []
        seen: set[str] = set()
        domains: list[str] = []
        for sig in (result.get("competitor_signals") or []):
            domain = str(sig.get("domain") or "").strip().lower()
            if domain and domain not in seen:
                seen.add(domain)
                domains.append(domain)
        return domains[:10]
    except Exception:
        return []


def analyze_business_profile(
    shop: str,
    snapshot: dict[str, Any],
    gsc_query_rows: list[dict[str, Any]],
    niche_hypothesis: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Analyze the business profile of a Shopify store using snapshot, GSC data, and LLM.

    Returns a profile dict with: niche_summary, brand_name, brand_voice, target_personas,
    content_style, key_themes, seasonal_patterns, competitor_domains, competitor_insights,
    content_gaps, internal_link_priorities, generated_at, status, sources_used.
    """
    brand_name = _resolve_brand_name(shop, snapshot)

    products_summary = _extract_products_summary(snapshot)
    top_queries = _top_gsc_queries(gsc_query_rows, max_count=20)

    seed_queries = [row["query"] for row in top_queries[:5] if row.get("query")]
    serp_data = _fetch_serp_data(seed_queries)
    paa_questions = serp_data["paa_questions"]
    blog_results = serp_data["blog_results"]

    # Prefer market analysis domain competitors (already computed via DataForSEO domain API)
    market_competitors = _load_market_analysis_competitors(shop)
    competitor_domains = market_competitors or serp_data["competitor_domains"]

    sources_used: list[str] = ["shopify_snapshot"]
    if top_queries:
        sources_used.append("gsc_queries")
    if market_competitors:
        sources_used.append("market_analysis_competitors")
    elif serp_data["competitor_domains"] or blog_results:
        sources_used.append("dataforseo_serp")
    if niche_hypothesis:
        sources_used.append("niche_hypothesis")

    niche_hint = ""
    if niche_hypothesis:
        niche_hint = f"\nHypothèse niche validée : {json.dumps(niche_hypothesis, ensure_ascii=False)}"

    products_text = json.dumps(products_summary[:20], ensure_ascii=False, indent=None)
    queries_text = json.dumps(
        [{"query": r["query"], "impressions": r["impressions"]} for r in top_queries],
        ensure_ascii=False,
    )
    blog_text = json.dumps(blog_results, ensure_ascii=False) if blog_results else "[]"
    domains_text = ", ".join(competitor_domains) if competitor_domains else "aucun détecté"
    paa_text = json.dumps(paa_questions, ensure_ascii=False) if paa_questions else "[]"

    prompt = f"""Tu es expert en stratégie de contenu SEO e-commerce.

Boutique Shopify : {brand_name}
Top produits (titre, collections, tags) :
{products_text}

Top requêtes GSC (impressions) :
{queries_text}

Domaines concurrents détectés dans les SERP :
{domains_text}

Questions "People Also Ask" détectées :
{paa_text}

Articles de blog concurrents (titre + snippet) :
{blog_text}
{niche_hint}

Analyse cette boutique et retourne UNIQUEMENT un objet JSON valide (pas de markdown, pas de texte avant/après) avec exactement ces clés :
{{
  "niche_summary": "description précise de la niche en 2-3 phrases",
  "brand_name": "nom de la marque détecté",
  "brand_voice": "ton et style de communication (1 paragraphe)",
  "target_personas": [
    {{
      "name": "nom du persona",
      "description": "description courte",
      "main_need": "besoin principal",
      "buying_trigger": "déclencheur d'achat"
    }}
  ],
  "content_style": {{
    "tone": "ex: expert et bienveillant",
    "typical_article_length": "ex: 1200-1800 mots",
    "h2_structure": ["H2 typique 1", "H2 typique 2", "H2 typique 3", "H2 typique 4"],
    "vocabulary_to_use": ["mot1", "mot2", "mot3"],
    "vocabulary_to_avoid": ["mot1", "mot2"],
    "hook_patterns": ["formule accrocheuse 1", "formule accrocheuse 2", "formule accrocheuse 3"]
  }},
  "key_themes": ["thème 1", "thème 2", "thème 3", "thème 4", "thème 5", "thème 6"],
  "seasonal_patterns": [
    {{"period": "ex: Noël", "theme": "thème saisonnier", "intensity": "high"}}
  ],
  "competitor_domains": ["domaine1.com", "domaine2.com"],
  "competitor_insights": [
    "observation sur la stratégie de contenu des concurrents"
  ],
  "content_gaps": [
    "sujet non couvert par les concurrents mais pertinent pour la boutique"
  ],
  "internal_link_priorities": ["handle-produit-1", "handle-produit-2"]
}}

Retourne 2-3 personas, 6-8 key_themes, 3-5 seasonal_patterns, les domaines concurrents réels détectés, 3-5 competitor_insights, 3-5 content_gaps, 5-8 internal_link_priorities."""

    try:
        from app.llm import LLMError, get_router  # noqa: PLC0415

        llm_router = get_router(shop=shop)
        result = llm_router.complete(
            prompt,
            system="Tu es expert en stratégie de contenu SEO e-commerce. Réponds uniquement avec du JSON valide.",
            max_tokens=2500,
            temperature=0.3,
        )
        raw_text = result.text.strip()

        if raw_text.startswith("```"):
            lines = raw_text.split("\n")
            raw_text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

        profile = json.loads(raw_text)

    except LLMError as exc:
        logger.error("LLM failed for business profile (%s): %s", shop, exc)
        return {
            "status": "error",
            "error": str(exc),
            "generated_at": datetime.now(UTC).isoformat(),
            "sources_used": sources_used,
        }
    except (json.JSONDecodeError, ValueError) as exc:
        logger.error("LLM returned invalid JSON for business profile (%s): %s", shop, exc)
        return {
            "status": "error",
            "error": f"JSON malformé: {exc}",
            "generated_at": datetime.now(UTC).isoformat(),
            "sources_used": sources_used,
        }

    # Merge in the raw DataForSEO domains if LLM didn't return any
    if not profile.get("competitor_domains") and competitor_domains:
        profile["competitor_domains"] = competitor_domains

    profile["generated_at"] = datetime.now(UTC).isoformat()
    profile["status"] = "draft"
    profile["sources_used"] = sources_used
    return profile
