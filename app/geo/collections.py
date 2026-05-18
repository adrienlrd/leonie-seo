"""Read-only GEO collection suggestions for conversational search intents."""

from __future__ import annotations

import csv
import io
import re
import unicodedata
from collections import Counter, defaultdict
from typing import Any

from app.niche.clustering import cluster_products

_COMMERCE_INTENT_TERMS = {
    "best": "commercial",
    "meilleur": "commercial",
    "meilleure": "commercial",
    "choisir": "commercial",
    "comparatif": "commercial",
    "guide": "informational",
    "comment": "informational",
    "quelle": "informational",
    "quelles": "informational",
    "quel": "informational",
    "achat": "transactional",
    "acheter": "transactional",
    "prix": "transactional",
}

_STOPWORDS = {
    "avec",
    "dans",
    "des",
    "for",
    "les",
    "pour",
    "the",
    "une",
    "and",
    "aux",
    "qui",
    "quoi",
    "comment",
    "quelle",
    "quelles",
    "quel",
}


def _normalize(text: str) -> str:
    nfkd = unicodedata.normalize("NFKD", text.lower())
    ascii_text = "".join(char for char in nfkd if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9\s-]", " ", ascii_text)


def _tokens(text: str) -> set[str]:
    return {token for token in _normalize(text).split() if len(token) >= 3 and token not in _STOPWORDS}


def _slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", _normalize(text)).strip("-")
    return slug or "collection-geo"


def _product_text(product: dict[str, Any]) -> str:
    tags = product.get("tags")
    tag_text = " ".join(tags) if isinstance(tags, list) else str(tags or "")
    return " ".join(
        str(part or "")
        for part in (
            product.get("title"),
            product.get("product_type"),
            tag_text,
            product.get("description"),
            product.get("body_html"),
        )
    )


def _existing_collection_handles(collections: list[dict[str, Any]]) -> set[str]:
    return {str(collection.get("handle") or "").strip() for collection in collections if collection.get("handle")}


def _detect_intent(queries: list[str]) -> str:
    counts: Counter[str] = Counter()
    for query in queries:
        for token in _tokens(query):
            if token in _COMMERCE_INTENT_TERMS:
                counts[_COMMERCE_INTENT_TERMS[token]] += 1
    if not counts:
        return "commercial"
    return counts.most_common(1)[0][0]


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


def parse_gsc_query_page_csv(csv_text: str) -> list[dict[str, Any]]:
    """Parse GSC query-page exports into normalized rows."""
    rows: list[dict[str, Any]] = []
    reader = csv.DictReader(io.StringIO(csv_text))
    for row in reader:
        query = str(row.get("query") or "").strip()
        page = str(row.get("page") or row.get("url") or "").strip()
        if not query:
            continue
        rows.append(
            {
                "query": query,
                "page": page,
                "clicks": _safe_int(row.get("clicks")),
                "impressions": _safe_int(row.get("impressions")),
                "ctr": _safe_float(row.get("ctr")),
                "position": _safe_float(row.get("position")),
            }
        )
    return rows


def _fallback_query_rows(products: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for product in products:
        title = str(product.get("title") or "").strip()
        if not title:
            continue
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


def _queries_for_cluster(cluster_keywords: list[str], query_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    keyword_tokens = set(cluster_keywords)
    scored = []
    for row in query_rows:
        query_tokens = _tokens(str(row.get("query") or ""))
        overlap = len(keyword_tokens & query_tokens)
        if overlap:
            scored.append((overlap, _safe_int(row.get("impressions")), row))
    scored.sort(key=lambda item: (-item[0], -item[1], str(item[2].get("query") or "")))
    return [row for _, _, row in scored[:5]]


def _collection_title(cluster_name: str, queries: list[str]) -> str:
    if queries:
        best_query = queries[0].strip()
        if best_query:
            return best_query[:1].upper() + best_query[1:]
    return f"Guide {cluster_name}".strip().title()


def _preview(title: str, products: list[dict[str, Any]], intent: str) -> dict[str, str | list[str]]:
    product_titles = [str(product.get("title") or "") for product in products if product.get("title")]
    h1 = title
    seo_title = f"{title} | Sélection boutique"
    meta_description = (
        f"Découvrez {len(product_titles)} produits sélectionnés pour {title.lower()} avec des critères clairs, "
        "des informations vérifiées et une navigation plus utile."
    )
    description = (
        f"Cette collection regroupe les produits les plus pertinents pour l'intention {intent}. "
        "Elle doit rester validée par un marchand avant publication."
    )
    questions = [
        f"Comment choisir parmi {title.lower()} ?",
        f"Quels produits comparer pour {title.lower()} ?",
        "Quels critères vérifier avant achat ?",
    ]
    return {
        "h1": h1,
        "seo_title": seo_title[:70],
        "meta_description": meta_description[:155],
        "description": description,
        "faq_questions": questions,
    }


def build_collection_suggestions(
    products: list[dict[str, Any]],
    collections: list[dict[str, Any]],
    query_rows: list[dict[str, Any]] | None = None,
    *,
    top: int = 10,
    min_products: int = 2,
) -> dict[str, Any]:
    """Suggest Shopify collections for AI-search-friendly conversational intents."""
    catalog_products = [product for product in products if product.get("title")]
    gsc_query_rows = query_rows or _fallback_query_rows(catalog_products)
    clusters = cluster_products(catalog_products)
    products_by_id = {str(product.get("id", "")): product for product in catalog_products}
    existing_handles = _existing_collection_handles(collections)

    suggestions = []
    for cluster in clusters:
        cluster_products_list = [
            products_by_id[product_id]
            for product_id in cluster.product_ids
            if product_id in products_by_id
        ]
        if len(cluster_products_list) < min_products:
            continue

        queries = _queries_for_cluster(cluster.keywords + [cluster.name], gsc_query_rows)
        source_queries = [str(row.get("query") or "") for row in queries]
        title = _collection_title(cluster.name, source_queries)
        handle = _slugify(title)
        impressions = sum(_safe_int(row.get("impressions")) for row in queries)
        clicks = sum(_safe_int(row.get("clicks")) for row in queries)
        intent = _detect_intent(source_queries)
        warnings = []
        if handle in existing_handles:
            warnings.append("A collection with this handle already exists.")
        if len(cluster_products_list) < 3:
            warnings.append("Thin collection candidate: review product depth before publishing.")
        if not queries:
            warnings.append("No matching query-page GSC rows found; opportunity uses catalog fallback only.")

        opportunity_score = round(
            min(100, 35 + min(40, impressions / 25) + min(15, len(cluster_products_list) * 3) - len(warnings) * 8)
        )

        suggestions.append(
            {
                "suggested_title": title,
                "handle": handle,
                "intent": intent,
                "cluster_name": cluster.name,
                "keywords": cluster.keywords,
                "source_queries": source_queries,
                "product_count": len(cluster_products_list),
                "products": [
                    {
                        "id": product.get("id", ""),
                        "title": product.get("title", ""),
                        "handle": product.get("handle", ""),
                    }
                    for product in cluster_products_list
                ],
                "estimated_impressions": impressions,
                "estimated_clicks": clicks,
                "opportunity_score": max(0, opportunity_score),
                "preview": _preview(title, cluster_products_list, intent),
                "dry_run": True,
                "warnings": warnings,
            }
        )

    if not suggestions and catalog_products:
        grouped: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
        for product in catalog_products:
            key = next(iter(_tokens(_product_text(product))), "catalogue")
            grouped[key].append(product)
        for key, grouped_products in grouped.items():
            if len(grouped_products) >= min_products:
                title = f"Guide {key}".title()
                suggestions.append(
                    {
                        "suggested_title": title,
                        "handle": _slugify(title),
                        "intent": "commercial",
                        "cluster_name": key,
                        "keywords": [key],
                        "source_queries": [],
                        "product_count": len(grouped_products),
                        "products": [
                            {
                                "id": product.get("id", ""),
                                "title": product.get("title", ""),
                                "handle": product.get("handle", ""),
                            }
                            for product in grouped_products
                        ],
                        "estimated_impressions": 0,
                        "estimated_clicks": 0,
                        "opportunity_score": 25,
                        "preview": _preview(title, grouped_products, "commercial"),
                        "dry_run": True,
                        "warnings": ["Catalog fallback only; validate intent before publishing."],
                    }
                )

    suggestions.sort(
        key=lambda item: (
            -int(item["opportunity_score"]),
            -int(item["estimated_impressions"]),
            str(item["suggested_title"]),
        )
    )
    limited = suggestions[:top]
    return {
        "total": len(suggestions),
        "summary": {
            "suggested_collections": len(limited),
            "total_estimated_impressions": sum(item["estimated_impressions"] for item in limited),
            "gsc_query_rows": len(query_rows or []),
            "dry_run": True,
            "note": "Collection suggestions are previews only; no Shopify collection is created.",
        },
        "suggestions": limited,
    }
