"""Niche Intelligence data models."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ProductCluster:
    """A group of products sharing a common niche theme.

    Attributes:
        name: Human-readable cluster label (e.g. "vêtements chien").
        product_ids: Shopify product GIDs in this cluster.
        product_titles: Display titles (same order as product_ids).
        keywords: Top TF-IDF terms that define this cluster, ranked by score.
        size: Number of products (== len(product_ids)).
    """

    name: str
    product_ids: list[str]
    product_titles: list[str]
    keywords: list[str]
    size: int = field(init=False)

    def __post_init__(self) -> None:
        self.size = len(self.product_ids)


@dataclass
class KeywordGap:
    """A GSC query that represents an under-served content opportunity.

    Attributes:
        query: The search query string.
        impressions: GSC impressions over the analysis window.
        clicks: GSC clicks over the analysis window.
        position: Average GSC position (lower = better ranked).
        cluster_name: Nearest matching product cluster, or None if no cluster covers it.
        saturation: SERP competition level — "low" / "medium" / "high" / "unknown".
        opportunity_score: Composite 0–1 score (higher = more actionable).
    """

    query: str
    impressions: int
    clicks: int
    position: float
    cluster_name: str | None
    saturation: str
    opportunity_score: float


@dataclass
class NicheReport:
    """Full Niche Intelligence output for a shop.

    Attributes:
        shop: Shopify shop domain.
        clusters: Detected product clusters, sorted by size desc.
        keyword_gaps: Keyword opportunities, sorted by opportunity_score desc.
        total_products: Number of products analysed.
        total_queries: Number of GSC queries analysed.
        generated_at: ISO 8601 timestamp.
    """

    shop: str
    clusters: list[ProductCluster]
    keyword_gaps: list[KeywordGap]
    total_products: int
    total_queries: int
    generated_at: str
