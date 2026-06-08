"""Auto-generated alt text for the blog draft cover image."""

from __future__ import annotations

from app.api.blog import _apply_image_alt, _default_blog_image_alt


def test_default_blog_image_alt_appends_keyword_when_absent_from_title() -> None:
    alt = _default_blog_image_alt("Le guide complet pour bien choisir", "croquettes sans céréales")

    assert alt == "Le guide complet pour bien choisir – croquettes sans céréales"


def test_default_blog_image_alt_does_not_duplicate_keyword_already_in_title() -> None:
    alt = _default_blog_image_alt("Croquettes sans céréales : le guide complet", "croquettes sans céréales")

    assert alt == "Croquettes sans céréales : le guide complet"


def test_default_blog_image_alt_truncates_to_125_chars() -> None:
    long_title = "Le guide ultra complet et détaillé pour bien choisir ses croquettes au quotidien sans se tromper"
    alt = _default_blog_image_alt(long_title, "croquettes sans céréales pour chien sensible")

    assert len(alt) <= 125


def test_apply_image_alt_generates_text_when_image_set_and_alt_missing() -> None:
    draft = {
        "blog_title": "Croquettes sans céréales : le guide complet",
        "target_keyword": "croquettes sans céréales",
        "image_url": "https://cdn.shopify.com/cover.jpg",
    }

    _apply_image_alt(draft)

    assert draft["image_alt"] == "Croquettes sans céréales : le guide complet"


def test_apply_image_alt_does_not_overwrite_existing_alt_text() -> None:
    draft = {
        "blog_title": "Croquettes sans céréales : le guide complet",
        "target_keyword": "croquettes sans céréales",
        "image_url": "https://cdn.shopify.com/cover.jpg",
        "image_alt": "Texte personnalisé du marchand",
    }

    _apply_image_alt(draft)

    assert draft["image_alt"] == "Texte personnalisé du marchand"


def test_apply_image_alt_clears_alt_text_when_image_removed() -> None:
    draft = {
        "blog_title": "Croquettes sans céréales : le guide complet",
        "image_url": "",
        "image_alt": "Ancien texte généré",
    }

    _apply_image_alt(draft)

    assert "image_alt" not in draft
