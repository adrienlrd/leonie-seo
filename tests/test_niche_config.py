"""Tests for NicheConfig loading and niche YAML content."""

from __future__ import annotations

import pytest

from scripts._config import NicheConfig, load_niche, reset_config_cache


@pytest.fixture(autouse=True)
def clear_cache():
    reset_config_cache()
    yield
    reset_config_cache()


# ── load_niche ────────────────────────────────────────────────────────────


def test_load_niche_pet_accessories_fr():
    niche = load_niche("pet_accessories_fr")
    assert niche.niche_id == "pet_accessories_fr"
    assert isinstance(niche, NicheConfig)


def test_load_niche_unknown_raises_file_not_found():
    with pytest.raises(FileNotFoundError):
        load_niche("niche_inconnue_xyz")


def test_load_niche_cache_returns_same_instance():
    n1 = load_niche("pet_accessories_fr")
    n2 = load_niche("pet_accessories_fr")
    assert n1 is n2


def test_reset_cache_invalidates_niche():
    n1 = load_niche("pet_accessories_fr")
    reset_config_cache()
    n2 = load_niche("pet_accessories_fr")
    assert n1 is not n2


# ── Signals ───────────────────────────────────────────────────────────────


def test_niche_signals_premium_not_empty():
    niche = load_niche("pet_accessories_fr")
    assert len(niche.signals.premium) > 5


def test_niche_signals_eeat_contains_veterinaire():
    niche = load_niche("pet_accessories_fr")
    assert "vétérinaires" in niche.signals.eeat or "vétérinaire" in niche.signals.eeat


def test_niche_signals_longtail_not_empty():
    niche = load_niche("pet_accessories_fr")
    assert len(niche.signals.longtail) > 5


def test_niche_signals_category_has_all_categories():
    niche = load_niche("pet_accessories_fr")
    for cat in ("vetements_chien", "vetements_chat", "fontaines", "filtres", "accessoires"):
        assert cat in niche.signals.category, f"Missing category: {cat}"


# ── EEAT dimensions ───────────────────────────────────────────────────────


def test_niche_eeat_experience_has_nous_avons_teste():
    niche = load_niche("pet_accessories_fr")
    assert "nous avons testé" in niche.eeat_dimensions.experience


def test_niche_eeat_expertise_has_veterinaire():
    niche = load_niche("pet_accessories_fr")
    assert "vétérinaire" in niche.eeat_dimensions.expertise


def test_niche_eeat_authority_has_made_in_france():
    niche = load_niche("pet_accessories_fr")
    assert "fabriqué en france" in niche.eeat_dimensions.authority


def test_niche_eeat_trust_has_garantie():
    niche = load_niche("pet_accessories_fr")
    assert "garantie" in niche.eeat_dimensions.trust


def test_niche_eeat_weights_sum_to_one():
    niche = load_niche("pet_accessories_fr")
    total = sum(niche.eeat_dimensions.weights.values())
    assert abs(total - 1.0) < 1e-6


# ── FAQ templates ─────────────────────────────────────────────────────────


def test_niche_faq_has_all_categories():
    niche = load_niche("pet_accessories_fr")
    for cat in ("vetements_chien", "vetements_chat", "fontaines", "filtres", "accessoires"):
        assert cat in niche.faq_templates, f"Missing FAQ category: {cat}"


def test_niche_faq_fontaines_mentions_veterinaire():
    niche = load_niche("pet_accessories_fr")
    all_text = " ".join(item["a"] for item in niche.faq_templates.get("fontaines", [])).lower()
    assert "vétérinaire" in all_text


def test_niche_faq_vetements_chien_mentions_france():
    niche = load_niche("pet_accessories_fr")
    all_text = " ".join(
        item["a"] for item in niche.faq_templates.get("vetements_chien", [])
    ).lower()
    assert "france" in all_text


def test_niche_faq_accessoires_mentions_ceramique_or_inox():
    niche = load_niche("pet_accessories_fr")
    all_text = " ".join(item["a"] for item in niche.faq_templates.get("accessoires", [])).lower()
    assert "céramique" in all_text or "inox" in all_text


# ── Blog templates ────────────────────────────────────────────────────────


def test_niche_blog_templates_has_informational():
    niche = load_niche("pet_accessories_fr")
    assert "informational" in niche.blog_templates


def test_niche_blog_templates_informational_h2s_not_empty():
    niche = load_niche("pet_accessories_fr")
    assert len(niche.blog_templates["informational"].h2s) >= 3


def test_niche_blog_templates_vetements_chien_has_intent():
    niche = load_niche("pet_accessories_fr")
    template = niche.blog_templates.get("vetements_chien")
    assert template is not None
    assert template.intent != ""


# ── Other niche stubs load correctly ─────────────────────────────────────


def test_load_niche_cosmetics_fr():
    niche = load_niche("cosmetics_fr")
    assert niche.niche_id == "cosmetics_fr"
    assert len(niche.signals.premium) > 0


def test_load_niche_mode_fr():
    niche = load_niche("mode_fr")
    assert niche.niche_id == "mode_fr"
    assert len(niche.eeat_dimensions.expertise) > 0


def test_load_niche_jardinage_fr():
    niche = load_niche("jardinage_fr")
    assert niche.niche_id == "jardinage_fr"
    assert len(niche.blog_templates) > 0
