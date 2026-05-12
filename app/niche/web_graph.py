"""Common Crawl CDX Index client — domain coverage and URL pattern analysis."""

from __future__ import annotations

import json
from dataclasses import dataclass
from urllib.parse import urlparse

import httpx

_CC_BASE = "https://index.commoncrawl.org"


class WebGraphError(Exception):
    """Raised on CC-Index API or parse errors."""


@dataclass
class CCPage:
    """A single crawled page entry from the CC-Index."""

    url: str
    timestamp: str
    status: str
    mime: str


class CCIndexClient:
    """Thin client for the Common Crawl CDX Index HTTP API.

    No credentials needed — the API is publicly accessible.
    Use sparingly and cache results; CC-Index is rate-sensitive.

    Args:
        base_url: CC-Index base URL (override for tests).
        timeout: httpx request timeout in seconds.
    """

    def __init__(self, *, base_url: str = _CC_BASE, timeout: float = 30.0) -> None:
        self._base = base_url.rstrip("/")
        self._timeout = timeout
        self._cached_crawl: str | None = None

    def get_latest_crawl(self) -> str:
        """Return the most recent CC crawl index identifier.

        Returns:
            Crawl ID, e.g. "CC-MAIN-2024-18".

        Raises:
            WebGraphError: If collinfo endpoint is unreachable or malformed.
        """
        if self._cached_crawl:
            return self._cached_crawl
        try:
            resp = httpx.get(
                f"{self._base}/collinfo.json",
                timeout=self._timeout,
                headers={"Accept": "application/json"},
            )
        except httpx.RequestError as exc:
            raise WebGraphError(f"CC-Index unreachable: {exc}") from exc

        if resp.status_code != 200:
            raise WebGraphError(f"collinfo HTTP {resp.status_code}")

        try:
            collections = resp.json()
            self._cached_crawl = collections[0]["id"]
        except (KeyError, IndexError, json.JSONDecodeError) as exc:
            raise WebGraphError(f"Unexpected collinfo format: {exc}") from exc

        return self._cached_crawl

    def _query_index(self, crawl: str, url_pattern: str, limit: int) -> list[CCPage]:
        """POST a CDX query and parse NDJSON response into CCPage list."""
        params = {"url": url_pattern, "output": "json", "limit": str(limit)}
        try:
            resp = httpx.get(
                f"{self._base}/{crawl}/index",
                params=params,
                timeout=self._timeout,
            )
        except httpx.RequestError as exc:
            raise WebGraphError(f"CC-Index query failed: {exc}") from exc

        if resp.status_code == 404:
            return []
        if resp.status_code != 200:
            raise WebGraphError(f"CC-Index HTTP {resp.status_code}: {resp.text[:200]}")

        pages: list[CCPage] = []
        for line in resp.text.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if "error" in record:
                continue
            pages.append(
                CCPage(
                    url=record.get("url", ""),
                    timestamp=record.get("timestamp", ""),
                    status=record.get("status", ""),
                    mime=record.get("mime", ""),
                )
            )
        return pages

    def query_domain(
        self,
        domain: str,
        *,
        crawl: str | None = None,
        limit: int = 200,
    ) -> list[CCPage]:
        """Fetch CC-Index entries for all crawled pages on a domain.

        Args:
            domain: Hostname (e.g. "miacara.com").
            crawl: Crawl index ID. Defaults to latest.
            limit: Max results (CC-Index hard caps at 100 000).

        Returns:
            List of CCPage instances.
        """
        index_id = crawl or self.get_latest_crawl()
        return self._query_index(index_id, f"*.{domain}", limit)

    def search_urls(
        self,
        pattern: str,
        *,
        crawl: str | None = None,
        limit: int = 100,
    ) -> list[CCPage]:
        """Query CC-Index for URLs matching an arbitrary wildcard pattern.

        Useful for brand mention detection: `*brand-name*`.

        Args:
            pattern: CDX URL pattern (wildcards with `*`).
            crawl: Crawl index ID. Defaults to latest.
            limit: Max results.

        Returns:
            List of CCPage instances.
        """
        index_id = crawl or self.get_latest_crawl()
        return self._query_index(index_id, pattern, limit)

    def count_domain_pages(
        self,
        domain: str,
        *,
        crawl: str | None = None,
        limit: int = 500,
    ) -> int:
        """Return the number of crawled pages for a domain (rough authority proxy).

        Args:
            domain: Hostname to count.
            crawl: Crawl index ID. Defaults to latest.
            limit: Query cap — result is capped at this value.

        Returns:
            Page count (integer, capped at limit).
        """
        return len(self.query_domain(domain, crawl=crawl, limit=limit))

    def get_url_patterns(
        self,
        domain: str,
        *,
        crawl: str | None = None,
        limit: int = 200,
    ) -> dict[str, int]:
        """Analyse URL path structure for a domain.

        Groups crawled URLs by first-level path prefix and returns counts.
        E.g. {"/products": 45, "/collections": 12, "/blog": 8, "/": 3}.

        Args:
            domain: Hostname to analyse.
            crawl: Crawl index ID. Defaults to latest.
            limit: Max pages to sample.

        Returns:
            Dict[path_prefix, count] sorted by count descending.
        """
        pages = self.query_domain(domain, crawl=crawl, limit=limit)
        counts: dict[str, int] = {}
        for page in pages:
            try:
                path = urlparse(page.url).path
            except Exception:
                path = "/"
            parts = path.split("/")
            prefix = f"/{parts[1]}" if len(parts) > 1 and parts[1] else "/"
            counts[prefix] = counts.get(prefix, 0) + 1

        return dict(sorted(counts.items(), key=lambda kv: -kv[1]))
