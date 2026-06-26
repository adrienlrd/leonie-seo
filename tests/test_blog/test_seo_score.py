"""Tests for the blog article GEO/SEO readiness score."""

from __future__ import annotations

from app.blog.seo_score import score_blog_readiness


def _rich_draft() -> dict:
    return {
        "blog_title": "Bien choisir un harnais pour chien",
        "target_keyword": "harnais pour chien",
        "intro": "Choisir un harnais pour chien dépend de la taille et de l'activité. " * 3,
        "meta_description": "Guide complet pour choisir un harnais pour chien adapté à la taille, "
        "au confort et à la sécurité de votre animal au quotidien.",
        "sections": [
            {"h2": "Quel harnais pour chien choisir ?", "direct_answer": "Un harnais ajustable.", "body": "Texte " * 200},
            {"h2": "Comment mesurer son chien ?", "direct_answer": "Tour de poitrine.", "body": "Texte " * 200},
            {"h2": "Harnais ou collier ?", "direct_answer": "Le harnais répartit mieux.", "body": "Texte " * 200},
        ],
        "faq": [{"q": "Q1", "a": "A1"}, {"q": "Q2", "a": "A2"}],
        "internal_links": [{"target_url": "/a", "anchor": "x"}, {"target_url": "/b", "anchor": "y"}],
        "image_url": "https://cdn/img.jpg",
    }


def test_rich_draft_scores_high() -> None:
    res = score_blog_readiness(_rich_draft())
    assert res["readiness_score"] >= 80
    assert res["word_count"] > 500
    assert set(res["components"]) == {
        "content_length",
        "keyword",
        "structure",
        "meta_description",
        "faq",
        "internal_links",
        "image",
    }
    for pillar in res["components"].values():
        assert 0 <= pillar["score"] <= 100
        assert 0 < pillar["weight"] <= 1


def test_empty_draft_scores_low() -> None:
    res = score_blog_readiness({"blog_title": "Titre", "sections": []})
    assert res["readiness_score"] < 30


def test_weights_sum_to_one() -> None:
    res = score_blog_readiness(_rich_draft())
    total = sum(c["weight"] for c in res["components"].values())
    assert abs(total - 1.0) < 1e-9


def test_meta_description_length_gate() -> None:
    base = {"blog_title": "T", "sections": []}
    too_short = score_blog_readiness({**base, "meta_description": "court"})
    good = score_blog_readiness(
        {**base, "meta_description": "Une meta description bien calibree entre soixante-dix "
        "et cent cinquante-cinq caracteres pour Google search."}
    )
    assert good["components"]["meta_description"]["score"] > too_short["components"]["meta_description"]["score"]


def test_keyword_placement_rewards_title_intro_h2() -> None:
    no_kw = score_blog_readiness({"blog_title": "Titre", "target_keyword": "harnais chien", "sections": []})
    with_kw = score_blog_readiness(
        {
            "blog_title": "harnais chien parfait",
            "target_keyword": "harnais chien",
            "intro": "le harnais chien ideal",
            "sections": [{"h2": "harnais chien et taille", "direct_answer": "", "body": ""}],
        }
    )
    assert with_kw["components"]["keyword"]["score"] > no_kw["components"]["keyword"]["score"]
