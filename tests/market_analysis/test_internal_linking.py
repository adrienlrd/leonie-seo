"""Tests for automatic internal-linking recommendations."""

from __future__ import annotations

from app.market_analysis import internal_linking as il


def _product(
    pid: str, title: str, handle: str, primary_kw: str, intent: str = "transactional"
) -> dict:
    return {
        "product_id": pid,
        "product_title": title,
        "product_handle": handle,
        "product_url": f"/products/{handle}",
        "seo_keywords": [
            {
                "query": primary_kw,
                "target_role": "primary",
                "intent_type": intent,
            }
        ],
    }


def _collection(handle: str, title: str, products: list[str]) -> dict:
    return {"handle": handle, "title": title, "product_ids": products}


def _article(handle: str, title: str, keywords: list[str]) -> dict:
    return {"handle": handle, "title": title, "keywords": keywords}


class TestBuildRecommendations:
    def test_sibling_products_in_same_cluster_are_linked(self):
        products = [
            _product("a", "Harnais chien cuir", "harnais-cuir", "harnais chien cuir"),
            _product("b", "Harnais chien tissu", "harnais-tissu", "harnais chien tissu"),
            _product("c", "Litière chat", "litiere", "litière chat"),
        ]
        recs_by_product = il.build_recommendations(
            products=products, collections=[], articles=[], pages=[], shop="boutique.fr"
        )
        a_recs = recs_by_product["a"]
        target_urls = {r["target_url"] for r in a_recs}
        assert "/products/harnais-tissu" in target_urls
        assert "/products/litiere" not in target_urls

    def test_collection_parent_is_suggested_when_product_belongs(self):
        products = [_product("a", "Harnais cuir", "harnais-cuir", "harnais chien")]
        collections = [_collection("accessoires-chien", "Accessoires chien", ["a"])]
        recs = il.build_recommendations(
            products=products,
            collections=collections,
            articles=[],
            pages=[],
            shop="boutique.fr",
        )["a"]
        urls = {r["target_url"] for r in recs}
        assert "/collections/accessoires-chien" in urls

    def test_collection_parent_is_suggested_from_shopify_edges(self):
        products = [
            _product(
                "gid://shopify/Product/1",
                "Harnais cuir",
                "harnais-cuir",
                "harnais chien",
            )
        ]
        collections = [
            {
                "handle": "accessoires-chien",
                "title": "Accessoires chien",
                "products": {
                    "edges": [
                        {"node": {"id": "gid://shopify/Product/1"}},
                    ]
                },
            }
        ]
        recs = il.build_recommendations(
            products=products,
            collections=collections,
            articles=[],
            pages=[],
            shop="boutique.fr",
        )["gid://shopify/Product/1"]
        urls = {r["target_url"] for r in recs}
        assert "/collections/accessoires-chien" in urls

    def test_article_with_matching_keywords_is_suggested(self):
        products = [
            _product("a", "Harnais cuir", "harnais-cuir", "harnais chien", intent="transactional"),
        ]
        articles = [
            _article(
                "comment-choisir-harnais", "Comment choisir un harnais chien", ["harnais chien"]
            ),
        ]
        recs = il.build_recommendations(
            products=products,
            collections=[],
            articles=articles,
            pages=[],
            shop="boutique.fr",
        )["a"]
        urls = {r["target_url"] for r in recs}
        assert any("/blogs/" in u and "comment-choisir-harnais" in u for u in urls)

    def test_anchor_variants_include_head_keyword(self):
        products = [
            _product("a", "Harnais cuir", "harnais-cuir", "harnais chien cuir"),
            _product("b", "Harnais tissu", "harnais-tissu", "harnais chien tissu"),
        ]
        recs = il.build_recommendations(
            products=products, collections=[], articles=[], pages=[], shop="boutique.fr"
        )["a"]
        first = recs[0]
        assert len(first["anchors"]) >= 1
        joined = " ".join(first["anchors"]).lower()
        assert "harnais" in joined

    def test_no_recommendations_when_only_one_product(self):
        products = [_product("a", "Solo", "solo", "harnais chien")]
        recs = il.build_recommendations(
            products=products, collections=[], articles=[], pages=[], shop="boutique.fr"
        )["a"]
        # Without siblings, collections or articles → empty list (not an error).
        assert recs == []

    def test_caps_at_max_suggestions_per_product(self):
        products = [_product("seed", "Seed", "seed", "harnais chien")]
        # 10 sibling products all in same cluster.
        for i in range(10):
            products.append(
                _product(f"sibling{i}", f"Harnais {i}", f"harnais-{i}", "harnais chien")
            )
        recs = il.build_recommendations(
            products=products, collections=[], articles=[], pages=[], shop="boutique.fr"
        )["seed"]
        assert len(recs) <= 5


class TestOrphanAndGapDetection:
    def test_orphan_products_have_no_collection_or_article_coverage(self):
        products = [
            _product("a", "Avec collection", "a", "alpha"),
            _product("b", "Orphan", "b", "beta"),
        ]
        collections = [_collection("c1", "C1", ["a"])]
        orphans = il.detect_orphan_products(products=products, collections=collections, articles=[])
        assert orphans == ["b"]

    def test_orphan_products_are_not_reported_when_link_coverage_is_unavailable(self):
        products = [
            _product("a", "Produit", "a", "alpha"),
        ]
        orphans = il.detect_orphan_products(
            products=products,
            collections=[],
            articles=[],
        )
        assert orphans == []

    def test_article_body_links_count_as_product_coverage(self):
        products = [
            _product("a", "Mentionné", "produit-a", "alpha"),
        ]
        articles = [
            {"body_html": '<a href="/products/produit-a">Produit A</a>'},
        ]
        orphans = il.detect_orphan_products(
            products=products,
            collections=[],
            articles=articles,
        )
        assert orphans == []

    def test_blog_gap_suggestions_emerge_for_informational_clusters(self):
        products = [
            _product("a", "X", "x", "comment dresser son chien", intent="informational"),
        ]
        gaps = il.detect_blog_gaps(products=products, articles=[])
        assert len(gaps) == 1
        assert "comment dresser" in gaps[0]["suggested_title"].lower()

    def test_blog_gap_skipped_when_article_already_covers_topic(self):
        products = [
            _product("a", "X", "x", "comment dresser son chien", intent="informational"),
        ]
        articles = [_article("dresser-chien", "Dresser son chien", ["dresser chien"])]
        gaps = il.detect_blog_gaps(products=products, articles=articles)
        assert gaps == []
