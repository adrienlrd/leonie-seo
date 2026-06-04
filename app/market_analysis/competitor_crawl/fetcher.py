"""Controlled external fetcher for competitor SERP URLs."""

from __future__ import annotations

import hashlib
import logging
import time
from urllib.parse import urlsplit, urlunsplit

import requests

from app.crawl.robots import RobotsRules, parse_robots_txt
from app.market_analysis.competitor_crawl.config import CompetitorCrawlConfig
from app.market_analysis.competitor_crawl.extractor import extract_competitor_features
from app.market_analysis.competitor_crawl.models import (
    CompetitorCrawlResult,
    CompetitorCrawlTarget,
)
from app.market_analysis.competitor_crawl.store import (
    get_cached_features,
    upsert_cached_features,
)

logger = logging.getLogger(__name__)


def fetch_competitor_targets(
    targets: list[CompetitorCrawlTarget],
    config: CompetitorCrawlConfig,
    *,
    session: requests.Session | None = None,
) -> list[CompetitorCrawlResult]:
    """Fetch selected competitor URLs with robots, cache, timeout and domain throttle."""
    if not config.enabled or not targets or config.max_urls_per_run <= 0:
        return []
    client = session or requests.Session()
    robots_by_domain: dict[str, RobotsRules] = {}
    last_fetch_at: dict[str, float] = {}
    results: list[CompetitorCrawlResult] = []
    seen_urls: set[str] = set()
    for target in targets:
        if len(results) >= config.max_urls_per_run:
            break
        if target.url in seen_urls:
            continue
        seen_urls.add(target.url)
        cached = _cached_result(target, config)
        if cached is not None:
            results.append(cached)
            continue
        domain = target.domain
        robots = robots_by_domain.get(domain)
        if robots is None:
            robots = _fetch_robots(target.url, config=config, session=client)
            robots_by_domain[domain] = robots
        if not robots.can_fetch(target.url, user_agent=config.user_agent):
            result = CompetitorCrawlResult(
                target=target,
                allowed_by_robots=False,
                error="blocked_by_robots",
            )
            _cache_result(result)
            results.append(result)
            continue
        _throttle(domain, last_fetch_at, config.throttle_seconds)
        result = _fetch_one(target, config=config, session=client)
        _cache_result(result)
        results.append(result)
    return results


def _cached_result(
    target: CompetitorCrawlTarget,
    config: CompetitorCrawlConfig,
) -> CompetitorCrawlResult | None:
    try:
        cached = get_cached_features(target.url, ttl_days=config.cache_ttl_days)
    except Exception as exc:
        logger.debug("competitor crawl cache read failed for %s: %s", target.url, exc)
        return None
    if not cached:
        return None
    return CompetitorCrawlResult(
        target=target,
        allowed_by_robots=bool(cached.get("allowed_by_robots")),
        status_code=cached.get("status_code"),
        final_url=cached.get("final_url"),
        features=dict(cached.get("features") or {}),
        error=cached.get("error"),
        from_cache=True,
        html_hash=str(cached.get("html_hash") or ""),
    )


def _fetch_one(
    target: CompetitorCrawlTarget,
    *,
    config: CompetitorCrawlConfig,
    session: requests.Session,
) -> CompetitorCrawlResult:
    try:
        response = session.get(
            target.url,
            headers={"User-Agent": config.user_agent, "Accept": "text/html,application/xhtml+xml"},
            timeout=config.timeout,
            allow_redirects=True,
        )
        content_type = response.headers.get("content-type", "")
        if "html" not in content_type.lower() and response.text:
            logger.debug(
                "competitor crawl non-html content-type for %s: %s", target.url, content_type
            )
        html = response.text or ""
        features = extract_competitor_features(html, url=response.url)
        return CompetitorCrawlResult(
            target=target,
            allowed_by_robots=True,
            status_code=response.status_code,
            final_url=response.url,
            features=features,
            html_hash=hashlib.sha256(html.encode("utf-8", errors="ignore")).hexdigest(),
        )
    except requests.RequestException as exc:
        return CompetitorCrawlResult(
            target=target,
            allowed_by_robots=True,
            error=str(exc),
        )
    except Exception as exc:
        logger.debug("competitor crawl extraction failed for %s: %s", target.url, exc)
        return CompetitorCrawlResult(
            target=target,
            allowed_by_robots=True,
            error=str(exc),
        )


def _fetch_robots(
    url: str,
    *,
    config: CompetitorCrawlConfig,
    session: requests.Session,
) -> RobotsRules:
    base_url = _base_url(url)
    robots_url = f"{base_url}/robots.txt"
    try:
        response = session.get(
            robots_url,
            headers={"User-Agent": config.user_agent},
            timeout=config.timeout,
        )
        if response.status_code >= 400:
            return parse_robots_txt("", base_url)
        return parse_robots_txt(response.text, base_url)
    except requests.RequestException:
        return parse_robots_txt("", base_url)


def _base_url(url: str) -> str:
    parsed = urlsplit(url)
    return urlunsplit((parsed.scheme, parsed.netloc, "", "", "")).rstrip("/")


def _throttle(domain: str, last_fetch_at: dict[str, float], throttle_seconds: float) -> None:
    if throttle_seconds <= 0:
        last_fetch_at[domain] = time.monotonic()
        return
    previous = last_fetch_at.get(domain)
    now = time.monotonic()
    if previous is not None:
        delay = throttle_seconds - (now - previous)
        if delay > 0:
            time.sleep(delay)
    last_fetch_at[domain] = time.monotonic()


def _cache_result(result: CompetitorCrawlResult) -> None:
    try:
        upsert_cached_features(
            url=result.target.url,
            domain=result.target.domain,
            status_code=result.status_code,
            final_url=result.final_url,
            allowed_by_robots=result.allowed_by_robots,
            html_hash=result.html_hash,
            features=result.features,
            error=result.error,
        )
    except Exception as exc:
        logger.debug("competitor crawl cache write failed for %s: %s", result.target.url, exc)
