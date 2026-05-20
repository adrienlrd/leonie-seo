"""Tests for Crawl L3 robots.txt helpers."""

from __future__ import annotations

from app.crawl.robots import parse_robots_txt


def test_parse_robots_txt_extracts_sitemaps_and_respects_disallow() -> None:
    robots = parse_robots_txt(
        "User-agent: *\nDisallow: /private\nSitemap: https://example.com/sitemap.xml\n",
        "https://example.com",
    )

    assert robots.sitemaps == ["https://example.com/sitemap.xml"]
    assert robots.can_fetch("https://example.com/products/a") is True
    assert robots.can_fetch("https://example.com/private/a") is False
