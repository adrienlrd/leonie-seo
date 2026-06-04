"""Typed models for competitor crawl targets and results."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class CompetitorCrawlTarget:
    """One external SERP URL selected for controlled competitor analysis."""

    keyword: str
    rank: int
    domain: str
    url: str
    title: str = ""


@dataclass(frozen=True)
class CompetitorCrawlResult:
    """Fetch and extraction result for one competitor URL."""

    target: CompetitorCrawlTarget
    allowed_by_robots: bool
    status_code: int | None = None
    final_url: str | None = None
    features: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    from_cache: bool = False
    html_hash: str = ""
