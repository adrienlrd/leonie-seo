"""Tests for scripts.report.score_eeat."""

from scripts.report.score_eeat import render_markdown, score_page


def _product(title: str, description: str = "") -> dict:
    return {"handle": title.lower().replace(" ", "-"), "title": title, "description": description}


# ── score_page ─────────────────────────────────────────────────────────────


def test_score_page_returns_all_keys():
    result = score_page(_product("Test Product"))
    for key in ("global_score", "experience_score", "expertise_score", "authority_score", "trust_score"):
        assert key in result


def test_score_page_empty_description_gives_low_scores():
    result = score_page(_product("Produit", ""))
    assert result["global_score"] < 0.1


def test_score_page_expertise_detects_veterinaire():
    result = score_page(_product("Fontaine", "Recommandé par les vétérinaires pour une bonne hydratation."))
    assert result["expertise_score"] > 0


def test_score_page_authority_detects_made_in_france():
    result = score_page(_product("Manteau", "Fabriqué en France par nos couturières expertes."))
    assert result["authority_score"] > 0


def test_score_page_trust_detects_garantie():
    result = score_page(_product("Bol", "Garantie 2 ans. Inox 304. Sans BPA."))
    assert result["trust_score"] > 0


def test_score_page_experience_detects_nous_avons_teste():
    result = score_page(_product("Griffoir", "Nous avons testé ce griffoir avec nos animaux au quotidien."))
    assert result["experience_score"] > 0


def test_score_page_global_score_between_0_and_1():
    result = score_page(_product("Produit", "Vétérinaire recommandé. Fabriqué en France. Garantie 2 ans."))
    assert 0.0 <= result["global_score"] <= 1.0


def test_score_page_rich_description_scores_higher():
    poor = score_page(_product("A", "Manteau pour chien."))
    rich = score_page(_product("B", (
        "Recommandé par les vétérinaires. Fabriqué en France par nos couturières. "
        "Certifié sans substances nocives. Garantie satisfait ou remboursé. "
        "Nos clients adorent ce produit. Testé sur nos animaux."
    )))
    assert rich["global_score"] > poor["global_score"]


def test_score_page_missing_signals_are_lists():
    result = score_page(_product("Produit", "description courte"))
    assert isinstance(result["top_missing_expertise"], list)
    assert isinstance(result["top_missing_authority"], list)
    assert isinstance(result["top_missing_trust"], list)


def test_score_page_description_words_count():
    result = score_page(_product("Produit", "un deux trois quatre cinq"))
    assert result["description_words"] == 5


# ── render_markdown ────────────────────────────────────────────────────────


def test_render_markdown_has_date():
    md = render_markdown([], "2026-05-08")
    assert "2026-05-08" in md


def test_render_markdown_empty_products():
    md = render_markdown([], "2026-05-08")
    assert "Aucun produit analysé" in md


def test_render_markdown_shows_product_title():
    results = [score_page(_product("Fontaine Smart", "Recommandé par les vétérinaires."))]
    md = render_markdown(results, "2026-05-08")
    assert "Fontaine Smart" in md


def test_render_markdown_has_eeat_sections():
    results = [score_page(_product("Produit A", "courte description"))]
    md = render_markdown(results, "2026-05-08")
    assert "Expertise" in md
    assert "Autorité" in md or "Authoritativeness" in md or "Authority" in md


def test_render_markdown_global_recommendations_present():
    md = render_markdown([], "2026-05-08")
    assert "Recommandations" in md or "recommandations" in md or "Aucun produit" in md
