"""Tests for blog publish HTML assembly: reading time, TOC, FAQ, author bio, meta."""

from __future__ import annotations

from app.api.blog import (
    BlogSection,
    _assemble_body_html,
    _author_bio_html,
    _cover_image_html,
    _cta_html,
    _faq_html,
    _reading_time_html,
    _reading_time_minutes,
    _toc_html,
    _truncate_clean,
)
from app.blog.schema import build_article_jsonld, build_howto_jsonld


def test_reading_time_floors_at_one_minute() -> None:
    assert _reading_time_minutes(10) == 1
    assert _reading_time_minutes(400) == 2
    assert "min de lecture" in _reading_time_html(400)


def test_toc_lists_sections_with_anchors() -> None:
    sections = [
        BlogSection(h2="Première question", direct_answer="", body=""),
        BlogSection(h2="Deuxième question", direct_answer="", body=""),
    ]
    html = _toc_html(sections)
    assert "Sommaire" in html
    assert 'href="#section-0"' in html
    assert 'href="#section-1"' in html
    assert "Première question" in html


def test_toc_empty_when_no_sections() -> None:
    assert _toc_html([]) == ""


def test_faq_html_renders_pairs_and_skips_incomplete() -> None:
    html = _faq_html([{"q": "Question ?", "a": "Réponse."}, {"q": "Sans réponse", "a": ""}])
    assert "Questions fréquentes" in html
    assert "Question ?" in html
    assert "Sans réponse" not in html


def test_author_bio_html_only_when_bio_present() -> None:
    assert _author_bio_html("Léonie", "") == ""
    html = _author_bio_html("Léonie", "Experte en soin animalier depuis 10 ans.")
    assert "À propos de l'auteur" in html
    assert "Léonie" in html


def test_cta_html_renders_button_with_url_and_label() -> None:
    html = _cta_html("Découvrir le produit", "/products/harnais", "Le meilleur pour votre chien.")
    assert "leonie-cta" in html
    assert 'href="/products/harnais"' in html
    assert "Découvrir le produit" in html
    assert "Le meilleur pour votre chien." in html


def test_cta_html_empty_without_url_or_label() -> None:
    assert _cta_html("", "/x", "") == ""
    assert _cta_html("Label", "", "") == ""


def test_assemble_body_html_numbered_steps_and_section_image() -> None:
    sections = [
        BlogSection(h2="Première étape", direct_answer="Fais ceci.", body="Détails.", image_url="https://cdn/a.jpg", image_alt="A"),
        BlogSection(h2="Deuxième étape", direct_answer="Puis cela.", body="Détails."),
    ]
    html = _assemble_body_html("Intro", sections, [], numbered_steps=True)
    assert "1. Première étape" in html
    assert "2. Deuxième étape" in html
    assert 'src="https://cdn/a.jpg"' in html


def test_assemble_body_html_no_numbering_by_default() -> None:
    sections = [BlogSection(h2="Titre", direct_answer="X", body="Y")]
    html = _assemble_body_html("Intro", sections, [])
    assert "1. Titre" not in html
    assert '<h2 id="section-0">Titre</h2>' in html


def test_howto_jsonld_from_numbered_sections() -> None:
    ld = build_howto_jsonld(
        name="Guide harnais",
        description="Comment choisir.",
        sections=[
            {"name": "Mesurer", "text": "Prendre le tour de poitrine."},
            {"name": "Choisir la taille", "text": "Comparer au guide."},
        ],
    )
    assert ld is not None
    assert ld["@type"] == "HowTo"
    assert len(ld["step"]) == 2
    assert ld["step"][0]["position"] == 1
    assert ld["step"][1]["name"] == "Choisir la taille"


def test_howto_jsonld_none_with_single_step() -> None:
    assert build_howto_jsonld(name="X", description="Y", sections=[{"name": "Un", "text": "seul"}]) is None


def test_article_jsonld_person_emits_sameas_and_bio() -> None:
    ld = build_article_jsonld(
        headline="T",
        description="D",
        url="https://shop/blogs/blog/t",
        author_type="Person",
        author_name="Léonie",
        author_url="https://linkedin.com/in/leonie",
        author_bio="Experte soin animalier.",
    )
    assert ld["author"]["@type"] == "Person"
    assert ld["author"]["sameAs"] == ["https://linkedin.com/in/leonie"]
    assert ld["author"]["description"] == "Experte soin animalier."


def test_article_jsonld_organization_no_sameas() -> None:
    ld = build_article_jsonld(
        headline="T", description="D", url="https://shop/x",
        author_type="Organization", author_name="Marque", author_url="https://shop",
    )
    assert "sameAs" not in ld["author"]


def test_create_article_includes_meta_description_metafield() -> None:
    from app.blog.shopify_articles import BlogPublisher

    publisher = BlogPublisher("shop.myshopify.com", "token")
    captured: dict = {}

    def fake_post(query, variables):  # noqa: ANN001
        captured["variables"] = variables
        return {"data": {"articleCreate": {"article": {"id": "gid://x/1", "handle": "h"}, "userErrors": []}}}

    publisher._post = fake_post  # type: ignore[method-assign]
    publisher.create_draft_article(
        blog_id="gid://shopify/Blog/1",
        title="T",
        body_html="<p>x</p>",
        meta_description="Une meta description SEO pour Google.",
    )
    metafields = captured["variables"]["article"]["metafields"]
    assert metafields[0]["namespace"] == "global"
    assert metafields[0]["key"] == "description_tag"
    assert "meta description SEO" in metafields[0]["value"]


def test_truncate_clean_no_midword_cut() -> None:
    text = "Choisir un harnais pour chien confortable et solide adapté à toutes les tailles de races"
    out = _truncate_clean(text, 40)
    assert len(out) <= 41  # +1 for the ellipsis
    assert out.endswith("…")
    assert " " not in out[-2:]  # did not cut mid-word right before ellipsis
    assert not out.rstrip("…").endswith(" ")


def test_truncate_clean_keeps_short_text() -> None:
    assert _truncate_clean("Court texte", 100) == "Court texte"


def test_cover_image_html_renders_and_empty() -> None:
    assert _cover_image_html("", "", "Titre") == ""
    html = _cover_image_html("https://cdn/x.jpg", "Un chien", "Titre")
    assert 'src="https://cdn/x.jpg"' in html
    assert 'alt="Un chien"' in html


def test_cover_image_html_applies_style() -> None:
    banner = _cover_image_html("https://cdn/x.jpg", "", "T", "banner")
    assert "height:220px" in banner
    float_left = _cover_image_html("https://cdn/x.jpg", "", "T", "float-left")
    assert "float:left" in float_left
    # Unknown style falls back to hero.
    hero = _cover_image_html("https://cdn/x.jpg", "", "T", "weird")
    assert "max-height:420px" in hero


def test_update_article_uses_articleupdate_mutation() -> None:
    from app.blog.shopify_articles import BlogPublisher

    publisher = BlogPublisher("shop.myshopify.com", "token")
    captured: dict = {}

    def fake_post(query, variables):  # noqa: ANN001
        captured["query"] = query
        captured["variables"] = variables
        return {"data": {"articleUpdate": {"article": {"id": "gid://x/1", "handle": "h"}, "userErrors": []}}}

    publisher._post = fake_post  # type: ignore[method-assign]
    updated = publisher.update_article(
        article_id="gid://shopify/Article/1",
        title="T",
        body_html="<p>x</p>",
        published=True,
    )
    assert "articleUpdate" in captured["query"]
    assert captured["variables"]["id"] == "gid://shopify/Article/1"
    assert "blogId" not in captured["variables"]["article"]  # blog fixed once created
    assert captured["variables"]["article"]["isPublished"] is True
    assert updated["id"] == "gid://x/1"


def test_create_article_draft_by_default_and_live_when_published() -> None:
    from app.blog.shopify_articles import BlogPublisher

    publisher = BlogPublisher("shop.myshopify.com", "token")
    captured: dict = {}

    def fake_post(query, variables):  # noqa: ANN001
        captured["variables"] = variables
        return {"data": {"articleCreate": {"article": {"id": "gid://x/1", "handle": "h"}, "userErrors": []}}}

    publisher._post = fake_post  # type: ignore[method-assign]

    publisher.create_draft_article(blog_id="gid://shopify/Blog/1", title="T", body_html="<p>x</p>")
    assert captured["variables"]["article"]["isPublished"] is False

    publisher.create_draft_article(blog_id="gid://shopify/Blog/1", title="T", body_html="<p>x</p>", published=True)
    assert captured["variables"]["article"]["isPublished"] is True
