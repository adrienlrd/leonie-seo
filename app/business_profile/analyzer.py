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


def _fetch_blog_results(seeds: list[str]) -> list[dict[str, Any]]:
    """Fetch blog-like SERP results for up to 3 seed queries via DataForSEO."""
    try:
        from app.market_analysis.providers.dataforseo_provider import (
            DataForSEOProvider,  # noqa: PLC0415
        )

        provider = DataForSEOProvider()
        if not provider.available:
            return []

        blog_results: list[dict[str, Any]] = []
        for seed in seeds[:3]:
            intelligence = provider.fetch_serp_intelligence([seed])
            for _kw, data in intelligence.items():
                for competitor in data.get("top_competitors", []):
                    url = str(competitor.get("url", ""))
                    if any(marker in url for marker in _BLOG_URL_MARKERS):
                        blog_results.append({
                            "title": competitor.get("title", ""),
                            "snippet": competitor.get("snippet", ""),
                            "url": url,
                        })
                    if len(blog_results) >= 10:
                        return blog_results
        return blog_results
    except Exception as exc:
        logger.warning("DataForSEO blog fetch failed (non-fatal): %s", exc)
        return []


def analyze_business_profile(
    shop: str,
    snapshot: dict[str, Any],
    gsc_query_rows: list[dict[str, Any]],
    niche_hypothesis: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Analyze the business profile of a Shopify store using snapshot, GSC data, and LLM.

    Args:
        shop: Shop domain.
        snapshot: Shopify snapshot dict (products, collections, shop info).
        gsc_query_rows: List of GSC query rows with impressions, clicks, position.
        niche_hypothesis: Optional validated niche hypothesis dict.

    Returns:
        Business profile dict with niche_summary, brand_name, brand_voice, target_personas,
        content_style, key_themes, seasonal_patterns, competitor_insights,
        internal_link_priorities, generated_at, status, sources_used.
    """
    shop_info = snapshot.get("shop") or {}
    brand_name = shop_info.get("name") or shop

    products_summary = _extract_products_summary(snapshot)
    top_queries = _top_gsc_queries(gsc_query_rows, max_count=20)

    seed_queries = [row["query"] for row in top_queries[:3] if row.get("query")]
    blog_results = _fetch_blog_results(seed_queries)

    sources_used: list[str] = ["shopify_snapshot"]
    if top_queries:
        sources_used.append("gsc_queries")
    if blog_results:
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

    prompt = f"""Tu es expert en stratégie de contenu SEO e-commerce.

Boutique Shopify : {brand_name}
Top produits (titre, collections, tags) :
{products_text}

Top requêtes GSC (impressions) :
{queries_text}

Articles concurrents détectés (titre + snippet) :
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
  "competitor_insights": [
    "observation 1 sur les articles concurrents"
  ],
  "internal_link_priorities": ["handle-produit-1", "handle-produit-2"]
}}

Retourne 2-3 personas, 6-8 key_themes, 3-5 seasonal_patterns, 3-5 competitor_insights, 5-8 internal_link_priorities."""

    try:
        from app.llm import LLMError, get_router  # noqa: PLC0415

        llm_router = get_router(shop=shop)
        result = llm_router.complete(
            prompt,
            system="Tu es expert en stratégie de contenu SEO e-commerce. Réponds uniquement avec du JSON valide.",
            max_tokens=2048,
            temperature=0.3,
        )
        raw_text = result.text.strip()

        # Strip markdown code fences if present
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

    profile["generated_at"] = datetime.now(UTC).isoformat()
    profile["status"] = "draft"
    profile["sources_used"] = sources_used
    return profile
