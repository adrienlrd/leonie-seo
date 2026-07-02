"""Tests for scripts.apply.rewrite_descriptions."""

from scripts.apply.rewrite_descriptions import (
    build_description,
    classify_product,
    strip_html,
)


def test_classify_product_vetements_chien():
    assert classify_product("Le Pardessus Pour Chien", "") == "vetements_chien"


def test_classify_product_vetements_chat():
    assert classify_product("Le Pardessus Pour Chat", "") == "vetements_chat"


def test_classify_product_tour_de_cou_chien():
    assert classify_product("Le Tour De Cou Pour Chien", "") == "vetements_chien"


def test_classify_product_tour_de_cou_chat():
    assert classify_product("Le Tour De Cou Pour Chat", "") == "vetements_chat"


def test_classify_product_fontaine():
    assert (
        classify_product("La Fontaine Smart - Fontaine à eau sans fil pour chat", "") == "fontaines"
    )


def test_classify_product_abreuvoir():
    assert classify_product("L'abreuvoir", "") == "fontaines"


def test_classify_product_filtres():
    assert classify_product("Pack de 5 Filtres Puissants pour l'Abreuvoir", "") == "filtres"


def test_classify_product_pompe():
    assert classify_product("Pompe pour l'abreuvoir", "") == "filtres"


def test_classify_product_accessoires_fallback():
    assert classify_product("Le Raisonnable", "") == "accessoires"


def test_classify_product_uses_description_fallback():
    assert classify_product("Produit mystère", "griffoir pour chat appartement") == "accessoires"


def test_build_description_contains_title():
    desc = build_description("Le Pardessus Pour Chien", "vetements_chien", "Acme Pets")
    assert "Le Pardessus Pour Chien" in desc


def test_build_description_word_count_above_minimum():
    for category in ("vetements_chien", "vetements_chat", "fontaines", "filtres", "accessoires"):
        desc = build_description("Produit test", category, "Acme Pets")
        word_count = len(desc.split())
        assert word_count >= 100, f"{category}: only {word_count} words"


def test_build_description_has_four_paragraphs():
    desc = build_description("Test", "fontaines", "Acme Pets")
    assert desc.count("\n\n") >= 3


def test_build_description_fontaines_mentions_veterinaire():
    desc = build_description("L'abreuvoir", "fontaines", "Acme Pets")
    assert "vétérinaire" in desc.lower()


def test_build_description_vetements_chien_mentions_france():
    desc = build_description("Le Pardessus Pour Chien", "vetements_chien", "Acme Pets")
    assert "france" in desc.lower() or "France" in desc


def test_strip_html_removes_tags():
    assert strip_html("<p>Bonjour <b>monde</b></p>") == "Bonjour monde"


def test_strip_html_handles_none():
    assert strip_html(None) == ""


def test_strip_html_handles_empty():
    assert strip_html("") == ""
