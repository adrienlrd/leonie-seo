"""Market analysis engine — per-product SEO/GEO opportunity + content pack generation."""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from app.llm import LLMError, get_router
from app.snapshot.scope import filter_products_by_scope

logger = logging.getLogger(__name__)

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


def _build_prompt(
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
        "product_summary": llm_pack.get("product_summary", ""),
        "target_customer": llm_pack.get("target_customer", ""),
        "buying_intents": llm_pack.get("buying_intents", []),
        "seo_keywords": llm_pack.get("seo_keywords", []),
        "geo_questions": llm_pack.get("geo_questions", []),
        "trend_signals": opportunity.get("trend_signals", []),
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
    progress_callback: Callable[[int, int, list[dict[str, Any]]], None] | None = None,
) -> dict[str, Any]:
    """Run full SEO/GEO market analysis for active products.

    Sources used: Shopify snapshot, GSC queries, GA4 page metrics (if connected),
    Google Trends (one global call), stock/inventory data from variants.
    Read-only: no Shopify writes.

    Args:
        max_products: Cap on products to analyse. 0 = no cap (all active products).
        progress_callback: Called after each product with (done, total, partial_results).
    """
    active_products = filter_products_by_scope(products, "active")

    opportunities = _score_active_products(active_products, gsc_query_rows, ga4_page_rows)

    if max_products and max_products > 0:
        opportunities = opportunities[:max_products]

    total = len(opportunities)

    product_by_id: dict[str, dict[str, Any]] = {
        str(p.get("id", "")): p for p in active_products
    }

    # Global sources tracker
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

    product_results: list[dict[str, Any]] = []

    for idx, opp in enumerate(opportunities):
        product_id = opp.get("product_id", "")
        product = product_by_id.get(product_id)
        if not product:
            continue

        try:
            product_title = product.get("title", "")
            # Merchant-validated SEO label (bonus context, not a title replacement)
            merchant_label = (product_labels or {}).get(product_id, "")
            handle = product.get("handle", "")
            body_html = product.get("body_html") or product.get("description") or ""
            description = _strip_html(body_html)

            raw_seo = product.get("seo")
            seo: dict[str, Any] = raw_seo if isinstance(raw_seo, dict) else {}
            current_meta_title = seo.get("title") or product_title
            current_meta_description = seo.get("description") or ""

            raw_collections = _coerce_list(product.get("collections"))
            collections = [
                c.get("title", "") if isinstance(c, dict) else str(c)
                for c in raw_collections
                if c
            ]

            raw_tags = product.get("tags") or ""
            tags = ", ".join(raw_tags) if isinstance(raw_tags, list) else str(raw_tags)

            variants = _coerce_list(product.get("variants"))
            first_variant = variants[0] if variants else {}
            price = str(first_variant.get("price", "")) if isinstance(first_variant, dict) else ""
            nb_variants = len(variants)

            stock_qty, stock_status = _read_stock(product)
            ga4_metrics: dict[str, Any] = opp.get("ga4_metrics", {})
            trend_top, trend_rising = _match_trends(product_title, trend_signals)

            matched_queries: list[str] = opp.get("matched_queries", [])
            opportunity_score: int = opp.get("opportunity_score", 0)
        except Exception:
            product_title = product.get("title", "") if isinstance(product, dict) else ""
            handle = product.get("handle", "") if isinstance(product, dict) else ""
            description = current_meta_title = product_title
            current_meta_description = collections = tags = price = ""
            nb_variants = 0
            stock_qty, stock_status = None, "inconnu"
            ga4_metrics, trend_top, trend_rising = {}, [], []
            matched_queries = []
            opportunity_score = opp.get("opportunity_score", 0) if isinstance(opp, dict) else 0

        prompt = _build_prompt(
            product_title=product_title,
            handle=handle,
            description=description,
            collections=collections,
            tags=tags,
            price=price,
            nb_variants=nb_variants,
            current_meta_title=current_meta_title,
            current_meta_description=current_meta_description,
            matched_queries=matched_queries,
            opportunity_score=opportunity_score,
            niche_summary=niche_summary,
            ga4_metrics=ga4_metrics,
            trend_top=trend_top,
            trend_rising=trend_rising,
            stock_qty=stock_qty,
            stock_status=stock_status,
            merchant_label=merchant_label,
        )

        llm_pack: dict[str, Any] = _fallback_pack(product_title, current_meta_title, current_meta_description)
        if llm_router is not None:
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
                    llm_pack = {k: parsed.get(k, llm_pack.get(k)) for k in _JSON_KEYS}
            except json.JSONDecodeError as exc:
                logger.warning(
                    "JSON parse failed for %r — likely truncated (%d chars): %s | start: %s",
                    product_title, len(raw), exc, raw[:200],
                )
            except LLMError as exc:
                logger.warning("LLM call failed for %r: %s", product_title, exc)
            except Exception as exc:
                logger.warning("Unexpected error for %r: %s", product_title, exc)

        product_results.append(_build_product_result(product, opp, llm_pack, shop))

        if progress_callback is not None:
            try:
                progress_callback(idx + 1, total, list(product_results))
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
        "products": product_results,
    }
