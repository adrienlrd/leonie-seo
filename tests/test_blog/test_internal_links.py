"""Internal links for generated blog drafts."""

from __future__ import annotations

from unittest.mock import patch

from app.api.blog import BlogSection, _assemble_body_html, _draft_from_product
from app.blog.internal_links import (
    render_internal_links_html,
    select_blog_internal_links,
    suggest_cluster_links,
)


def test_select_blog_internal_links_deduplicates_and_prefers_anchor() -> None:
    links = select_blog_internal_links(
        [
            {
                "target_url": "/products/harnais-cuir",
                "target_title": "Harnais cuir",
                "anchors": ["harnais chien cuir", "Harnais cuir"],
                "reason": "sibling_product",
            },
            {
                "target_url": "/products/harnais-cuir",
                "target_title": "Duplicate",
                "anchors": ["duplicate"],
            },
            {
                "target_url": "/collections/chien",
                "target_title": "Chien",
                "anchors": [],
                "reason": "collection_parent",
            },
        ]
    )

    assert links == [
        {
            "target_url": "/products/harnais-cuir",
            "anchor": "harnais chien cuir",
            "target_title": "Harnais cuir",
            "reason": "sibling_product",
        },
        {
            "target_url": "/collections/chien",
            "anchor": "Chien",
            "target_title": "Chien",
            "reason": "collection_parent",
        },
    ]


def test_render_internal_links_html_escapes_values() -> None:
    html = render_internal_links_html(
        [
            {
                "target_url": '/products/a" onclick="bad',
                "anchor": "<Harnais>",
                "target_title": "Titre",
            }
        ]
    )

    assert 'class="leonie-internal-links"' in html
    assert "&lt;Harnais&gt;" in html
    assert "onclick=&quot;bad" in html
    assert "<Harnais>" not in html


def test_assemble_body_html_appends_internal_links_block() -> None:
    html = _assemble_body_html(
        "Intro",
        [BlogSection(h2="Pourquoi choisir ce produit ?", direct_answer="Réponse.", body="Corps.")],
        [{"target_url": "/products/a", "anchor": "produit conseillé", "target_title": "A"}],
    )

    assert "<h2>Pourquoi choisir ce produit ?</h2>" in html
    assert "leonie-internal-links" in html
    assert '<a href="/products/a"' in html


def test_draft_from_product_carries_market_analysis_internal_links() -> None:
    latest = {
        "products": [
            {
                "product_id": "gid://shopify/Product/1",
                "product_title": "Harnais cuir",
                "product_summary": "Harnais solide.",
                "target_customer": "Propriétaires de chien",
                "content_test_pack": {
                    "proposed_blog_title": "Comment choisir un harnais chien cuir",
                    "proposed_blog_intro": "Intro",
                    "proposed_blog_ideas": [
                        {
                            "title": "Comment choisir un harnais chien cuir",
                            "target_keyword": "harnais chien cuir",
                            "intro": "Intro",
                            "outline": ["Pourquoi le cuir ?"],
                        }
                    ],
                    "confirmed_facts": [{"key": "material", "value": "cuir"}],
                    "recommended_internal_links": [
                        {
                            "target_url": "/collections/chien",
                            "target_title": "Collection chien",
                            "anchors": ["accessoires chien"],
                            "reason": "collection_parent",
                        }
                    ],
                },
                "product_url": "/products/harnais-cuir",
            }
        ]
    }

    with patch("app.api.blog.load_latest_result", return_value=latest):
        draft = _draft_from_product(
            "shop.myshopify.com",
            "gid://shopify/Product/1",
            blog_idea_index=0,
        )

    assert draft["internal_links"] == [
        {
            "target_url": "/products/harnais-cuir",
            "anchor": "harnais chien cuir",
            "target_title": "Harnais cuir",
            "reason": "source_product",
        },
        {
            "target_url": "/collections/chien",
            "anchor": "accessoires chien",
            "target_title": "Collection chien",
            "reason": "collection_parent",
        },
    ]


def test_suggest_cluster_links_self_pillar_links_down_to_siblings() -> None:
    other_drafts = [
        {
            "id": "draft-1",
            "blog_title": "Croquettes sans céréales pour chien sensible",
            "target_keyword": "croquettes sans céréales chien",
            "outline": ["Pourquoi choisir ?", "Comment doser ?"],
            "shopify_article_handle": "croquettes-sans-cereales-chien-sensible",
        },
        {
            "id": "draft-2",
            "blog_title": "Quelle alimentation pour un chien allergique ?",
            "target_keyword": "alimentation chien allergique",
            "outline": ["Les signes d'allergie"],
            "shopify_article_handle": "",
        },
    ]

    links = suggest_cluster_links(
        current_keyword="croquettes sans céréales chien sensible",
        current_outline=["A", "B", "C", "D"],
        other_drafts=other_drafts,
    )

    assert links == [
        {
            "target_url": "/blogs/blog/croquettes-sans-cereales-chien-sensible",
            "anchor": "Croquettes sans céréales pour chien sensible",
            "target_title": "Croquettes sans céréales pour chien sensible",
            "reason": "cluster_sibling",
        }
    ]


def test_suggest_cluster_links_self_sibling_links_up_to_pillar() -> None:
    other_drafts = [
        {
            "id": "draft-1",
            "blog_title": "Le guide complet des croquettes sans céréales pour chien",
            "target_keyword": "croquettes sans céréales chien",
            "outline": ["A", "B", "C", "D", "E"],
            "shopify_article_handle": "guide-croquettes-sans-cereales-chien",
        },
    ]

    links = suggest_cluster_links(
        current_keyword="croquettes sans céréales chien sensible",
        current_outline=["A"],
        other_drafts=other_drafts,
    )

    assert links == [
        {
            "target_url": "/blogs/blog/guide-croquettes-sans-cereales-chien",
            "anchor": "Le guide complet des croquettes sans céréales pour chien",
            "target_title": "Le guide complet des croquettes sans céréales pour chien",
            "reason": "cluster_pillar",
        }
    ]


def test_suggest_cluster_links_returns_empty_without_similar_draft() -> None:
    other_drafts = [
        {
            "id": "draft-1",
            "blog_title": "Quelle litière choisir pour un chat d'intérieur ?",
            "target_keyword": "litière chat intérieur",
            "outline": ["A"],
            "shopify_article_handle": "litiere-chat-interieur",
        },
    ]

    assert (
        suggest_cluster_links(
            current_keyword="croquettes sans céréales chien sensible",
            current_outline=["A"],
            other_drafts=other_drafts,
        )
        == []
    )


def test_suggest_cluster_links_returns_empty_without_target_keyword() -> None:
    assert (
        suggest_cluster_links(current_keyword="", current_outline=["A"], other_drafts=[{"id": "draft-1"}])
        == []
    )


def test_draft_from_product_adds_source_product_link_without_recommendations() -> None:
    latest = {
        "products": [
            {
                "product_id": "gid://shopify/Product/1",
                "product_title": "Fontaine chat inox",
                "product_handle": "fontaine-chat-inox",
                "content_test_pack": {
                    "proposed_blog_title": "Pourquoi choisir une fontaine chat inox",
                    "proposed_blog_intro": "Intro",
                    "proposed_blog_outline": ["Pourquoi l'inox ?"],
                    "confirmed_facts": [{"key": "material", "value": "inox"}],
                },
            }
        ]
    }

    with patch("app.api.blog.load_latest_result", return_value=latest):
        draft = _draft_from_product("shop.myshopify.com", "gid://shopify/Product/1")

    assert draft["internal_links"] == [
        {
            "target_url": "/products/fontaine-chat-inox",
            "anchor": "Fontaine chat inox",
            "target_title": "Fontaine chat inox",
            "reason": "source_product",
        }
    ]
