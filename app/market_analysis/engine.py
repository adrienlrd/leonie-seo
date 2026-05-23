"""Market analysis engine — per-product SEO/GEO opportunity + content pack generation."""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from typing import Any

from app.llm import LLMError, get_router
from app.opportunities.finder import find_opportunities_for_catalog
from app.snapshot.scope import filter_products_by_scope

_SYSTEM_PROMPT = (
    "Tu es un expert SEO et GEO copywriter pour boutiques Shopify. "
    "Réponds toujours avec du JSON valide et rien d'autre. "
    "Ne jamais inventer de faits. Signaler clairement les affirmations incertaines."
)

_JSON_KEYS = (
    "product_summary",
    "target_customer",
    "buying_intents",
    "seo_keywords",
    "geo_questions",
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


def _strip_html(html: str) -> str:
    without_tags = re.sub(r"<[^>]+>", " ", html)
    return re.sub(r"\s+", " ", without_tags).strip()


def _build_prompt(
    product_title: str,
    handle: str,
    description: str,
    collections: list[str],
    tags: str,
    price: str,
    current_meta_title: str,
    current_meta_description: str,
    matched_queries: list[str],
    opportunity_score: int,
    niche_summary: str,
) -> str:
    queries_text = ", ".join(matched_queries[:5]) if matched_queries else "aucune donnée GSC"
    collections_text = ", ".join(collections) if collections else "aucune"

    return (
        f"NICHE: {niche_summary or 'Non définie'}\n"
        f"PRODUIT: {product_title} | handle: {handle} | prix: {price or 'non renseigné'}\n"
        f"DESCRIPTION: {description[:400]}\n"
        f"COLLECTIONS: {collections_text}\n"
        f"TAGS: {tags or 'aucun'}\n"
        f"META TITLE ACTUEL: {current_meta_title or 'absent'}\n"
        f"META DESCRIPTION ACTUELLE: {current_meta_description or 'absente'}\n"
        f"REQUÊTES GSC TOP: {queries_text}\n"
        f"SCORE OPPORTUNITÉ: {opportunity_score}/100\n\n"
        "Réponds uniquement en JSON valide avec exactement ces clés : "
        "product_summary, target_customer, buying_intents (liste de strings), "
        "seo_keywords (5-8 objets avec query/intent_type/demand_score/competition_score/product_fit_score/reason), "
        "geo_questions (5-8 objets avec question/answer_angle/content_block_type/confidence), "
        "proposed_meta_title, proposed_meta_description, proposed_product_title_if_different, "
        "proposed_product_description, proposed_faq (5-8 objets {q, a}), "
        "proposed_geo_answer_block (40-80 mots, factuel), "
        "proposed_blog_title, proposed_blog_outline (liste strings), proposed_blog_intro, "
        "recommended_content_actions (liste strings), facts_used (liste strings), "
        "facts_missing (liste strings), confidence (high/medium/low)."
    )


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
    seo = product.get("seo") or {}
    current_meta_title = seo.get("title") or product_title
    current_meta_description = seo.get("description") or ""
    body_html = product.get("body_html") or product.get("description") or ""
    description_summary = _strip_html(body_html)[:200]

    return {
        "product_id": product_id,
        "product_title": product_title,
        "product_handle": handle,
        "product_url": f"/products/{handle}",
        "product_summary": llm_pack.get("product_summary", ""),
        "target_customer": llm_pack.get("target_customer", ""),
        "buying_intents": llm_pack.get("buying_intents", []),
        "seo_keywords": llm_pack.get("seo_keywords", []),
        "geo_questions": llm_pack.get("geo_questions", []),
        "trend_signals": [],
        "competitor_signals": opportunity.get("signals", []),
        "content_test_pack": {
            "current_meta_title": current_meta_title,
            "proposed_meta_title": llm_pack.get("proposed_meta_title", ""),
            "current_meta_description": current_meta_description,
            "proposed_meta_description": llm_pack.get("proposed_meta_description", ""),
            "current_product_title": product_title,
            "proposed_product_title": llm_pack.get("proposed_product_title_if_different", product_title),
            "current_product_description_summary": description_summary,
            "proposed_product_description": llm_pack.get("proposed_product_description", ""),
            "proposed_faq": llm_pack.get("proposed_faq", []),
            "proposed_geo_answer_block": llm_pack.get("proposed_geo_answer_block", ""),
            "proposed_blog_title": llm_pack.get("proposed_blog_title", ""),
            "proposed_blog_outline": llm_pack.get("proposed_blog_outline", []),
            "proposed_blog_intro": llm_pack.get("proposed_blog_intro", ""),
            "proposed_comparison_or_buying_guide": "",
            "recommended_internal_links": [],
            "content_risks": [],
            "facts_used": llm_pack.get("facts_used", []),
            "facts_missing": llm_pack.get("facts_missing", []),
            "confidence": llm_pack.get("confidence", "low"),
        },
        "recommended_content_actions": llm_pack.get("recommended_content_actions", []),
        "confidence": llm_pack.get("confidence", opportunity.get("confidence", "low")),
        "opportunity_score": opportunity.get("opportunity_score", 0),
        "sources_used": [sig.get("name", "") for sig in opportunity.get("signals", []) if sig.get("score", 0) > 0],
    }


def run_market_analysis(
    products: list[dict[str, Any]],
    shop: str,
    gsc_page_rows: dict[str, dict[str, Any]],
    gsc_query_rows: list[dict[str, Any]],
    *,
    niche_hypothesis: dict[str, Any] | None = None,
    crawl_findings: list[dict[str, Any]] | None = None,
    max_products: int = 10,
) -> dict[str, Any]:
    """Run full SEO/GEO market analysis for active products.

    Returns a structured dict with opportunity scores and AI-generated content
    packs for the top active products. Read-only: no Shopify writes.
    """
    active_products = filter_products_by_scope(products, "active")

    opportunities_result = find_opportunities_for_catalog(
        products,
        shop,
        gsc_page_rows,
        gsc_query_rows,
        niche_hypothesis=niche_hypothesis,
        crawl_findings=crawl_findings,
        scope="active",
        top=max_products,
    )
    opportunities = opportunities_result.get("opportunities", [])

    product_by_id: dict[str, dict[str, Any]] = {
        str(p.get("id", "")): p for p in active_products
    }

    sources_used = ["shopify_snapshot"]
    if gsc_query_rows:
        sources_used.append("gsc")
    if niche_hypothesis:
        sources_used.append("niche_hypothesis")

    niche_summary: str = ""
    if niche_hypothesis:
        niche_summary = niche_hypothesis.get("primary_niche", "")

    llm_router = get_router(shop=shop)
    product_results: list[dict[str, Any]] = []

    for opp in opportunities[:max_products]:
        product_id = opp.get("product_id", "")
        product = product_by_id.get(product_id)
        if not product:
            continue

        product_title = product.get("title", "")
        handle = product.get("handle", "")
        body_html = product.get("body_html") or product.get("description") or ""
        description = _strip_html(body_html)
        seo = product.get("seo") or {}
        current_meta_title = seo.get("title") or product_title
        current_meta_description = seo.get("description") or ""
        collections = [c.get("title", "") for c in (product.get("collections") or [])]
        tags = product.get("tags") or ""
        variants = product.get("variants") or []
        price = str(variants[0].get("price", "")) if variants else ""
        matched_queries: list[str] = opp.get("matched_queries", [])
        opportunity_score: int = opp.get("opportunity_score", 0)

        prompt = _build_prompt(
            product_title=product_title,
            handle=handle,
            description=description,
            collections=collections,
            tags=tags,
            price=price,
            current_meta_title=current_meta_title,
            current_meta_description=current_meta_description,
            matched_queries=matched_queries,
            opportunity_score=opportunity_score,
            niche_summary=niche_summary,
        )

        llm_pack: dict[str, Any] = _fallback_pack(product_title, current_meta_title, current_meta_description)
        try:
            completion = llm_router.complete(
                prompt,
                system=_SYSTEM_PROMPT,
                max_tokens=2048,
                temperature=0.3,
            )
            raw = completion.text.strip()
            # Strip optional markdown code fences
            if raw.startswith("```"):
                raw = re.sub(r"^```[a-z]*\n?", "", raw)
                raw = re.sub(r"\n?```$", "", raw)
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                llm_pack = {k: parsed.get(k, llm_pack.get(k)) for k in _JSON_KEYS}
        except (LLMError, json.JSONDecodeError, ValueError, KeyError):
            pass

        product_results.append(_build_product_result(product, opp, llm_pack, shop))

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
        "products": product_results,
    }
