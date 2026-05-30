"""Cross-product keyword cannibalization detection.

Two products in the same catalog targeting the same primary keyword (or two
keywords in the same semantic cluster) compete with each other in search.
This module surfaces those conflicts as `cannibalization_alerts` at job level
and provides per-product reorientation hints used by Pass 2 to redirect the
losing product toward a longer-tail variant.
"""

from __future__ import annotations

from typing import Any

from app.market_analysis.keyword_normalization import tokenize_normalized


def detect_alerts(products: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return one alert per shared primary keyword cluster.

    Args:
        products: list of per-product analysis results, each with `product_id`,
            `product_title`, `product_url`, `seo_keywords` (with `target_role`
            and optional `gsc_impressions`), `opportunity_score`.

    Returns:
        A list of `{cluster_head, cluster_key, product_ids, products,
        winner_suggested, action}` entries. Empty when no cannibalization
        exists. Only `primary` target roles contribute to detection.
    """
    if not products:
        return []

    by_cluster: dict[frozenset[str], list[dict[str, Any]]] = {}
    cluster_label: dict[frozenset[str], str] = {}

    for product in products:
        primary_kw = _find_primary_keyword(product)
        if not primary_kw:
            continue
        query = str(primary_kw.get("query") or "").strip()
        if not query:
            continue
        cluster_key = frozenset(tokenize_normalized(query))
        if not cluster_key:
            continue
        by_cluster.setdefault(cluster_key, []).append(
            {
                "product": product,
                "primary": primary_kw,
                "query": query,
            }
        )
        cluster_label.setdefault(cluster_key, query)

    alerts: list[dict[str, Any]] = []
    for cluster_key, entries in by_cluster.items():
        if len(entries) < 2:
            continue
        winner = max(entries, key=_winner_score)
        product_ids = [str(e["product"].get("product_id") or "") for e in entries]
        alerts.append(
            {
                "cluster_head": cluster_label[cluster_key],
                "cluster_key": sorted(cluster_key),
                "product_ids": product_ids,
                "products": [
                    {
                        "product_id": str(e["product"].get("product_id") or ""),
                        "product_title": str(e["product"].get("product_title") or ""),
                        "product_url": str(e["product"].get("product_url") or ""),
                        "primary_keyword": str(e["query"]),
                        "gsc_impressions": int(e["primary"].get("gsc_impressions") or 0),
                        "opportunity_score": int(e["product"].get("opportunity_score") or 0),
                        "all_keywords": list(e["product"].get("seo_keywords") or []),
                    }
                    for e in entries
                ],
                "winner_suggested": str(winner["product"].get("product_id") or ""),
                "action": "reorient_secondary",
            }
        )
    return alerts


def get_reorientation_hint(
    alerts: list[dict[str, Any]], *, product_id: str
) -> dict[str, Any] | None:
    """Return a reorientation hint for a product that lost a cannibalization conflict.

    Used by Pass 2 to redirect the loser product's content toward a more
    specific long-tail keyword from its own list rather than re-targeting the
    head cluster keyword.
    """
    if not product_id:
        return None
    for alert in alerts:
        if alert.get("winner_suggested") == product_id:
            return None
        if product_id not in (alert.get("product_ids") or []):
            continue
        loser_entry = next(
            (p for p in (alert.get("products") or []) if p.get("product_id") == product_id),
            None,
        )
        pivots: list[str] = []
        if loser_entry is not None:
            head_tokens = set(tokenize_normalized(str(alert.get("cluster_head") or "")))
            cluster_tokens = set(alert.get("cluster_key") or [])
            primary_query = str(loser_entry.get("primary_keyword") or "")
            for kw in loser_entry.get("all_keywords") or []:
                candidate = str(kw.get("query") or "")
                if not candidate or candidate == primary_query:
                    continue
                tokens = tokenize_normalized(candidate)
                if cluster_tokens.issubset(tokens) and tokens - head_tokens:
                    pivots.append(candidate)
        return {
            "cluster_head": alert.get("cluster_head"),
            "winner_id": alert.get("winner_suggested"),
            "target_role": "secondary",
            "pivot_suggestions": pivots,
        }
    return None


def _find_primary_keyword(product: dict[str, Any]) -> dict[str, Any] | None:
    keywords = product.get("seo_keywords") or []
    for kw in keywords:
        if isinstance(kw, dict) and kw.get("target_role") == "primary":
            return kw
    return None


def _winner_score(entry: dict[str, Any]) -> tuple[int, int]:
    primary = entry["primary"]
    product = entry["product"]
    gsc = int(primary.get("gsc_impressions") or 0)
    opp = int(product.get("opportunity_score") or 0)
    # GSC dominates; opportunity_score breaks ties.
    return (gsc, opp)
