"""Niche Intelligence orchestrator — combines clustering, gaps, intents, NER.

Single entry point for the niche-first differentiator: takes Shopify products
and GSC queries, produces a NicheReport that contains every signal we can
build offline (no external HTTP). External signals (Google Suggest, pytrends,
Reddit, CC-Index brand mentions) remain composable via the niche/signals/ and
niche/brand_signals modules — they're not pulled here so the engine stays
deterministic and fast.
"""

from __future__ import annotations

from datetime import UTC, datetime

from app.niche.clustering import cluster_products
from app.niche.gaps import analyze_keyword_gaps
from app.niche.intent import cluster_gsc_queries
from app.niche.models import NicheReport
from app.niche.ner import extract_entities


def _aggregate_entities(products: list[dict]) -> dict[str, dict[str, int]]:
    """Build a frequency map of NER entities across the catalogue.

    Returns a nested dict: category → term → count of products that mention it.
    Empty categories are omitted. Helpful for the merchant UI ("78% of your
    products mention 'France', highlight it more in meta titles").
    """
    summary: dict[str, dict[str, int]] = {}
    for product in products:
        title = str(product.get("title", ""))
        body = str(product.get("body_html", ""))
        text = f"{title} {body}".strip()
        if not text:
            continue
        entities = extract_entities(text)
        for category in ("materials", "certifications", "origins", "targets", "properties"):
            values = getattr(entities, category, []) or []
            if not values:
                continue
            bucket = summary.setdefault(category, {})
            for value in values:
                bucket[value] = bucket.get(value, 0) + 1
    return summary


def run_niche_analysis(
    products: list[dict],
    gsc_queries: list[dict],
    *,
    shop: str,
    min_impressions: int = 10,
) -> NicheReport:
    """Run the full Niche Intelligence pipeline.

    Args:
        products: Shopify product dicts (id, title, product_type, tags, body_html).
        gsc_queries: GSC query rows (query, impressions, clicks, position).
        shop: Shopify shop domain (for the report header).
        min_impressions: Minimum GSC impressions to consider a query in both
                         keyword-gap and intent-clustering stages.

    Returns:
        NicheReport with product clusters, keyword gaps, GSC intent clusters,
        and aggregate NER entity counts. Ready to serialize as JSON.
    """
    clusters = cluster_products(products)
    gaps = analyze_keyword_gaps(gsc_queries, clusters, min_impressions=min_impressions)
    intent_clusters = cluster_gsc_queries(gsc_queries, min_impressions=min_impressions)
    entity_summary = _aggregate_entities(products)

    return NicheReport(
        shop=shop,
        clusters=clusters,
        keyword_gaps=gaps,
        total_products=len(products),
        total_queries=len(gsc_queries),
        generated_at=datetime.now(UTC).isoformat(),
        intent_clusters=intent_clusters,
        entity_summary=entity_summary,
    )
