"""Keyword gap analysis and SERP saturation scoring."""

from __future__ import annotations

import re
import unicodedata

from app.niche.models import KeywordGap, ProductCluster

# SERP position thresholds for saturation classification
_POS_LOW_MAX = 10  # top 10 = well ranked, already captured
_POS_MED_MAX = 20  # 11-20 = medium — could improve
# >20 = high saturation / hard to rank — biggest opportunity if impressions are high

_MIN_IMPRESSIONS = 10  # ignore queries with very few impressions (noisy data)


def _normalize_query(text: str) -> set[str]:
    """Return a set of meaningful tokens from a query string."""
    nfkd = unicodedata.normalize("NFKD", text.lower())
    ascii_text = "".join(c for c in nfkd if not unicodedata.combining(c))
    tokens = re.findall(r"[a-z]{3,}", ascii_text)
    return set(tokens)


def _jaccard_similarity(set_a: set[str], set_b: set[str]) -> float:
    """Jaccard index between two token sets."""
    if not set_a or not set_b:
        return 0.0
    inter = len(set_a & set_b)
    union = len(set_a | set_b)
    return inter / union if union else 0.0


def _saturation(position: float) -> str:
    """Classify SERP saturation from GSC average position."""
    if position <= 0:
        return "unknown"
    if position <= _POS_LOW_MAX:
        return "low"  # we rank well — competition is high but we're competitive
    if position <= _POS_MED_MAX:
        return "medium"  # 11-20 — on page 2, improvable
    return "high"  # >20 — page 3+ — hard to rank, likely saturated


def _opportunity_score(
    impressions: int,
    position: float,
    has_cluster: bool,
    *,
    max_impressions: int = 1,
) -> float:
    """Compute a 0-1 opportunity score.

    Higher = more actionable. Factors:
    - High impressions (demand exists)
    - Poor ranking (position > 10 — we're not capturing this traffic)
    - No matching product cluster (content gap, not just an optimization issue)

    Args:
        impressions: GSC impressions count.
        position: Average GSC position (0 = not in GSC).
        has_cluster: Whether a product cluster covers this keyword.
        max_impressions: Normalization factor (max impressions in dataset).
    """
    # Normalised impression score [0, 1]
    imp_score = min(impressions / max_impressions, 1.0) if max_impressions > 0 else 0.0

    # Position penalty: close to 1 when position is high (bad), 0 when position ≤ 10
    if position <= 0:
        pos_score = 0.3  # unknown position — moderate signal
    elif position <= _POS_LOW_MAX:
        pos_score = 0.0  # already ranking well — low opportunity
    else:
        pos_score = min((position - _POS_LOW_MAX) / 40.0, 1.0)  # scales 0→1 from pos 10 to pos 50

    # Content gap bonus: no cluster = product doesn't exist → highest priority
    gap_bonus = 0.3 if not has_cluster else 0.0

    return round(min(0.5 * imp_score + 0.35 * pos_score + gap_bonus, 1.0), 3)


def _find_best_cluster(
    query_tokens: set[str],
    clusters: list[ProductCluster],
    threshold: float = 0.15,
) -> ProductCluster | None:
    """Return the cluster with highest Jaccard overlap, or None if below threshold."""
    best: ProductCluster | None = None
    best_score = 0.0
    for cluster in clusters:
        cluster_tokens = set()
        for kw in cluster.keywords:
            cluster_tokens.update(_normalize_query(kw))
        for title in cluster.product_titles:
            cluster_tokens.update(_normalize_query(title))

        score = _jaccard_similarity(query_tokens, cluster_tokens)
        if score > best_score:
            best_score = score
            best = cluster

    return best if best_score >= threshold else None


def analyze_keyword_gaps(
    gsc_queries: list[dict],
    clusters: list[ProductCluster],
    *,
    min_impressions: int = _MIN_IMPRESSIONS,
) -> list[KeywordGap]:
    """Identify keyword opportunities from GSC data vs product cluster coverage.

    Args:
        gsc_queries: GSC query rows (query, impressions, clicks, position).
        clusters: Product clusters from cluster_products().
        min_impressions: Minimum impressions to consider a query (filters noise).

    Returns:
        List of KeywordGap sorted by opportunity_score descending.
        Queries already ranking in top 10 are excluded (not gaps).
    """
    if not gsc_queries:
        return []

    # Filter noise and already-ranked queries
    candidates = [q for q in gsc_queries if int(q.get("impressions", 0)) >= min_impressions]

    if not candidates:
        return []

    max_impressions = max(int(q.get("impressions", 0)) for q in candidates)

    gaps: list[KeywordGap] = []
    for row in candidates:
        query = str(row.get("query", ""))
        impressions = int(row.get("impressions", 0))
        clicks = int(row.get("clicks", 0))
        position = float(row.get("position", 0))

        # Already in top 3 — not a gap (we're doing great)
        if 0 < position <= 3:
            continue

        query_tokens = _normalize_query(query)
        best_cluster = _find_best_cluster(query_tokens, clusters)
        sat = _saturation(position)

        score = _opportunity_score(
            impressions,
            position,
            has_cluster=best_cluster is not None,
            max_impressions=max_impressions,
        )

        gaps.append(
            KeywordGap(
                query=query,
                impressions=impressions,
                clicks=clicks,
                position=position,
                cluster_name=best_cluster.name if best_cluster else None,
                saturation=sat,
                opportunity_score=score,
            )
        )

    return sorted(gaps, key=lambda g: g.opportunity_score, reverse=True)
