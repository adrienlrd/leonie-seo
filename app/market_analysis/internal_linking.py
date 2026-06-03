"""Build automatic internal-linking recommendations from product clusters.

The market analysis already groups keywords into semantic clusters (via
`keyword_normalization.build_clusters`). This module turns that signal into
concrete linking suggestions a merchant can paste into product copy / blog
articles: sibling products in the same cluster, collection parents, related
blog articles, and orphan/blog-gap diagnostics.

Purely deterministic — no LLM calls, no cost.
"""

from __future__ import annotations

import re
from typing import Any

from app.market_analysis.keyword_normalization import (
    jaccard_similarity,
    tokenize_normalized,
)

_MAX_SUGGESTIONS_PER_PRODUCT = 5
_CLUSTER_SIM_THRESHOLD = 0.5
_ARTICLE_MATCH_THRESHOLD = 0.5


def build_recommendations(
    *,
    products: list[dict[str, Any]],
    collections: list[dict[str, Any]],
    articles: list[dict[str, Any]],
    pages: list[dict[str, Any]],  # noqa: ARG001 — reserved for institutional pages
    shop: str,  # noqa: ARG001 — reserved for absolute URL building
) -> dict[str, list[dict[str, Any]]]:
    """Return per-product link suggestions keyed by `product_id`.

    Each suggestion is a `{target_url, target_title, anchors, reason, confidence}`
    dict. Suggestion reasons:
    - `sibling_product`: another product in the same primary-keyword cluster.
    - `collection_parent`: a collection the product belongs to.
    - `informational_support`: a blog article matching the cluster topic.
    """
    primary_by_product: dict[str, str] = {}
    primary_intent_by_product: dict[str, str] = {}
    for product in products:
        primary = _primary_keyword(product)
        if primary:
            primary_by_product[product["product_id"]] = str(primary.get("query") or "")
            primary_intent_by_product[product["product_id"]] = str(primary.get("intent_type") or "")

    product_index = {p["product_id"]: p for p in products}
    product_tokens: dict[str, set[str]] = {
        pid: tokenize_normalized(query) for pid, query in primary_by_product.items()
    }

    collections_by_product: dict[str, list[dict[str, Any]]] = {}
    for col in collections:
        for pid in _collection_product_ids(col):
            collections_by_product.setdefault(pid, []).append(col)

    recommendations: dict[str, list[dict[str, Any]]] = {p["product_id"]: [] for p in products}

    for product in products:
        pid = product["product_id"]
        suggestions: list[dict[str, Any]] = []
        my_tokens = product_tokens.get(pid, set())

        if my_tokens:
            for other in products:
                if other["product_id"] == pid:
                    continue
                other_tokens = product_tokens.get(other["product_id"], set())
                if not other_tokens:
                    continue
                sim = jaccard_similarity(my_tokens, other_tokens)
                if sim >= _CLUSTER_SIM_THRESHOLD:
                    suggestions.append(
                        {
                            "target_url": str(other.get("product_url") or ""),
                            "target_title": str(other.get("product_title") or ""),
                            "anchors": _build_anchors(
                                primary_by_product.get(other["product_id"], ""),
                                str(other.get("product_title") or ""),
                            ),
                            "reason": "sibling_product",
                            "confidence": "high" if sim >= 0.75 else "medium",
                            "_similarity": sim,
                        }
                    )

        for col in collections_by_product.get(pid, []):
            handle = str(col.get("handle") or "")
            title = str(col.get("title") or "")
            if not handle:
                continue
            suggestions.append(
                {
                    "target_url": f"/collections/{handle}",
                    "target_title": title,
                    "anchors": _build_anchors(primary_by_product.get(pid, ""), title),
                    "reason": "collection_parent",
                    "confidence": "high",
                    "_similarity": 1.0,
                }
            )

        for article in articles:
            article_keywords = article.get("keywords") or []
            best_sim = 0.0
            for kw in article_keywords:
                sim = jaccard_similarity(my_tokens, tokenize_normalized(str(kw)))
                if sim > best_sim:
                    best_sim = sim
            if best_sim >= _ARTICLE_MATCH_THRESHOLD:
                handle = str(article.get("handle") or "")
                suggestions.append(
                    {
                        "target_url": f"/blogs/blog/{handle}",
                        "target_title": str(article.get("title") or ""),
                        "anchors": _build_anchors(
                            primary_by_product.get(pid, ""),
                            str(article.get("title") or ""),
                        ),
                        "reason": "informational_support",
                        "confidence": "medium",
                        "_similarity": best_sim,
                    }
                )

        suggestions.sort(key=lambda s: s["_similarity"], reverse=True)
        for s in suggestions:
            s.pop("_similarity", None)
        recommendations[pid] = suggestions[:_MAX_SUGGESTIONS_PER_PRODUCT]

        # Quiet unused-variable warning when product_index is not consulted.
        _ = product_index

    return recommendations


def detect_orphan_products(
    *,
    products: list[dict[str, Any]],
    collections: list[dict[str, Any]],
    articles: list[dict[str, Any]],
) -> list[str]:
    """Return product_ids that belong to no collection and no article links to them."""
    if not _has_link_coverage_data(collections=collections, articles=articles):
        return []

    in_collection: set[str] = set()
    for col in collections:
        for pid in _collection_product_ids(col):
            in_collection.add(str(pid))

    mentioned_in_article: set[str] = set()
    for article in articles:
        for handle in _article_linked_product_handles(article):
            mentioned_in_article.add(str(handle))

    orphans: list[str] = []
    for product in products:
        pid = str(product.get("product_id") or "")
        handle = str(product.get("product_handle") or "")
        if pid in in_collection:
            continue
        if handle and handle in mentioned_in_article:
            continue
        orphans.append(pid)
    return orphans


def detect_blog_gaps(
    *,
    products: list[dict[str, Any]],
    articles: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Return informational-intent keyword clusters not yet covered by a blog article."""
    article_tokens = [
        tokenize_normalized(" ".join(str(k) for k in (a.get("keywords") or []))) for a in articles
    ]
    gaps: list[dict[str, Any]] = []
    seen_clusters: set[frozenset[str]] = set()
    for product in products:
        primary = _primary_keyword(product)
        if not primary:
            continue
        intent = str(primary.get("intent_type") or "")
        if intent != "informational":
            continue
        query = str(primary.get("query") or "")
        tokens = tokenize_normalized(query)
        if not tokens:
            continue
        key = frozenset(tokens)
        if key in seen_clusters:
            continue
        seen_clusters.add(key)
        covered = any(
            jaccard_similarity(tokens, at) >= _ARTICLE_MATCH_THRESHOLD for at in article_tokens
        )
        if covered:
            continue
        gaps.append(
            {
                "cluster_head": query,
                "suggested_title": query.capitalize(),
                "reason": "informational_intent_uncovered",
            }
        )
    return gaps


def _primary_keyword(product: dict[str, Any]) -> dict[str, Any] | None:
    for kw in product.get("seo_keywords") or []:
        if isinstance(kw, dict) and kw.get("target_role") == "primary":
            return kw
    return None


def _edge_nodes(container: Any) -> list[dict[str, Any]]:
    if isinstance(container, dict) and isinstance(container.get("edges"), list):
        return [edge.get("node", {}) for edge in container["edges"] if isinstance(edge, dict)]
    if isinstance(container, list):
        return [item for item in container if isinstance(item, dict)]
    return []


def _collection_product_ids(collection: dict[str, Any]) -> list[str]:
    explicit = collection.get("product_ids") or collection.get("productIds") or []
    ids = [str(pid) for pid in explicit if str(pid)]
    for product in _edge_nodes(collection.get("products")):
        pid = product.get("id") or product.get("product_id")
        if pid:
            ids.append(str(pid))
    return list(dict.fromkeys(ids))


def _article_linked_product_handles(article: dict[str, Any]) -> list[str]:
    explicit = article.get("linked_product_handles") or []
    handles = [str(handle) for handle in explicit if str(handle)]
    body = " ".join(
        str(article.get(key) or "")
        for key in ("body_html", "bodyHtml", "content", "contentHtml", "html")
    )
    handles.extend(re.findall(r"/products/([a-zA-Z0-9_-]+)", body))
    return list(dict.fromkeys(handles))


def _has_link_coverage_data(
    *,
    collections: list[dict[str, Any]],
    articles: list[dict[str, Any]],
) -> bool:
    return any(_collection_product_ids(col) for col in collections) or any(
        _article_linked_product_handles(article) for article in articles
    )


def _build_anchors(head_keyword: str, target_title: str) -> list[str]:
    anchors: list[str] = []
    if head_keyword:
        anchors.append(head_keyword)
    if target_title and target_title not in anchors:
        anchors.append(target_title)
    return anchors
