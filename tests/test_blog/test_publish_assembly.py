"""Tests for blog publish HTML assembly: reading time, TOC, FAQ, author bio, meta."""

from __future__ import annotations

from app.api.blog import (
    BlogSection,
    _author_bio_html,
    _faq_html,
    _reading_time_html,
    _reading_time_minutes,
    _toc_html,
)


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
