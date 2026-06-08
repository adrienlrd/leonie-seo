"""Topic clustering for blog ideas and drafts.

Groups blog content by similar ``target_keyword`` — Jaccard similarity on
normalized tokens, the same mechanism `keyword_normalization.build_clusters`
already uses for product keyword clusters and internal-link suggestions — and
designates a pillar per cluster: the member with the richest outline, the
natural hub for a hub-and-spoke internal-linking structure
(see `app.blog.internal_links.suggest_cluster_links`).
"""

from __future__ import annotations

from typing import Any

_CLUSTER_SIM_THRESHOLD = 0.5


def build_blog_idea_clusters(
    items: list[dict[str, Any]],
    *,
    threshold: float = _CLUSTER_SIM_THRESHOLD,
) -> list[dict[str, Any]]:
    """Group items sharing a similar ``target_keyword`` and flag a pillar.

    Each item needs a unique ``key``, a ``target_keyword``, and an ``outline``.
    Singleton groups (no real overlap) are dropped — nothing to suggest.
    Returns ``[{cluster_id, head_keyword, pillar_key, member_keys}]`` so the
    caller can map clusters back to its own items by ``key``.
    """
    from app.market_analysis.keyword_normalization import build_clusters

    candidates = [
        {**item, "query": str(item.get("target_keyword") or "").strip()}
        for item in items
        if str(item.get("target_keyword") or "").strip() and str(item.get("key") or "").strip()
    ]

    clusters: list[dict[str, Any]] = []
    for cluster in build_clusters(candidates, threshold=threshold):
        members = cluster["members"]
        if len(members) < 2:
            continue
        pillar = max(members, key=lambda m: len(m.get("outline") or []))
        clusters.append(
            {
                "cluster_id": cluster["cluster_id"],
                "head_keyword": cluster["head_keyword"],
                "pillar_key": str(pillar.get("key") or ""),
                "member_keys": [str(m.get("key") or "") for m in members],
            }
        )
    return clusters
