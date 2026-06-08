"""Keyword-placement guardrail for generated blog articles."""

from __future__ import annotations

from app.blog.quality import check_keyword_placement

_KEYWORD = "croquettes sans céréales"


def _section(h2: str, extra_body: str = "") -> dict[str, str]:
    return {
        "h2": h2,
        "direct_answer": "Cette alimentation limite les troubles digestifs au quotidien. " * 2,
        "body": ("Les chiens sensibles digèrent souvent mal le blé ou le maïs. " * 12) + extra_body,
    }


def test_check_keyword_placement_returns_ok_when_placement_is_correct() -> None:
    result = check_keyword_placement(
        title="Croquettes sans céréales : le guide complet pour bien choisir",
        intro=(
            "Les croquettes sans céréales séduisent de plus en plus de propriétaires "
            "de chiens sensibles aux céréales classiques."
        ),
        h2_questions=[
            "Pourquoi choisir des croquettes sans céréales ?",
            "Comment doser les croquettes sans céréales au quotidien ?",
        ],
        sections=[
            _section(
                "Pourquoi choisir des croquettes sans céréales ?",
                "Les croquettes sans céréales sont recommandées par de nombreux vétérinaires.",
            ),
            _section("Comment doser les croquettes sans céréales au quotidien ?"),
        ],
        target_keyword=_KEYWORD,
    )

    assert result["ok"] is True
    assert result["score"] == 100
    assert result["label"] == "excellent"
    assert result["issues"] == []


def test_check_keyword_placement_flags_missing_title_h2_and_lead_when_keyword_absent() -> None:
    result = check_keyword_placement(
        title="Le guide complet pour le bien-être de votre compagnon",
        intro="Un article généraliste sur l'alimentation animale au quotidien.",
        h2_questions=[
            "Comment bien nourrir son animal ?",
            "Quels sont les besoins nutritionnels ?",
        ],
        sections=[_section("Comment bien nourrir son animal ?")],
        target_keyword=_KEYWORD,
    )

    assert result["ok"] is False
    assert "n'apparaît pas dans le titre" in " ".join(result["issues"])
    assert "aucun sous-titre" in " ".join(result["issues"])
    assert "100 premiers mots" in " ".join(result["issues"])
    assert result["score"] < 50
    assert result["label"] == "incomplet"


def test_check_keyword_placement_flags_overuse_when_density_too_high() -> None:
    keyword = "croquettes chien"
    stuffed_body = (keyword + " ") * 30 + "autre texte sans rapport " * 20
    result = check_keyword_placement(
        title=f"{keyword} : le guide",
        intro=f"{keyword} expliquées simplement pour bien choisir.",
        h2_questions=[f"Pourquoi choisir des {keyword} ?"],
        sections=[
            {
                "h2": f"Pourquoi choisir des {keyword} ?",
                "direct_answer": f"Les {keyword} conviennent à la plupart des chiens. ",
                "body": stuffed_body,
            }
        ],
        target_keyword=keyword,
    )

    assert result["ok"] is False
    assert any("revient trop souvent" in issue for issue in result["issues"])


def test_check_keyword_placement_skips_check_when_no_target_keyword() -> None:
    result = check_keyword_placement(
        title="Titre sans mot-clé défini",
        intro="Intro",
        h2_questions=[],
        sections=[],
        target_keyword="",
    )

    assert result == {"ok": True, "score": 100, "label": "excellent", "issues": []}
