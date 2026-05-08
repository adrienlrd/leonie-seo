"""Tests for scripts.report.generate_blog_briefs."""

from scripts.report.generate_blog_briefs import (
    _h1_from_keyword,
    _secondary_keywords,
    generate_brief,
    render_markdown,
    select_candidates,
)

_KEYWORDS = {
    "informational": [
        "comment choisir fontaine eau chat",
        "meilleur griffoir chat appartement",
    ],
    "vetements_chien": [
        "pardessus pour chien france",
        "manteau pour chien luxe made in france",
        "harnais chien haute couture france",
    ],
    "fontaines_abreuvoirs": [
        "fontaine eau chat sans fil silencieuse",
        "abreuvoir chat design inox",
    ],
    "brand": [
        "leoniedelacroix",
    ],
}

_GAPS = [
    {
        "keyword": "pardessus pour chien france",
        "status": "on_site",
        "impressions": 0,
        "opportunity_score": 5.0,
    },
    {
        "keyword": "abreuvoir chat design inox",
        "status": "on_site",
        "impressions": 0,
        "opportunity_score": 4.0,
    },
    {
        "keyword": "manteau pour chien luxe made in france",
        "status": "ranking",
        "impressions": 50,
        "opportunity_score": 8.0,
    },
    {
        "keyword": "leoniedelacroix",
        "status": "ranking",
        "impressions": 690,
        "opportunity_score": 87.0,
    },
]


def test_select_candidates_includes_all_informational():
    candidates = select_candidates(_KEYWORDS, _GAPS)
    kws = [c["keyword"] for c in candidates]
    assert "comment choisir fontaine eau chat" in kws
    assert "meilleur griffoir chat appartement" in kws


def test_select_candidates_includes_on_site_zero_impressions():
    candidates = select_candidates(_KEYWORDS, _GAPS)
    kws = [c["keyword"] for c in candidates]
    assert "pardessus pour chien france" in kws
    assert "abreuvoir chat design inox" in kws


def test_select_candidates_excludes_brand():
    candidates = select_candidates(_KEYWORDS, _GAPS)
    kws = [c["keyword"] for c in candidates]
    assert "leoniedelacroix" not in kws


def test_select_candidates_excludes_ranking_with_impressions():
    candidates = select_candidates(_KEYWORDS, _GAPS)
    kws = [c["keyword"] for c in candidates]
    assert "manteau pour chien luxe made in france" not in kws


def test_select_candidates_no_duplicates():
    candidates = select_candidates(_KEYWORDS, _GAPS)
    kws = [c["keyword"] for c in candidates]
    assert len(kws) == len(set(kws))


def test_select_candidates_max_ten():
    large_kws = {f"cat{i}": [f"kw{j}" for j in range(5)] for i in range(10)}
    large_kws["informational"] = [f"info{i}" for i in range(20)]
    candidates = select_candidates(large_kws, [])
    assert len(candidates) <= 10


def test_h1_informational_keeps_keyword():
    h1 = _h1_from_keyword("comment choisir fontaine eau chat", "informational")
    assert "Comment choisir fontaine eau chat" == h1


def test_h1_vetements_adds_guide():
    h1 = _h1_from_keyword("pardessus pour chien france", "vetements_chien")
    assert "guide complet" in h1.lower()


def test_h1_fontaines_adds_veterinaire():
    h1 = _h1_from_keyword("fontaine eau chat sans fil", "fontaines_abreuvoirs")
    assert "vétérinaire" in h1.lower()


def test_secondary_keywords_excludes_primary():
    sec = _secondary_keywords("pardessus pour chien france", "vetements_chien", _KEYWORDS)
    assert "pardessus pour chien france" not in sec


def test_secondary_keywords_max_four():
    sec = _secondary_keywords("pardessus pour chien france", "vetements_chien", _KEYWORDS)
    assert len(sec) <= 4


def test_generate_brief_has_required_fields():
    candidate = {
        "keyword": "comment choisir fontaine eau chat",
        "category": "informational",
        "status": "planned",
        "impressions": 0,
    }
    brief = generate_brief(candidate, _KEYWORDS)
    for field in (
        "keyword",
        "category",
        "intent",
        "h1",
        "h2s",
        "secondary_keywords",
        "target_length",
        "eeat_angle",
        "internal_links",
    ):
        assert field in brief, f"Missing field: {field}"


def test_generate_brief_h2s_not_empty():
    candidate = {
        "keyword": "pardessus pour chien france",
        "category": "vetements_chien",
        "status": "on_site",
        "impressions": 0,
    }
    brief = generate_brief(candidate, _KEYWORDS)
    assert len(brief["h2s"]) >= 3


def test_render_markdown_contains_all_keywords():
    candidates = select_candidates(_KEYWORDS, _GAPS)
    briefs = [generate_brief(c, _KEYWORDS) for c in candidates]
    md = render_markdown(briefs, "2026-05-08")
    for b in briefs:
        assert b["keyword"] in md


def test_render_markdown_has_date():
    md = render_markdown([], "2026-05-08")
    assert "2026-05-08" in md


def test_render_markdown_has_eeat_section():
    candidate = {
        "keyword": "comment choisir fontaine eau chat",
        "category": "informational",
        "status": "planned",
        "impressions": 0,
    }
    briefs = [generate_brief(candidate, _KEYWORDS)]
    md = render_markdown(briefs, "2026-05-08")
    assert "E-E-A-T" in md
