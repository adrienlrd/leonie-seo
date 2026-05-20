"""Tests for Crawl L3 sitemap helpers."""

from __future__ import annotations

from app.crawl.sitemap import diff_sitemap_snapshot, parse_sitemap_xml, snapshot_public_urls


def test_parse_sitemap_xml_returns_urls_and_lastmod() -> None:
    urls, children = parse_sitemap_xml(
        """<?xml version="1.0"?>
        <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
          <url><loc>https://example.com/products/a</loc><lastmod>2026-05-20</lastmod></url>
        </urlset>
        """
    )

    assert children == []
    assert urls[0].loc == "https://example.com/products/a"
    assert urls[0].lastmod == "2026-05-20"


def test_parse_sitemap_xml_returns_child_sitemaps() -> None:
    urls, children = parse_sitemap_xml(
        """<?xml version="1.0"?>
        <sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
          <sitemap><loc>https://example.com/products.xml</loc></sitemap>
        </sitemapindex>
        """
    )

    assert urls == []
    assert children == ["https://example.com/products.xml"]


def test_snapshot_public_urls_includes_products_collections_pages_and_articles() -> None:
    snapshot = {
        "products": [{"handle": "harnais"}],
        "collections": [{"handle": "chiens"}],
        "pages": [{"handle": "contact"}],
        "articles": [{"handle": "guide", "blog_handle": "news"}],
    }

    urls = snapshot_public_urls(snapshot, "https://example.com")

    assert "https://example.com/products/harnais" in urls
    assert "https://example.com/collections/chiens" in urls
    assert "https://example.com/pages/contact" in urls
    assert "https://example.com/blogs/news/guide" in urls


def test_diff_sitemap_snapshot_reports_missing_urls() -> None:
    snapshot = {"products": [{"handle": "harnais"}], "collections": [], "pages": [], "articles": []}
    urls, _ = parse_sitemap_xml(
        """<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
          <url><loc>https://example.com/products/harnais</loc></url>
          <url><loc>https://example.com/pages/orphan</loc></url>
        </urlset>"""
    )

    diff = diff_sitemap_snapshot(urls, snapshot, "https://example.com")

    assert diff["in_sitemap_not_snapshot"] == ["https://example.com/pages/orphan"]
