"""Environment configuration for competitor crawling."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class CompetitorCrawlConfig:
    """Runtime limits for the optional competitor crawl."""

    enabled: bool = False
    max_urls_per_product: int = 3
    max_urls_per_run: int = 50
    timeout: int = 12
    throttle_seconds: float = 1.5
    cache_ttl_days: int = 14
    user_agent: str = "LeonieSEOBot/0.1 (+SEO/GEO analysis; contact configurable)"

    @classmethod
    def from_env(cls) -> CompetitorCrawlConfig:
        """Build config from COMPETITOR_CRAWL_* environment variables."""
        return cls(
            enabled=_env_bool("COMPETITOR_CRAWL_ENABLED", False),
            max_urls_per_product=_env_int("COMPETITOR_CRAWL_MAX_URLS_PER_PRODUCT", 3, minimum=0),
            max_urls_per_run=_env_int("COMPETITOR_CRAWL_MAX_URLS_PER_RUN", 50, minimum=0),
            timeout=_env_int("COMPETITOR_CRAWL_TIMEOUT_SECONDS", 12, minimum=1),
            throttle_seconds=_env_float("COMPETITOR_CRAWL_THROTTLE_SECONDS", 1.5, minimum=0.0),
            cache_ttl_days=_env_int("COMPETITOR_CRAWL_CACHE_TTL_DAYS", 14, minimum=1),
            user_agent=os.getenv(
                "COMPETITOR_CRAWL_USER_AGENT",
                "LeonieSEOBot/0.1 (+SEO/GEO analysis; contact configurable)",
            ).strip()
            or "LeonieSEOBot/0.1 (+SEO/GEO analysis; contact configurable)",
        )


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int, *, minimum: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError:
        return default
    return max(minimum, value)


def _env_float(name: str, default: float, *, minimum: float) -> float:
    try:
        value = float(os.getenv(name, str(default)))
    except ValueError:
        return default
    return max(minimum, value)
