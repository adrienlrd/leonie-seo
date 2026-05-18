"""Light AI answer competitor monitor for conversational GEO queries."""

from __future__ import annotations

import re
from typing import Any

from app.geo.collections import parse_gsc_query_page_csv
from app.geo.readiness import score_product_readiness

_QUESTION_HINTS = {
    "comment",
    "choisir",
    "meilleur",
    "meilleure",
    "guide",
    "comparatif",
    "quelle",
    "quel",
    "quelles",
    "prix",
    "best",
    "how",
    "which",
}


def _tokens(text: str) -> set[str]:
    return {token for token in re.sub(r"[^a-z0-9\s]", " ", text.lower()).split() if len(token) >= 3}


def _safe_int(value: Any) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


def _safe_float(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _domain_list(value: str | list[str] | None) -> list[str]:
    if isinstance(value, str):
        raw = value.split(",")
    else:
        raw = value or []
    domains = []
    seen = set()
    for item in raw:
        domain = str(item).strip().lower().replace("https://", "").replace("http://", "").strip("/")
        if not domain or domain in seen:
            continue
        seen.add(domain)
        domains.append(domain)
    return domains


def _fallback_query_rows(products: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for product in products:
        title = str(product.get("title") or "").strip()
        if title:
            rows.append(
                {
                    "query": f"meilleur {title}",
                    "page": f"/products/{product.get('handle', '')}",
                    "clicks": 0,
                    "impressions": 0,
                    "ctr": 0.0,
                    "position": 0.0,
                }
            )
    return rows


def _query_intent(query: str) -> str:
    tokens = _tokens(query)
    if tokens & {"prix", "acheter"}:
        return "transactional"
    if tokens & {"comparatif", "meilleur", "meilleure", "best"}:
        return "commercial"
    if tokens & {"comment", "guide", "how", "which", "quelle", "quel"}:
        return "informational"
    return "commercial"


def _priority_queries(query_rows: list[dict[str, Any]], *, top: int) -> list[dict[str, Any]]:
    rows = []
    for row in query_rows:
        query = str(row.get("query") or "").strip()
        if not query:
            continue
        tokens = _tokens(query)
        conversational = bool(tokens & _QUESTION_HINTS) or len(tokens) >= 3
        if not conversational:
            continue
        rows.append(
            {
                "query": query,
                "page": str(row.get("page") or ""),
                "clicks": _safe_int(row.get("clicks")),
                "impressions": _safe_int(row.get("impressions")),
                "position": round(_safe_float(row.get("position")), 2),
                "intent": _query_intent(query),
            }
        )
    rows.sort(key=lambda item: (-item["impressions"], item["position"] or 99, item["query"]))
    return rows[:top]


def _matching_products(query: str, products: list[dict[str, Any]], *, limit: int = 3) -> list[dict[str, Any]]:
    query_tokens = _tokens(query)
    matches = []
    for product in products:
        title = str(product.get("title") or "")
        text = " ".join(
            str(part or "")
            for part in (
                title,
                product.get("product_type"),
                product.get("description"),
                product.get("descriptionHtml"),
            )
        )
        overlap = len(query_tokens & _tokens(text))
        if overlap <= 0:
            continue
        readiness = score_product_readiness(product)
        matches.append((overlap, readiness["readiness_score"], product))
    matches.sort(key=lambda item: (-item[0], -item[1], str(item[2].get("title") or "")))
    return [
        {
            "product_id": product.get("id", ""),
            "title": product.get("title", ""),
            "handle": product.get("handle", ""),
            "readiness_score": readiness,
        }
        for _, readiness, product in matches[:limit]
    ]


def _competitor_rows(domains: list[str], query: str) -> list[dict[str, Any]]:
    tokens = _tokens(query)
    rows = []
    for domain in domains:
        strengths = ["Manual visibility candidate for this query."]
        checks = [
            "Check whether the competitor has a clear FAQ or answer block for the query.",
            "Check product facts: material, origin, price, reviews, warranty and shipping proof.",
            "Check structured data and internal links without copying wording.",
        ]
        if tokens & {"prix", "acheter"}:
            strengths.append("Likely needs price, availability and shipping proof comparison.")
        if tokens & {"meilleur", "comparatif", "best"}:
            strengths.append("Likely needs comparison angle, reviews and proof points.")
        rows.append(
            {
                "domain": domain,
                "visible_url": f"https://{domain}/search?q={query.replace(' ', '+')}",
                "visibility_source": "manual_or_serp_import",
                "likely_strengths": strengths,
                "review_checklist": checks,
            }
        )
    return rows


def _recommended_action(query: dict[str, Any], products: list[dict[str, Any]], competitor_count: int) -> dict[str, str]:
    if not products:
        return {
            "action_type": "create_collection_or_guide",
            "label": "Créer une collection ou un guide dédié",
            "reason": "No matching product page is strong enough for this conversational query.",
        }
    lowest_score = min(int(product["readiness_score"]) for product in products)
    if lowest_score < 50:
        return {
            "action_type": "enrich_product_facts",
            "label": "Enrichir les faits produit",
            "reason": "A matching product exists, but readiness is weak compared with competitor candidates.",
        }
    if query["intent"] in {"informational", "commercial"} and competitor_count:
        return {
            "action_type": "add_answer_blocks",
            "label": "Ajouter FAQ et blocs de réponse",
            "reason": "Competitor candidates should be reviewed for answer coverage; respond with confirmed facts only.",
        }
    return {
        "action_type": "strengthen_internal_links",
        "label": "Renforcer le maillage interne",
        "reason": "A relevant page exists; improve discoverability from collection, product and guide pages.",
    }


def build_competitor_monitor(
    products: list[dict[str, Any]],
    query_rows: list[dict[str, Any]] | None = None,
    *,
    competitors: str | list[str] | None = None,
    top: int = 10,
) -> dict[str, Any]:
    """Build a light competitor monitor for priority conversational queries."""
    catalog_products = [product for product in products if product.get("title")]
    rows = query_rows or _fallback_query_rows(catalog_products)
    domains = _domain_list(competitors)
    queries = _priority_queries(rows, top=top)
    monitored = []
    for query in queries:
        matching = _matching_products(query["query"], catalog_products)
        competitor_candidates = _competitor_rows(domains, query["query"])
        monitored.append(
            {
                **query,
                "matching_products": matching,
                "competitors": competitor_candidates,
                "recommended_action": _recommended_action(query, matching, len(competitor_candidates)),
                "copy_policy": "Do not copy competitor wording; use the checklist to identify gaps and answer with verified merchant facts.",
            }
        )

    return {
        "total": len(monitored),
        "summary": {
            "queries_monitored": len(monitored),
            "competitor_domains": len(domains),
            "gsc_query_rows": len(query_rows or []),
            "dry_run": True,
            "note": "V1 uses GSC/manual query data and provided competitor domains; it does not scrape live AI answers or copy competitor content.",
        },
        "competitor_domains": domains,
        "queries": monitored,
    }


def parse_manual_competitor_csv(csv_text: str) -> list[dict[str, Any]]:
    """Parse a simple manual SERP/AI-answer CSV export.

    Expected columns: query, domain, visible_url.
    """
    rows = parse_gsc_query_page_csv(csv_text)
    parsed = []
    for row in rows:
        parsed.append(
            {
                "query": row["query"],
                "domain": "",
                "visible_url": row.get("page", ""),
                "impressions": row.get("impressions", 0),
                "clicks": row.get("clicks", 0),
                "position": row.get("position", 0.0),
            }
        )
    return parsed
