"""JSON-LD generators: Article + FAQPage."""

from __future__ import annotations

import json

from app.blog.schema import build_article_jsonld, build_faqpage_jsonld, render_jsonld_blocks


def test_article_jsonld_defaults_to_organization_author():
    ld = build_article_jsonld(
        headline="Comment choisir une fontaine à chat",
        description="Guide complet 2026",
        url="https://example.com/blogs/blog/fontaine-chat",
        publisher_name="Léonie Delacroix",
    )
    assert ld["@type"] == "Article"
    assert ld["author"]["@type"] == "Organization"
    assert ld["author"]["name"] == "Léonie Delacroix"
    assert ld["publisher"]["name"] == "Léonie Delacroix"
    assert ld["mainEntityOfPage"]["@id"].endswith("fontaine-chat")
    assert "datePublished" in ld and "dateModified" in ld


def test_article_jsonld_supports_person_author_for_eeat():
    ld = build_article_jsonld(
        headline="x",
        description="y",
        url="https://example.com",
        author_type="Person",
        author_name="Adrien Lerédé",
        author_url="https://example.com/about",
        publisher_name="Léonie Delacroix",
    )
    assert ld["author"]["@type"] == "Person"
    assert ld["author"]["url"] == "https://example.com/about"


def test_faqpage_jsonld_filters_empty_pairs():
    ld = build_faqpage_jsonld(
        [
            {"question": "Comment nettoyer ?", "answer": "Démontez et rincez chaque semaine."},
            {"question": "", "answer": "ignored"},
            {"question": "ignored", "answer": ""},
        ]
    )
    assert ld is not None
    assert len(ld["mainEntity"]) == 1
    assert ld["mainEntity"][0]["@type"] == "Question"
    assert ld["mainEntity"][0]["acceptedAnswer"]["text"].startswith("Démontez")


def test_render_jsonld_blocks_skips_none():
    out = render_jsonld_blocks({"@type": "Thing"}, None, {"@type": "Other"})
    assert out.count("<script") == 2
    # Both blocks must be valid JSON inside the script tags
    fragments = out.split("</script>")
    for frag in fragments:
        if "<script" not in frag:
            continue
        payload = frag.split(">", 1)[1]
        json.loads(payload)
