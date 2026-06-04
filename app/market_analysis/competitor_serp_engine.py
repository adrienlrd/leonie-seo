"""Engine for the dedicated competitor SERP crawl page.

Reads seo_keywords from the last market analysis, queries the keyword cache for
SERP intel (no new API calls if cache is warm), collects ALL competitor URLs per
domain (not limited to top-3 per product), crawls them with the existing
infrastructure, and returns a result organized by competitor domain.
"""
from __future__ import annotations

import logging
import os
from collections import defaultdict
from dataclasses import replace
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlsplit

from app.market_analysis import keyword_cache
from app.market_analysis.competitor_crawl.config import CompetitorCrawlConfig
from app.market_analysis.competitor_crawl.fetcher import fetch_competitor_targets
from app.market_analysis.competitor_crawl.insights import url_to_competitor_top_url
from app.market_analysis.competitor_crawl.models import CompetitorCrawlTarget
from app.market_analysis.competitor_crawl.url_selection import canonicalize_competitor_url
from app.market_analysis.jobs import load_latest_result

logger = logging.getLogger(__name__)

_LOCATION_CODE = 2250
_LANGUAGE_CODE = "fr"
_BLOCKED_PATH_PARTS = ("/cart", "/checkout", "/account", "/search", "/login", "/register")


def build_config_for_serp_job() -> CompetitorCrawlConfig:
    """Build a crawl config suitable for the dedicated SERP job.

    Always sets enabled=True (user explicitly triggered the crawl) and
    respects COMPETITOR_SERP_MAX_URLS_PER_RUN env var (default 100).
    """
    base = CompetitorCrawlConfig.from_env()
    max_urls = int(os.getenv("COMPETITOR_SERP_MAX_URLS_PER_RUN", "100"))
    return replace(base, enabled=True, max_urls_per_run=max(10, max_urls))


def run_competitor_serp_crawl(shop: str, config: CompetitorCrawlConfig) -> dict[str, Any]:
    """Run the competitor SERP crawl for a shop.

    Returns:
        Dict with 'competitors' (list ordered by strength), 'total_urls_crawled',
        'keywords_used', and 'created_at'. On error returns an 'error' key.
    """
    result = load_latest_result(shop)
    if not result:
        return {
            "created_at": datetime.now(UTC).isoformat(),
            "shop": shop,
            "competitors": [],
            "total_urls_crawled": 0,
            "keywords_used": 0,
            "error": "no_market_analysis",
        }

    merchant_domains = _collect_merchant_domains(shop)
    all_keywords = _collect_all_keywords(result)

    serp_cache = keyword_cache.get_many(
        keyword_cache.SERP,
        list(all_keywords),
        location_code=_LOCATION_CODE,
        language_code=_LANGUAGE_CODE,
    )
    missing = len(all_keywords) - len(serp_cache)
    if missing > 0:
        logger.warning(
            "competitor_serp: %d/%d keywords missing from SERP cache — re-run market analysis to refresh",
            missing,
            len(all_keywords),
        )
    logger.info("competitor_serp: %d keywords found in cache", len(serp_cache))

    domain_targets: dict[str, list[CompetitorCrawlTarget]] = defaultdict(list)
    domain_strength: dict[str, int] = {}
    domain_sources: dict[str, str] = {}
    domain_serp_intel: dict[str, dict[str, Any]] = {}

    for kw_norm, intel in serp_cache.items():
        domain_serp_intel[kw_norm] = intel
        for comp in intel.get("top_competitors") or []:
            if not isinstance(comp, dict):
                continue
            domain = _normalize_domain(str(comp.get("domain", "")))
            if not domain or _is_merchant(domain, merchant_domains):
                continue
            url = str(comp.get("url", "")).strip()
            if not url:
                continue
            canonical = canonicalize_competitor_url(url)
            if not canonical or _is_blocked_path(canonical):
                continue
            rank = int(comp.get("rank") or 99)
            strength = max(10, min(100, 100 - rank * 5))
            if strength > domain_strength.get(domain, 0):
                domain_strength[domain] = strength
            domain_sources.setdefault(domain, "serp_per_product")
            domain_targets[domain].append(CompetitorCrawlTarget(
                keyword=kw_norm,
                rank=rank,
                domain=domain,
                url=canonical,
                title=str(comp.get("title", "")),
            ))

    for signal in result.get("competitor_signals") or []:
        domain = _normalize_domain(str(signal.get("domain", "")))
        if not domain or _is_merchant(domain, merchant_domains):
            continue
        domain_targets.setdefault(domain, [])
        if domain not in domain_strength:
            domain_strength[domain] = int(signal.get("estimated_strength") or 30)
        if domain not in domain_sources:
            domain_sources[domain] = "domain_level"

    max_per_domain = int(os.getenv("COMPETITOR_SERP_MAX_URLS_PER_DOMAIN", "10"))
    targets = _deduplicate_targets(domain_targets, max_per_domain=max_per_domain, max_total=config.max_urls_per_run)
    logger.info("competitor_serp: crawling %d URLs across %d domains", len(targets), len(domain_targets))

    crawl_results = fetch_competitor_targets(targets, config)

    return _build_result(
        shop=shop,
        domain_targets=domain_targets,
        domain_strength=domain_strength,
        domain_sources=domain_sources,
        domain_serp_intel=domain_serp_intel,
        crawl_results=crawl_results,
        keywords_used=len(serp_cache),
    )


def _collect_merchant_domains(shop: str) -> set[str]:
    return {_normalize_domain(shop)} - {""}


def _collect_all_keywords(result: dict[str, Any]) -> set[str]:
    keywords: set[str] = set()
    for product in result.get("products") or []:
        for kw in product.get("seo_keywords") or []:
            if isinstance(kw, dict):
                query = str(kw.get("query", "")).strip().lower()
                if query:
                    keywords.add(query)
    return keywords


def _deduplicate_targets(
    domain_targets: dict[str, list[CompetitorCrawlTarget]],
    max_per_domain: int,
    max_total: int,
) -> list[CompetitorCrawlTarget]:
    all_targets: list[CompetitorCrawlTarget] = []
    for targets in domain_targets.values():
        seen: set[str] = set()
        deduped: list[CompetitorCrawlTarget] = []
        for t in sorted(targets, key=lambda t: t.rank):
            if t.url not in seen:
                seen.add(t.url)
                deduped.append(t)
                if len(deduped) >= max_per_domain:
                    break
        all_targets.extend(deduped)
    all_targets.sort(key=lambda t: t.rank)
    return all_targets[:max_total]


def _build_result(
    shop: str,
    domain_targets: dict[str, list[CompetitorCrawlTarget]],
    domain_strength: dict[str, int],
    domain_sources: dict[str, str],
    domain_serp_intel: dict[str, dict[str, Any]],
    crawl_results: list[Any],
    keywords_used: int,
) -> dict[str, Any]:
    results_by_url: dict[str, Any] = {r.target.url: r for r in crawl_results}
    competitors: list[dict[str, Any]] = []
    total_urls_crawled = 0

    for domain in sorted(domain_targets):
        seen: set[str] = set()
        url_entries: list[dict[str, Any]] = []
        for target in sorted(domain_targets[domain], key=lambda t: t.rank):
            if target.url in seen:
                continue
            seen.add(target.url)
            crawl_result = results_by_url.get(target.url)
            entry = _build_url_entry(target, crawl_result, domain_serp_intel)
            url_entries.append(entry)
            if crawl_result and crawl_result.status_code and crawl_result.status_code < 400 and not crawl_result.error:
                total_urls_crawled += 1
        competitors.append({
            "domain": domain,
            "source": domain_sources.get(domain, "serp_per_product"),
            "estimated_strength": domain_strength.get(domain, 30),
            "urls": url_entries,
        })

    competitors.sort(key=lambda c: -c["estimated_strength"])
    return {
        "created_at": datetime.now(UTC).isoformat(),
        "shop": shop,
        "competitors": competitors,
        "total_urls_crawled": total_urls_crawled,
        "keywords_used": keywords_used,
    }


def _build_url_entry(
    target: CompetitorCrawlTarget,
    result: Any | None,
    domain_serp_intel: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    intel = domain_serp_intel.get(target.keyword) or {}
    features = result.features if (result and result.features) else {}
    item: dict[str, Any] = {
        "url": target.url,
        "domain": target.domain,
        "rank": target.rank,
        "keyword": target.keyword,
        "keyword_intent_type": "",
        "title": features.get("title") or target.title,
        "page_type": features.get("page_type", "unknown"),
        "final_url": (result.final_url if result else None) or target.url,
        "from_cache": bool(result and result.from_cache),
        "serp_paa_questions": intel.get("paa") or [],
        "serp_featured_snippet": intel.get("featured_snippet"),
        **features,
    }
    entry = url_to_competitor_top_url(item)
    entry["from_cache"] = item["from_cache"]
    if result and result.error:
        entry["error"] = result.error
    if result and not result.allowed_by_robots:
        entry["blocked_by_robots"] = True
    return entry


def _normalize_domain(value: str) -> str:
    raw = value.strip().lower()
    if not raw:
        return ""
    if "://" in raw:
        raw = urlsplit(raw).netloc.lower()
    raw = raw.split("/")[0].split(":")[0]
    return raw[4:] if raw.startswith("www.") else raw


def _is_merchant(domain: str, merchant_domains: set[str]) -> bool:
    return any(domain == m or domain.endswith(f".{m}") for m in merchant_domains)


def _is_blocked_path(url: str) -> bool:
    path = urlsplit(url).path.lower().rstrip("/")
    return any(path == part or path.startswith(f"{part}/") for part in _BLOCKED_PATH_PARTS)
