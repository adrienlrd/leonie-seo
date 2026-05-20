"""Sitemap discovery and snapshot diff helpers for Crawl L3."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass
from urllib.parse import urljoin

import requests

from app.crawl.robots import USER_AGENT

_NS = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}


@dataclass(frozen=True)
class SitemapUrl:
    """One URL discovered from a sitemap."""

    loc: str
    lastmod: str | None = None


def parse_sitemap_xml(xml_text: str) -> tuple[list[SitemapUrl], list[str]]:
    """Parse sitemap XML and return ``(urls, child_sitemaps)``."""
    root = ET.fromstring(xml_text)
    tag = root.tag.rsplit("}", 1)[-1]

    if tag == "sitemapindex":
        children = [
            loc.text.strip()
            for loc in root.findall("sm:sitemap/sm:loc", _NS)
            if loc.text and loc.text.strip()
        ]
        return [], children

    urls: list[SitemapUrl] = []
    for node in root.findall("sm:url", _NS):
        loc = node.find("sm:loc", _NS)
        if loc is None or not loc.text:
            continue
        lastmod = node.find("sm:lastmod", _NS)
        urls.append(SitemapUrl(loc=loc.text.strip(), lastmod=lastmod.text.strip() if lastmod is not None and lastmod.text else None))
    return urls, []


def fetch_sitemap_urls(
    sitemap_urls: list[str],
    *,
    timeout: int = 15,
    max_sitemaps: int = 20,
    session: requests.Session | None = None,
) -> list[SitemapUrl]:
    """Fetch sitemap URLs recursively with a hard sitemap-count cap."""
    client = session or requests.Session()
    pending = list(dict.fromkeys(sitemap_urls))
    seen: set[str] = set()
    discovered: list[SitemapUrl] = []

    while pending and len(seen) < max_sitemaps:
        sitemap_url = pending.pop(0)
        if sitemap_url in seen:
            continue
        seen.add(sitemap_url)

        try:
            response = client.get(sitemap_url, headers={"User-Agent": USER_AGENT}, timeout=timeout)
        except requests.RequestException:
            continue
        if response.status_code >= 400:
            continue
        try:
            urls, children = parse_sitemap_xml(response.text)
        except ET.ParseError:
            continue
        discovered.extend(urls)
        for child in children:
            if child not in seen:
                pending.append(child)

    return discovered


def default_sitemap_urls(base_url: str, robots_sitemaps: list[str]) -> list[str]:
    """Return sitemap URLs declared in robots.txt or the Shopify default path."""
    if robots_sitemaps:
        return list(dict.fromkeys(robots_sitemaps))
    return [urljoin(base_url.rstrip("/") + "/", "sitemap.xml")]


def snapshot_public_urls(snapshot: dict, base_url: str) -> set[str]:
    """Build canonical public URLs represented by the Shopify snapshot."""
    root = base_url.rstrip("/")
    urls: set[str] = {root + "/"}

    for product in snapshot.get("products") or []:
        handle = product.get("handle")
        if handle:
            urls.add(f"{root}/products/{handle}")
    for collection in snapshot.get("collections") or []:
        handle = collection.get("handle")
        if handle:
            urls.add(f"{root}/collections/{handle}")
    for page in snapshot.get("pages") or []:
        handle = page.get("handle")
        if handle:
            urls.add(f"{root}/pages/{handle}")
    for article in snapshot.get("articles") or []:
        handle = article.get("handle")
        blog_handle = article.get("blog_handle") or article.get("blogHandle") or article.get("blog", {}).get("handle")
        if handle and blog_handle:
            urls.add(f"{root}/blogs/{blog_handle}/{handle}")

    return urls


def diff_sitemap_snapshot(sitemap_urls: list[SitemapUrl], snapshot: dict, base_url: str) -> dict[str, list[str]]:
    """Compare sitemap URLs with URLs represented in the Shopify snapshot."""
    sitemap_set = {entry.loc.rstrip("/") for entry in sitemap_urls}
    snapshot_set = {url.rstrip("/") for url in snapshot_public_urls(snapshot, base_url)}
    return {
        "in_sitemap_not_snapshot": sorted(sitemap_set - snapshot_set),
        "in_snapshot_not_sitemap": sorted(snapshot_set - sitemap_set),
    }
