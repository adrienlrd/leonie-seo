"""Tests for Crawl L3 mini-crawler helpers."""

from __future__ import annotations

from app.crawl.mini import extract_html_signals


def test_extract_html_signals_reads_core_seo_and_jsonld() -> None:
    html = """
    <html>
      <head>
        <title>Product A</title>
        <meta name="description" content="Useful product description">
        <link rel="canonical" href="https://example.com/products/a">
        <link rel="alternate" hreflang="fr" href="https://example.com/fr/products/a">
        <script type="application/ld+json">{"@type": "Product", "name": "A"}</script>
      </head>
    </html>
    """

    signals = extract_html_signals(html)

    assert signals["title"] == "Product A"
    assert signals["meta_description"] == "Useful product description"
    assert signals["canonical"] == "https://example.com/products/a"
    assert signals["hreflang"] == [{"hreflang": "fr", "href": "https://example.com/fr/products/a"}]
    assert signals["jsonld_types"] == ["Product"]
    assert signals["jsonld_valid"] is True


def test_extract_html_signals_marks_invalid_jsonld() -> None:
    signals = extract_html_signals('<script type="application/ld+json">{invalid</script>')

    assert signals["jsonld_valid"] is False
    assert signals["jsonld_types"] == []
