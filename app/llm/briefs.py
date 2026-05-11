"""LLM-powered brief generation for blog articles and collection pages."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field

from app.llm.prompts import load_prompt
from app.llm.provider import LLMError
from app.llm.router import LLMRouter
from app.niche.intent import _classify_intent


@dataclass
class BlogBriefResult:
    """LLM-generated brief for a blog article targeting a keyword gap.

    Attributes:
        query: Target GSC query / keyword gap.
        intent: Detected intent (informational / commercial / transactional / navigational).
        cluster_name: Nearest product cluster, or None if no match.
        impressions: GSC impressions for this query.
        current_position: Average GSC position.
        brief: Raw LLM output (structured markdown brief).
        provider: LLM provider that generated this result.
        error: Error message if generation failed, None on success.
    """

    query: str
    intent: str
    cluster_name: str | None
    impressions: int
    current_position: float
    brief: str = ""
    provider: str = ""
    error: str | None = None

    @property
    def success(self) -> bool:
        return self.error is None and bool(self.brief)


@dataclass
class CollectionBriefResult:
    """LLM-generated brief for a Shopify collection page.

    Attributes:
        cluster_name: Product cluster name (maps to a Shopify collection).
        product_count: Number of products in the cluster.
        top_keywords: Dominant TF-IDF terms used as input.
        brief: Raw LLM output (structured markdown brief).
        provider: LLM provider that generated this result.
        error: Error message if generation failed, None on success.
    """

    cluster_name: str
    product_count: int
    top_keywords: list[str] = field(default_factory=list)
    brief: str = ""
    provider: str = ""
    error: str | None = None

    @property
    def success(self) -> bool:
        return self.error is None and bool(self.brief)


def generate_blog_brief(gap: dict, router: LLMRouter) -> BlogBriefResult:
    """Generate a blog article brief for a single keyword gap.

    Args:
        gap: Keyword gap dict — expected keys: query, impressions, clicks,
             position, cluster_name, saturation, opportunity_score.
        router: Configured LLMRouter instance.

    Returns:
        BlogBriefResult with brief text on success, error message on failure.
    """
    query = str(gap.get("query", ""))
    impressions = int(gap.get("impressions", 0))
    position = float(gap.get("position", 0.0))
    cluster_name = gap.get("cluster_name")
    intent = _classify_intent(query).value

    result = BlogBriefResult(
        query=query,
        intent=intent,
        cluster_name=cluster_name,
        impressions=impressions,
        current_position=position,
    )

    try:
        tmpl = load_prompt("blog_brief")
        prompt = tmpl.render_user(
            target_query=query,
            search_intent=intent,
            cluster=cluster_name or "",
            competitor_titles=[],
            search_volume=impressions,
            current_position=round(position, 1) if position else "non classé",
        )
        completion = router.complete(
            prompt,
            system=tmpl.render_system(),
            max_tokens=tmpl.max_tokens,
            temperature=tmpl.temperature,
        )
        result.brief = completion.text
        result.provider = completion.provider
    except LLMError as exc:
        result.error = str(exc)

    return result


def generate_blog_briefs(
    gaps: list[dict],
    router: LLMRouter,
    *,
    max_workers: int = 3,
) -> list[BlogBriefResult]:
    """Generate blog briefs for multiple keyword gaps concurrently.

    Args:
        gaps: List of keyword gap dicts (from GET /niche/gaps).
        router: Configured LLMRouter instance.
        max_workers: Thread pool size (default 3 — conservative for LLM rate limits).

    Returns:
        List of BlogBriefResult in completion order.
    """
    if not gaps:
        return []

    results: list[BlogBriefResult] = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(generate_blog_brief, gap, router): gap for gap in gaps}
        for future in as_completed(futures):
            try:
                results.append(future.result())
            except Exception as exc:  # pragma: no cover — generate_blog_brief catches LLMError
                gap = futures[future]
                results.append(
                    BlogBriefResult(
                        query=str(gap.get("query", "")),
                        intent="unknown",
                        cluster_name=gap.get("cluster_name"),
                        impressions=int(gap.get("impressions", 0)),
                        current_position=float(gap.get("position", 0.0)),
                        error=f"Unexpected error: {exc}",
                    )
                )

    return results


def generate_collection_brief(cluster: dict, router: LLMRouter) -> CollectionBriefResult:
    """Generate a collection page brief for a single product cluster.

    Args:
        cluster: Product cluster dict — expected keys: name, product_ids,
                 product_titles, keywords, size.
        router: Configured LLMRouter instance.

    Returns:
        CollectionBriefResult with brief text on success, error message on failure.
    """
    cluster_name = str(cluster.get("name", ""))
    product_count = int(cluster.get("size", len(cluster.get("product_ids", []))))
    top_keywords: list[str] = cluster.get("keywords", [])[:8]
    current_description = str(cluster.get("description", ""))

    result = CollectionBriefResult(
        cluster_name=cluster_name,
        product_count=product_count,
        top_keywords=top_keywords,
    )

    try:
        tmpl = load_prompt("collection_brief")
        prompt = tmpl.render_user(
            cluster_name=cluster_name,
            product_count=product_count,
            top_keywords=top_keywords,
            current_description=current_description,
        )
        completion = router.complete(
            prompt,
            system=tmpl.render_system(),
            max_tokens=tmpl.max_tokens,
            temperature=tmpl.temperature,
        )
        result.brief = completion.text
        result.provider = completion.provider
    except LLMError as exc:
        result.error = str(exc)

    return result


def generate_collection_briefs(
    clusters: list[dict],
    router: LLMRouter,
    *,
    max_workers: int = 3,
) -> list[CollectionBriefResult]:
    """Generate collection page briefs for multiple product clusters concurrently.

    Args:
        clusters: List of product cluster dicts (from GET /niche/clusters).
        router: Configured LLMRouter instance.
        max_workers: Thread pool size (default 3).

    Returns:
        List of CollectionBriefResult in completion order.
    """
    if not clusters:
        return []

    results: list[CollectionBriefResult] = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(generate_collection_brief, cluster, router): cluster
            for cluster in clusters
        }
        for future in as_completed(futures):
            try:
                results.append(future.result())
            except Exception as exc:  # pragma: no cover
                cluster = futures[future]
                results.append(
                    CollectionBriefResult(
                        cluster_name=str(cluster.get("name", "")),
                        product_count=int(cluster.get("size", 0)),
                        top_keywords=cluster.get("keywords", []),
                        error=f"Unexpected error: {exc}",
                    )
                )

    return results
