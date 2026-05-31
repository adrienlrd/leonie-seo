"""Internal links for generated blog drafts."""

from __future__ import annotations

from unittest.mock import patch

from app.api.blog import BlogSection, _assemble_body_html, _draft_from_product
from app.blog.internal_links import render_internal_links_html, select_blog_internal_links


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
                    "proposed_blog_outline": ["Pourquoi le cuir ?"],
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
            }
        ]
    }

    with patch("app.api.blog.load_latest_result", return_value=latest):
        draft = _draft_from_product("shop.myshopify.com", "gid://shopify/Product/1")

    assert draft["internal_links"] == [
        {
            "target_url": "/collections/chien",
            "anchor": "accessoires chien",
            "target_title": "Collection chien",
            "reason": "collection_parent",
        }
    ]
