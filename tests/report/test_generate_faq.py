"""Tests for scripts.report.generate_faq."""

from scripts.report.generate_faq import (
    build_json_ld,
    generate_faq,
    render_markdown,
)

_ALL_CATEGORIES = ["vetements_chien", "vetements_chat", "fontaines", "filtres", "accessoires"]


def test_generate_faq_returns_list_for_known_category():
    faq = generate_faq("vetements_chien")
    assert isinstance(faq, list)
    assert len(faq) >= 3


def test_generate_faq_returns_empty_for_unknown_category():
    faq = generate_faq("categorie_inconnue")
    assert faq == []


def test_generate_faq_all_items_have_q_and_a():
    for category in _ALL_CATEGORIES:
        for item in generate_faq(category):
            assert "q" in item and item["q"], f"{category}: missing question"
            assert "a" in item and item["a"], f"{category}: missing answer"


def test_generate_faq_answers_not_empty():
    for category in _ALL_CATEGORIES:
        for item in generate_faq(category):
            assert len(item["a"]) > 50, f"{category}: answer too short"


def test_generate_faq_fontaines_mentions_veterinaire():
    faq = generate_faq("fontaines")
    all_text = " ".join(item["a"] for item in faq).lower()
    assert "vétérinaire" in all_text


def test_generate_faq_vetements_chien_mentions_france():
    faq = generate_faq("vetements_chien")
    all_text = " ".join(item["a"] for item in faq).lower()
    assert "france" in all_text


def test_generate_faq_accessoires_mentions_ceramique_or_inox():
    faq = generate_faq("accessoires")
    all_text = " ".join(item["a"] for item in faq).lower()
    assert "céramique" in all_text or "inox" in all_text


def test_build_json_ld_structure():
    faq = [{"q": "Question test ?", "a": "Réponse test."}]
    ld = build_json_ld(faq)
    assert ld["@type"] == "FAQPage"
    assert ld["@context"] == "https://schema.org"
    assert len(ld["mainEntity"]) == 1


def test_build_json_ld_question_fields():
    faq = [{"q": "Question ?", "a": "Réponse."}]
    ld = build_json_ld(faq)
    entity = ld["mainEntity"][0]
    assert entity["@type"] == "Question"
    assert entity["name"] == "Question ?"
    assert entity["acceptedAnswer"]["@type"] == "Answer"
    assert entity["acceptedAnswer"]["text"] == "Réponse."


def test_build_json_ld_multiple_questions():
    faq = generate_faq("fontaines")
    ld = build_json_ld(faq)
    assert len(ld["mainEntity"]) == len(faq)


def test_render_markdown_has_date():
    md = render_markdown({}, "2026-05-08")
    assert "2026-05-08" in md


def test_render_markdown_has_all_categories():
    faqs = {cat: generate_faq(cat) for cat in _ALL_CATEGORIES}
    md = render_markdown(faqs, "2026-05-08")
    assert "Vêtements pour chien" in md
    assert "Fontaines" in md
    assert "Accessoires" in md


def test_render_markdown_questions_appear_in_output():
    faq = generate_faq("vetements_chien")
    md = render_markdown({"vetements_chien": faq}, "2026-05-08")
    assert faq[0]["q"] in md


def test_render_markdown_answers_appear_in_output():
    faq = generate_faq("filtres")
    md = render_markdown({"filtres": faq}, "2026-05-08")
    assert "charbon actif" in md or "filtre" in md.lower()


def test_render_markdown_has_json_ld_mention():
    md = render_markdown({}, "2026-05-08")
    assert "JSON-LD" in md or "json" in md.lower()


def test_total_question_count():
    total = sum(len(generate_faq(cat)) for cat in _ALL_CATEGORIES)
    assert total >= 18
