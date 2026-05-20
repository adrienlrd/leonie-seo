"""robots.txt helpers for Crawl L3."""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urljoin
from urllib.robotparser import RobotFileParser

import requests

USER_AGENT = "Leonie-SEO/1.0 (+https://leonie-seo.app)"


@dataclass(frozen=True)
class RobotsRules:
    """Parsed robots.txt rules and declared sitemap URLs."""

    base_url: str
    text: str
    sitemaps: list[str]
    parser: RobotFileParser

    def can_fetch(self, url: str, user_agent: str = USER_AGENT) -> bool:
        """Return whether the URL can be fetched by the crawler."""
        return self.parser.can_fetch(user_agent, url)


def parse_robots_txt(text: str, base_url: str) -> RobotsRules:
    """Parse robots.txt text and extract sitemap declarations."""
    robots_url = urljoin(base_url.rstrip("/") + "/", "robots.txt")
    parser = RobotFileParser(robots_url)
    lines = text.splitlines()
    parser.parse(lines)

    sitemaps: list[str] = []
    for line in lines:
        key, sep, value = line.partition(":")
        if sep and key.strip().lower() == "sitemap":
            sitemap = value.strip()
            if sitemap:
                sitemaps.append(sitemap)

    return RobotsRules(base_url=base_url.rstrip("/"), text=text, sitemaps=sitemaps, parser=parser)


def fetch_robots_txt(
    base_url: str,
    *,
    timeout: int = 10,
    session: requests.Session | None = None,
) -> RobotsRules:
    """Fetch robots.txt, falling back to permissive rules when absent."""
    client = session or requests.Session()
    robots_url = urljoin(base_url.rstrip("/") + "/", "robots.txt")
    try:
        response = client.get(robots_url, headers={"User-Agent": USER_AGENT}, timeout=timeout)
    except requests.RequestException:
        return parse_robots_txt("", base_url)

    if response.status_code >= 400:
        return parse_robots_txt("", base_url)
    return parse_robots_txt(response.text, base_url)
