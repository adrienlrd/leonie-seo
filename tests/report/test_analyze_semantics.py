"""Tests for scripts.report.analyze_semantics."""

from scripts.report.analyze_semantics import (
    _score_signals,
    analyze_product,
    render_markdown,
)

_SIGNALS = ["made in france", "artisanal", "vétérinaire", "confort", "élégant"]

_PRODUCT_RICH = {
    "handle": "le-pardessus-pour-chien",
    "title": "Le Pardessus Pour Chien",
    "description": (
        "Made in France par nos artisanes couturières. Laine d'alpaga, confort optimal. "
        "Recommandé par des vétérinaires. Design élégant et durable. Liberté de mouvement "
        "assurée, respirant, hypoallergénique. Satisfait ou remboursé. Pour chien premium."
    ),
}

_PRODUCT_EMPTY = {
    "handle": "le-raisonnable",
    "title": "Le Raisonnable",
    "description": "",
}


def test_score_signals_all_present():
    found, total, missing = _score_signals("made in france et artisanal", ["made in france", "artisanal"])
    assert found == 2
    assert total == 2
    assert missing == []


def test_score_signals_none_present():
    found, total, missing = _score_signals("rien de pertinent", _SIGNALS)
    assert found == 0
    assert len(missing) == len(_SIGNALS)


def test_score_signals_partial():
    found, total, missing = _score_signals("confort et élégant", _SIGNALS)
    assert found == 2
    assert "confort" not in missing
    assert "made in france" in missing


def test_analyze_product_has_all_fields():
    result = analyze_product(_PRODUCT_RICH)
    required = {
        "handle", "title", "category", "description_length",
        "premium_score", "eeat_score", "longtail_score", "category_score",
        "global_score", "top_missing_premium", "top_missing_eeat",
        "top_missing_longtail", "top_missing_category",
    }
    assert required.issubset(result.keys())


def test_analyze_product_scores_between_0_and_1():
    result = analyze_product(_PRODUCT_RICH)
    for field in ("premium_score", "eeat_score", "longtail_score", "category_score", "global_score"):
        assert 0.0 <= result[field] <= 1.0, f"{field} out of range"


def test_analyze_product_rich_scores_higher_than_empty():
    rich = analyze_product(_PRODUCT_RICH)
    empty = analyze_product(_PRODUCT_EMPTY)
    assert rich["global_score"] > empty["global_score"]
    assert rich["premium_score"] > empty["premium_score"]


def test_analyze_product_empty_description_zero_scores():
    result = analyze_product(_PRODUCT_EMPTY)
    assert result["premium_score"] == 0.0
    assert result["eeat_score"] == 0.0
    assert result["description_length"] == 0


def test_analyze_product_detects_eeat_signal():
    result = analyze_product(_PRODUCT_RICH)
    assert result["eeat_score"] > 0


def test_analyze_product_category_assigned():
    result = analyze_product(_PRODUCT_RICH)
    assert result["category"] == "vetements_chien"


def test_analyze_product_missing_lists_are_lists():
    result = analyze_product(_PRODUCT_RICH)
    assert isinstance(result["top_missing_premium"], list)
    assert isinstance(result["top_missing_eeat"], list)
    assert isinstance(result["top_missing_category"], list)


def test_analyze_product_missing_not_in_text():
    result = analyze_product(_PRODUCT_RICH)
    text = (_PRODUCT_RICH["title"] + " " + _PRODUCT_RICH["description"]).lower()
    for term in result["top_missing_premium"]:
        assert term not in text


def test_render_markdown_has_date():
    md = render_markdown([], "2026-05-08")
    assert "2026-05-08" in md


def test_render_markdown_has_benchmark():
    md = render_markdown([], "2026-05-08")
    assert "Benchmark" in md or "Miacara" in md


def test_render_markdown_shows_all_products():
    results = [analyze_product(_PRODUCT_RICH), analyze_product(_PRODUCT_EMPTY)]
    md = render_markdown(results, "2026-05-08")
    assert "Le Pardessus Pour Chien" in md
    assert "Le Raisonnable" in md


def test_render_markdown_has_recommendations():
    md = render_markdown([analyze_product(_PRODUCT_EMPTY)], "2026-05-08")
    assert "Recommandations" in md


def test_render_markdown_low_score_product_appears_in_gaps():
    results = [analyze_product(_PRODUCT_EMPTY)]
    md = render_markdown(results, "2026-05-08")
    assert "Le Raisonnable" in md
    assert "Lacunes" in md
