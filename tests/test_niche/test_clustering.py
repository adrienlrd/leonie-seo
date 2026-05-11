"""Tests for product clustering engine."""

from __future__ import annotations

from app.niche.clustering import _normalize, _tokenize, cluster_products
from app.niche.models import ProductCluster

# ── Catalogue fixture ─────────────────────────────────────────────────────────

_CATALOG = [
    {
        "id": "1",
        "title": "Pardessus chien imperméable",
        "product_type": "Vêtements chien",
        "tags": [],
    },
    {"id": "2", "title": "Pull chien laine mérinos", "product_type": "Vêtements chien", "tags": []},
    {"id": "3", "title": "Manteau chien hiver", "product_type": "Vêtements chien", "tags": []},
    {"id": "4", "title": "Fontaine eau chat céramique", "product_type": "Fontaines", "tags": []},
    {"id": "5", "title": "Fontaine eau chien inox", "product_type": "Fontaines", "tags": []},
    {"id": "6", "title": "Griffoir Dimitrios sisal", "product_type": "Griffoirs", "tags": []},
    {"id": "7", "title": "Harnais chat escapade", "product_type": "Harnais", "tags": []},
    {"id": "8", "title": "Harnais chien promenade", "product_type": "Harnais", "tags": []},
]


# ── _normalize / _tokenize ────────────────────────────────────────────────────


def test_normalize_removes_accents():
    assert _normalize("Véloce château") == "veloce chateau"


def test_normalize_lowercases():
    assert _normalize("PARDESSUS CHIEN") == "pardessus chien"


def test_tokenize_filters_short_words():
    tokens = _tokenize("Le chat à la fontaine")
    assert "le" not in tokens
    assert "à" not in tokens
    assert "la" not in tokens


def test_tokenize_filters_stopwords():
    tokens = _tokenize("un beau produit pour chien")
    assert "un" not in tokens
    assert "produit" not in tokens  # in stopwords


def test_tokenize_keeps_meaningful_terms():
    tokens = _tokenize("Pardessus chien imperméable France")
    assert "pardessus" in tokens
    assert "chien" in tokens


# ── cluster_products ──────────────────────────────────────────────────────────


def test_cluster_products_returns_product_clusters():
    clusters = cluster_products(_CATALOG)
    assert all(isinstance(c, ProductCluster) for c in clusters)


def test_cluster_products_groups_by_product_type():
    clusters = cluster_products(_CATALOG)
    names = [c.name for c in clusters]
    # product_type "Vêtements chien" → normalized "vetements chien" should appear
    assert any("vetements" in n or "chien" in n for n in names)


def test_cluster_products_largest_cluster_first():
    clusters = cluster_products(_CATALOG)
    sizes = [c.size for c in clusters]
    assert sizes == sorted(sizes, reverse=True)


def test_cluster_products_covers_all_products():
    clusters = cluster_products(_CATALOG)
    total = sum(c.size for c in clusters)
    assert total == len(_CATALOG)


def test_cluster_products_no_duplicate_product_ids():
    clusters = cluster_products(_CATALOG)
    all_ids = [pid for c in clusters for pid in c.product_ids]
    assert len(all_ids) == len(set(all_ids))


def test_cluster_products_includes_keywords():
    clusters = cluster_products(_CATALOG)
    for c in clusters:
        assert isinstance(c.keywords, list)
        assert len(c.keywords) > 0


def test_cluster_products_empty_input_returns_empty():
    assert cluster_products([]) == []


def test_cluster_products_single_product():
    products = [{"id": "1", "title": "Bol chat design", "product_type": "Bols", "tags": []}]
    clusters = cluster_products(products)
    assert len(clusters) == 1
    assert clusters[0].size == 1


def test_cluster_products_without_product_type_uses_title_keywords():
    """Without product_type, TF-IDF groups by dominant title term.

    Shared terms (fontaine, eau) have low IDF so unique terms dominate.
    The important invariant: all products are covered, none lost.
    """
    products = [
        {"id": "1", "title": "Fontaine eau chat céramique", "product_type": "", "tags": []},
        {"id": "2", "title": "Fontaine eau chat inox", "product_type": "", "tags": []},
    ]
    clusters = cluster_products(products)
    total = sum(c.size for c in clusters)
    assert total == len(products)
    # "fontaine" or "eau" appears in at least one cluster's keywords
    all_keywords = [kw for c in clusters for kw in c.keywords]
    assert any("fontaine" in kw or "eau" in kw for kw in all_keywords)
