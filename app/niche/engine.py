"""Niche Intelligence orchestrator — combines clustering and gap analysis."""

from __future__ import annotations

from datetime import UTC, datetime

from app.niche.clustering import cluster_products
from app.niche.gaps import analyze_keyword_gaps
from app.niche.models import NicheReport


def run_niche_analysis(
    products: list[dict],
    gsc_queries: list[dict],
    *,
    shop: str,
    min_impressions: int = 10,
) -> NicheReport:
    """Run the full Niche Intelligence pipeline.

    Args:
        products: Shopify product dicts (id, title, product_type, tags).
        gsc_queries: GSC query rows (query, impressions, clicks, position).
        shop: Shopify shop domain (for the report header).
        min_impressions: Minimum GSC impressions to consider a query.

    Returns:
        NicheReport with clusters and keyword gaps, ready to serialize.
    """
    clusters = cluster_products(products)
    gaps = analyze_keyword_gaps(gsc_queries, clusters, min_impressions=min_impressions)

    return NicheReport(
        shop=shop,
        clusters=clusters,
        keyword_gaps=gaps,
        total_products=len(products),
        total_queries=len(gsc_queries),
        generated_at=datetime.now(UTC).isoformat(),
    )
