"""Tests for scripts.report.generate_hreflang."""

import json
import tempfile

from scripts.report.generate_hreflang import (
    _url_paths_from_snapshot,
    build_hreflang_entries,
    render_liquid_snippet,
    render_markdown,
    render_sitemap_xml,
)

_BASE_URL = "https://www.leoniedelacroix.com"
_LOCALES = [("fr-FR", ""), ("fr-BE", "/fr-be"), ("fr-CH", "/fr-ch"), ("fr", "")]


def _make_snapshot(products: list[dict], collections: list[dict] | None = None) -> str:
    data = {"products": products, "collections": collections or []}
    with tempfile.NamedTemporaryFile(suffix=".json", mode="w", delete=False, encoding="utf-8") as f:
        json.dump(data, f)
        return f.name


# ── _url_paths_from_snapshot ───────────────────────────────────────────────


def test_url_paths_includes_homepage():
    path = _make_snapshot([])
    pages = _url_paths_from_snapshot(path)
    assert any(p["path"] == "/" for p in pages)


def test_url_paths_includes_product():
    path = _make_snapshot([{"handle": "manteau-chien", "title": "Le Manteau"}])
    pages = _url_paths_from_snapshot(path)
    assert any(p["path"] == "/products/manteau-chien" for p in pages)


def test_url_paths_excludes_pet_products():
    path = _make_snapshot([{"handle": "pet-test", "title": "Pet Feeder"}])
    pages = _url_paths_from_snapshot(path)
    assert not any("/products/pet-test" in p["path"] for p in pages)


def test_url_paths_includes_collections():
    path = _make_snapshot([], [{"handle": "chien", "title": "Chien"}])
    pages = _url_paths_from_snapshot(path)
    assert any(p["path"] == "/collections/chien" for p in pages)


# ── build_hreflang_entries ─────────────────────────────────────────────────


def test_build_hreflang_entries_returns_one_entry_per_page():
    pages = [
        {"path": "/", "page_type": "homepage", "title": "Home"},
        {"path": "/products/a", "page_type": "product", "title": "A"},
    ]
    entries = build_hreflang_entries(pages, _BASE_URL, _LOCALES)
    assert len(entries) == 2


def test_build_hreflang_entries_has_x_default():
    pages = [{"path": "/products/a", "page_type": "product", "title": "A"}]
    entries = build_hreflang_entries(pages, _BASE_URL, _LOCALES)
    hreflangs = [lnk["hreflang"] for lnk in entries[0]["links"]]
    assert "x-default" in hreflangs


def test_build_hreflang_entries_x_default_points_to_canonical():
    pages = [{"path": "/products/a", "page_type": "product", "title": "A"}]
    entries = build_hreflang_entries(pages, _BASE_URL, _LOCALES)
    x_default = next(lnk for lnk in entries[0]["links"] if lnk["hreflang"] == "x-default")
    assert x_default["url"] == f"{_BASE_URL}/products/a"


def test_build_hreflang_entries_be_gets_prefix():
    pages = [{"path": "/products/a", "page_type": "product", "title": "A"}]
    entries = build_hreflang_entries(pages, _BASE_URL, _LOCALES)
    be_link = next(lnk for lnk in entries[0]["links"] if lnk["hreflang"] == "fr-BE")
    assert "/fr-be/products/a" in be_link["url"]


def test_build_hreflang_entries_fr_generic_no_prefix():
    pages = [{"path": "/products/a", "page_type": "product", "title": "A"}]
    entries = build_hreflang_entries(pages, _BASE_URL, _LOCALES)
    fr_link = next(lnk for lnk in entries[0]["links"] if lnk["hreflang"] == "fr")
    assert fr_link["url"] == f"{_BASE_URL}/products/a"


# ── render_liquid_snippet ──────────────────────────────────────────────────


def test_render_liquid_snippet_contains_hreflang():
    pages = [{"path": "/products/a", "page_type": "product", "title": "A"}]
    entries = build_hreflang_entries(pages, _BASE_URL, _LOCALES)
    snippet = render_liquid_snippet(entries)
    assert 'rel="alternate"' in snippet
    assert "hreflang" in snippet


def test_render_liquid_snippet_contains_if_block():
    pages = [{"path": "/products/a", "page_type": "product", "title": "A"}]
    entries = build_hreflang_entries(pages, _BASE_URL, _LOCALES)
    snippet = render_liquid_snippet(entries)
    assert "{% if " in snippet
    assert "{% endif %}" in snippet


# ── render_sitemap_xml ─────────────────────────────────────────────────────


def test_render_sitemap_xml_is_valid_xml_structure():
    pages = [{"path": "/products/a", "page_type": "product", "title": "A"}]
    entries = build_hreflang_entries(pages, _BASE_URL, _LOCALES)
    xml = render_sitemap_xml(entries)
    assert "<?xml" in xml
    assert "<urlset" in xml
    assert "<xhtml:link" in xml
    assert "</urlset>" in xml


# ── render_markdown ────────────────────────────────────────────────────────


def test_render_markdown_has_date():
    pages = [{"path": "/", "page_type": "homepage", "title": "Home"}]
    entries = build_hreflang_entries(pages, _BASE_URL, _LOCALES)
    snippet = render_liquid_snippet(entries)
    md = render_markdown(entries, _LOCALES, "2026-05-08", snippet)
    assert "2026-05-08" in md


def test_render_markdown_has_shopify_integration_section():
    pages = [{"path": "/", "page_type": "homepage", "title": "Home"}]
    entries = build_hreflang_entries(pages, _BASE_URL, _LOCALES)
    snippet = render_liquid_snippet(entries)
    md = render_markdown(entries, _LOCALES, "2026-05-08", snippet)
    assert "theme.liquid" in md
    assert "Marchés" in md or "marché" in md.lower()
