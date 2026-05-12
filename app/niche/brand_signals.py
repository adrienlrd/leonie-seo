"""Brand mention and competitor coverage signals via CC-Index."""

from __future__ import annotations

from app.niche.web_graph import CCIndexClient


def search_brand_in_urls(
    client: CCIndexClient,
    brand_slug: str,
    *,
    crawl: str | None = None,
    limit: int = 100,
) -> list[str]:
    """Find third-party pages that reference a brand slug in their URL.

    Queries the CC-Index wildcard pattern `*brand_slug*`. Surfaces external
    pages that contain the brand name (comparison articles, retailer listings,
    press mentions, unlinked brand references in URLs).

    Args:
        client: CCIndexClient instance.
        brand_slug: URL-safe brand identifier (e.g. "leoniedelacroix").
        crawl: CC crawl index ID. Defaults to latest.
        limit: Max results to return.

    Returns:
        List of unique URLs (deduplicated, preserving order).
    """
    pages = client.search_urls(f"*{brand_slug}*", crawl=crawl, limit=limit)
    seen: set[str] = set()
    urls: list[str] = []
    for page in pages:
        if page.url and page.url not in seen:
            seen.add(page.url)
            urls.append(page.url)
    return urls


def compare_competitor_coverage(
    client: CCIndexClient,
    competitors: list[str],
    *,
    crawl: str | None = None,
    limit_per_domain: int = 500,
) -> dict[str, int]:
    """Compare crawled page count across competitor domains.

    Higher page count = larger indexed content footprint = rough authority signal.
    Useful for benchmarking the shop's content volume vs. competitors.

    Args:
        client: CCIndexClient instance.
        competitors: Domain names to compare (e.g. ["miacara.com", "zara.com"]).
        crawl: CC crawl index ID. Defaults to latest.
        limit_per_domain: Query cap per domain.

    Returns:
        Dict[domain, page_count] sorted by page_count descending.
    """
    results: dict[str, int] = {}
    for domain in competitors:
        domain = domain.strip().lower()
        if not domain:
            continue
        results[domain] = client.count_domain_pages(
            domain, crawl=crawl, limit=limit_per_domain
        )
    return dict(sorted(results.items(), key=lambda kv: -kv[1]))
