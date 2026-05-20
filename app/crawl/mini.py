"""Mini HTTP crawler for Crawl L3."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from html.parser import HTMLParser
from typing import Any

import requests

from app.crawl.robots import USER_AGENT, RobotsRules


class _HTMLSignalsParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.in_title = False
        self.title_parts: list[str] = []
        self.meta_description = ""
        self.canonical = ""
        self.hreflang: list[dict[str, str]] = []
        self.in_jsonld = False
        self.jsonld_parts: list[str] = []
        self.jsonld_blocks: list[Any] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr = {key.lower(): value or "" for key, value in attrs}
        lower_tag = tag.lower()
        if lower_tag == "title":
            self.in_title = True
        elif lower_tag == "meta" and attr.get("name", "").lower() == "description":
            self.meta_description = attr.get("content", "")
        elif lower_tag == "link":
            rel = {part.strip().lower() for part in attr.get("rel", "").split()}
            if "canonical" in rel:
                self.canonical = attr.get("href", "")
            if "alternate" in rel and attr.get("hreflang") and attr.get("href"):
                self.hreflang.append({"hreflang": attr["hreflang"], "href": attr["href"]})
        elif lower_tag == "script" and attr.get("type", "").lower() == "application/ld+json":
            self.in_jsonld = True
            self.jsonld_parts = []

    def handle_endtag(self, tag: str) -> None:
        lower_tag = tag.lower()
        if lower_tag == "title":
            self.in_title = False
        elif lower_tag == "script" and self.in_jsonld:
            raw = "".join(self.jsonld_parts).strip()
            if raw:
                try:
                    self.jsonld_blocks.append(json.loads(raw))
                except json.JSONDecodeError:
                    self.jsonld_blocks.append({"_invalid": True})
            self.in_jsonld = False
            self.jsonld_parts = []

    def handle_data(self, data: str) -> None:
        if self.in_title:
            self.title_parts.append(data)
        if self.in_jsonld:
            self.jsonld_parts.append(data)

    @property
    def title(self) -> str:
        return " ".join(part.strip() for part in self.title_parts if part.strip()).strip()


@dataclass(frozen=True)
class MiniCrawlResult:
    """Extracted crawl signals for one URL."""

    url: str
    allowed_by_robots: bool
    status_code: int | None = None
    final_url: str | None = None
    redirect_chain: list[str] = field(default_factory=list)
    title: str = ""
    meta_description: str = ""
    canonical: str = ""
    hreflang: list[dict[str, str]] = field(default_factory=list)
    jsonld_types: list[str] = field(default_factory=list)
    jsonld_valid: bool = True
    error: str | None = None


def _jsonld_types(block: Any) -> list[str]:
    if isinstance(block, list):
        values: list[str] = []
        for item in block:
            values.extend(_jsonld_types(item))
        return values
    if not isinstance(block, dict) or block.get("_invalid"):
        return []
    graph = block.get("@graph")
    values = _jsonld_types(graph) if graph else []
    node_type = block.get("@type")
    if isinstance(node_type, list):
        values.extend(str(item) for item in node_type)
    elif node_type:
        values.append(str(node_type))
    return values


def extract_html_signals(html: str) -> dict[str, Any]:
    """Extract title, meta description, canonical, hreflang and JSON-LD types."""
    parser = _HTMLSignalsParser()
    parser.feed(html)
    jsonld_valid = not any(isinstance(block, dict) and block.get("_invalid") for block in parser.jsonld_blocks)
    types: list[str] = []
    for block in parser.jsonld_blocks:
        types.extend(_jsonld_types(block))
    return {
        "title": parser.title,
        "meta_description": parser.meta_description,
        "canonical": parser.canonical,
        "hreflang": parser.hreflang,
        "jsonld_types": sorted(set(types)),
        "jsonld_valid": jsonld_valid,
    }


def crawl_url(
    url: str,
    *,
    robots: RobotsRules | None = None,
    timeout: int = 15,
    session: requests.Session | None = None,
) -> MiniCrawlResult:
    """Fetch one URL and return extracted crawl signals."""
    if robots and not robots.can_fetch(url):
        return MiniCrawlResult(url=url, allowed_by_robots=False, error="blocked_by_robots")

    client = session or requests.Session()
    try:
        response = client.get(url, headers={"User-Agent": USER_AGENT}, timeout=timeout, allow_redirects=True)
    except requests.RequestException as exc:
        return MiniCrawlResult(url=url, allowed_by_robots=True, error=str(exc))

    signals = extract_html_signals(response.text if response.text else "")
    return MiniCrawlResult(
        url=url,
        allowed_by_robots=True,
        status_code=response.status_code,
        final_url=response.url,
        redirect_chain=[item.url for item in response.history],
        **signals,
    )


def crawl_urls(
    urls: list[str],
    *,
    robots: RobotsRules | None = None,
    max_urls: int = 50,
    throttle_seconds: float = 1.0,
    timeout: int = 15,
    session: requests.Session | None = None,
) -> list[MiniCrawlResult]:
    """Mini-crawl a capped URL list with basic per-shop throttling."""
    results: list[MiniCrawlResult] = []
    for index, url in enumerate(list(dict.fromkeys(urls))[:max_urls]):
        if index > 0 and throttle_seconds > 0:
            time.sleep(throttle_seconds)
        results.append(crawl_url(url, robots=robots, timeout=timeout, session=session))
    return results
