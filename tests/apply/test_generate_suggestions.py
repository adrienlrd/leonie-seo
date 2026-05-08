"""Tests for scripts.apply.generate_suggestions."""

from scripts._config import get_config
from scripts.apply.generate_suggestions import (
    build_alt_suggestions,
    build_meta_suggestions,
    suggest_alt_text,
    suggest_meta_description,
    suggest_meta_title,
)

_cfg = get_config()
BRAND = _cfg.brand
TITLE_MIN = _cfg.seo_rules.title_min_chars
TITLE_MAX = _cfg.seo_rules.title_max_chars
DESC_MIN = _cfg.seo_rules.description_min_chars
DESC_MAX = _cfg.seo_rules.description_max_chars

# ── Meta title ────────────────────────────────────────────────────────────────


def test_suggest_meta_title_already_set_in_range():
    existing = "Titre existant bien long pour le SEO | Léonie Delacroix"
    result = suggest_meta_title("Autre", "chien", existing=existing)
    assert result["value"] == existing
    assert not result["is_review_needed"]


def test_suggest_meta_title_already_set_too_short():
    existing = "Titre court | Léonie Delacroix"
    result = suggest_meta_title("Autre", "chien", existing=existing)
    assert result["value"] == existing
    assert result["is_review_needed"]


def test_suggest_meta_title_fixes_old_brand():
    existing = "Harnais en Cuir pour Chien | Léonie de la Croix"
    result = suggest_meta_title("Harnais en Cuir pour Chien", "chien", existing=existing)
    assert "Léonie Delacroix" in result["value"]
    assert "Léonie de la Croix" not in result["value"]


def test_suggest_meta_title_english_flagged():
    result = suggest_meta_title("Pet drinking machine for dog and cat", "animal")
    assert result["value"] is None
    assert result["is_review_needed"]


def test_suggest_meta_title_ideal_length():
    # "Distributeur Automatique pour Chat | Léonie Delacroix" = 53 chars ✓
    result = suggest_meta_title("Distributeur Automatique pour Chat", "chat")
    assert result["value"] is not None
    assert BRAND in result["value"]
    assert TITLE_MIN <= len(result["value"]) <= TITLE_MAX


def test_suggest_meta_title_short_gets_extended():
    # Short title → qualifier added
    result = suggest_meta_title("Arbre Boho", "chat")
    assert result["value"] is not None
    assert BRAND in result["value"]


def test_suggest_meta_title_long_gets_truncated():
    long_title = "Pack de 5 Filtres Puissants pour l'Abreuvoir Automatique Premium Deluxe"
    result = suggest_meta_title(long_title, "animal")
    assert result["value"] is not None
    assert len(result["value"]) <= TITLE_MAX
    assert result["is_review_needed"]


# ── Meta description ──────────────────────────────────────────────────────────


def test_suggest_meta_description_generates_valid_template():
    result = suggest_meta_description("Le Pardessus Pour Chien", "chien")
    assert result["value"] is not None
    assert DESC_MIN <= len(result["value"]) <= DESC_MAX
    assert BRAND in result["value"]


def test_suggest_meta_description_uses_long_existing():
    existing = "Une description suffisamment longue pour être valide en SEO, bien rédigée." * 2
    existing = existing[:130].strip()
    result = suggest_meta_description("Prod", "chien", existing=existing)
    assert result["value"] == existing
    assert not result["is_review_needed"]


def test_suggest_meta_description_truncates_too_long_existing():
    existing = "A" * 200
    result = suggest_meta_description("Prod", "chien", existing=existing)
    assert len(result["value"]) <= DESC_MAX
    assert result["is_review_needed"]


def test_suggest_meta_description_english_flagged():
    result = suggest_meta_description("Pet clothing for keeping warm windproof", "animal")
    assert result["value"] is None
    assert result["is_review_needed"]


# ── Alt text ──────────────────────────────────────────────────────────────────


def test_suggest_alt_text_first_image():
    result = suggest_alt_text("Le Pardessus Pour Chien", 0)
    assert BRAND in result
    assert len(result) <= 125
    assert "vue" not in result


def test_suggest_alt_text_subsequent_image():
    result = suggest_alt_text("Arbre à chat Boho", 2)
    assert "vue 3" in result
    assert len(result) <= 125


def test_suggest_alt_text_very_long_title():
    long_title = "T" * 120
    result = suggest_alt_text(long_title, 0)
    assert len(result) <= 125


# ── build helpers ─────────────────────────────────────────────────────────────


def test_build_alt_suggestions_only_missing():
    products = [
        {
            "id": "gid://shopify/Product/1",
            "title": "Test Produit",
            "images": {
                "edges": [
                    {"node": {"id": "img1", "url": "http://img1", "altText": None}},
                    {"node": {"id": "img2", "url": "http://img2", "altText": "already set"}},
                ]
            },
        }
    ]
    suggestions = build_alt_suggestions(products)
    assert len(suggestions) == 1
    assert suggestions[0]["image_id"] == "img1"
    assert BRAND in suggestions[0]["new_alt"]


def test_build_meta_suggestions_skips_english_products():
    products = [
        {
            "id": "gid://shopify/Product/1",
            "title": "Pet drinking machine for cat and dog",
            "seo": {"title": None, "description": None},
            "images": {"edges": []},
            "collections": {"edges": []},
        }
    ]
    suggestions = build_meta_suggestions(products, [])
    # English name → both value=None → skipped
    assert len(suggestions) == 0


def test_build_meta_suggestions_includes_valid_products():
    products = [
        {
            "id": "gid://shopify/Product/2",
            "title": "Le Pardessus Pour Chien",
            "seo": {"title": None, "description": None},
            "images": {"edges": []},
            "collections": {"edges": [{"node": {"title": "Chien"}}]},
        }
    ]
    suggestions = build_meta_suggestions(products, [])
    assert len(suggestions) == 1
    assert suggestions[0]["new_title"] is not None
    assert BRAND in suggestions[0]["new_title"]


def test_build_meta_suggestions_skips_home_page_collection():
    collections = [
        {
            "id": "gid://shopify/Collection/1",
            "title": "Home page",
            "seo": {"title": None, "description": None},
        }
    ]
    suggestions = build_meta_suggestions([], collections)
    assert len(suggestions) == 0
