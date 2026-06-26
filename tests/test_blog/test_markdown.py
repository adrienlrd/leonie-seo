"""Tests for the LLM-body Markdown → HTML renderer."""

from __future__ import annotations

from app.blog.markdown import render_inline_markdown, render_markdown


def test_bold_becomes_strong() -> None:
    assert render_inline_markdown("Le **Confort** avant tout") == "Le <strong>Confort</strong> avant tout"


def test_italic_variants() -> None:
    assert "<em>doux</em>" in render_inline_markdown("un tissu *doux*")
    assert "<em>doux</em>" in render_inline_markdown("un tissu _doux_")


def test_link_conversion() -> None:
    out = render_inline_markdown("Voir [le produit](/products/harnais)")
    assert '<a href="/products/harnais">le produit</a>' in out


def test_html_is_escaped_before_conversion() -> None:
    out = render_inline_markdown("2 < 3 & <script>alert(1)</script>")
    assert "<script>" not in out
    assert "&lt;script&gt;" in out


def test_bullet_list_block() -> None:
    md = "Avantages :\n- Confort\n- Solidité\n- Lavable"
    out = render_markdown(md)
    assert "<ul>" in out
    assert out.count("<li>") == 3
    assert "<li>Confort</li>" in out


def test_numbered_list_block() -> None:
    out = render_markdown("1. Mesurer\n2. Choisir la taille")
    assert "<ol>" in out
    assert out.count("<li>") == 2


def test_paragraphs_separated_by_blank_line() -> None:
    out = render_markdown("Premier paragraphe.\n\nDeuxième paragraphe.")
    assert out.count("<p>") == 2


def test_bold_inside_body_paragraph() -> None:
    out = render_markdown("Le **Confort** est clé.")
    assert "<p>Le <strong>Confort</strong> est clé.</p>" == out


def test_empty_returns_empty() -> None:
    assert render_markdown("") == ""
    assert render_markdown("   \n  ") == ""
