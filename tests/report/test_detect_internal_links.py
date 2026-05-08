"""Tests for scripts.report.detect_internal_links."""

from scripts.report.detect_internal_links import (
    _anchor_from_keyword,
    _tokenize,
    detect_opportunities,
    detect_orphans,
    render_markdown,
)

_KEYWORDS = {
    "vetements_chien": ["pardessus pour chien france", "harnais chien haute couture france"],
    "fontaines_abreuvoirs": [
        "fontaine eau chat sans fil silencieuse",
        "abreuvoir chat design inox",
    ],
    "informational": ["comment choisir fontaine eau chat"],
    "brand": ["leoniedelacroix"],
}

_PRODUCTS = [
    {
        "handle": "le-pardessus-pour-chien",
        "title": "Le Pardessus Pour Chien",
        "id": "gid://shopify/Product/1",
    },
    {
        "handle": "fontaine-smart-cordless",
        "title": "La Fontaine Smart",
        "id": "gid://shopify/Product/2",
    },
    {"handle": "labreuvoir", "title": "L'abreuvoir", "id": "gid://shopify/Product/3"},
    {"handle": "produit-sans-liens", "title": "Produit Orphelin", "id": "gid://shopify/Product/4"},
]

_COLLECTIONS = [
    {"handle": "chien", "title": "Chien"},
    {"handle": "chat", "title": "Chat"},
]

_GSC_URLS = {
    "https://www.leoniedelacroix.com/products/le-pardessus-pour-chien",
    "https://www.leoniedelacroix.com/products/fontaine-smart-cordless",
    "https://www.leoniedelacroix.com/products/labreuvoir",
}


def test_tokenize_removes_stop_words():
    tokens = _tokenize("comment choisir une fontaine")
    assert "comment" not in tokens
    assert "une" not in tokens
    assert "fontaine" in tokens


def test_tokenize_returns_set():
    assert isinstance(_tokenize("fontaine eau chat"), set)


def test_anchor_from_keyword_uses_shared_tokens():
    anchor = _anchor_from_keyword("fontaine eau chat silencieuse", "La Fontaine Smart")
    assert "fontaine" in anchor


def test_anchor_falls_back_to_title():
    anchor = _anchor_from_keyword("quelque chose sans rapport", "Mon Produit")
    assert anchor == "mon produit"


def test_detect_opportunities_returns_list():
    opps = detect_opportunities(_KEYWORDS, _PRODUCTS, _COLLECTIONS)
    assert isinstance(opps, list)
    assert len(opps) > 0


def test_detect_opportunities_excludes_brand():
    opps = detect_opportunities(_KEYWORDS, _PRODUCTS, _COLLECTIONS)
    source_kws = {o["source_keyword"] for o in opps}
    assert "leoniedelacroix" not in source_kws


def test_detect_opportunities_no_duplicates():
    opps = detect_opportunities(_KEYWORDS, _PRODUCTS, _COLLECTIONS)
    pairs = [(o["source_keyword"], o["target_url"]) for o in opps]
    assert len(pairs) == len(set(pairs))


def test_detect_opportunities_sorted_by_score_desc():
    opps = detect_opportunities(_KEYWORDS, _PRODUCTS, _COLLECTIONS)
    scores = [o["relevance_score"] for o in opps]
    assert scores == sorted(scores, reverse=True)


def test_detect_opportunities_has_required_fields():
    opps = detect_opportunities(_KEYWORDS, _PRODUCTS, _COLLECTIONS)
    required = {"source_keyword", "target_url", "target_title", "anchor_text", "relevance_score"}
    for opp in opps:
        assert required.issubset(opp.keys())


def test_detect_opportunities_informational_links_to_fontaine():
    opps = detect_opportunities(_KEYWORDS, _PRODUCTS, _COLLECTIONS)
    kw_targets = {
        (o["source_keyword"], o["target_url"])
        for o in opps
        if o["source_keyword"] == "comment choisir fontaine eau chat"
    }
    assert any("fontaine" in url for _, url in kw_targets)


def test_detect_orphans_finds_missing_from_gsc():
    orphans = detect_orphans(_PRODUCTS, _GSC_URLS)
    handles = [o["handle"] for o in orphans]
    assert "produit-sans-liens" in handles


def test_detect_orphans_excludes_gsc_pages():
    orphans = detect_orphans(_PRODUCTS, _GSC_URLS)
    handles = [o["handle"] for o in orphans]
    assert "le-pardessus-pour-chien" not in handles
    assert "fontaine-smart-cordless" not in handles


def test_detect_orphans_empty_gsc_flags_all():
    orphans = detect_orphans(_PRODUCTS, set())
    assert len(orphans) == len(_PRODUCTS)


def test_render_markdown_has_title():
    md = render_markdown([], [], "2026-05-08")
    assert "Maillage Interne" in md
    assert "2026-05-08" in md


def test_render_markdown_lists_opportunities():
    opps = detect_opportunities(_KEYWORDS, _PRODUCTS, _COLLECTIONS)
    md = render_markdown(opps[:5], [], "2026-05-08")
    assert "|" in md  # table rows


def test_render_markdown_lists_orphans():
    orphans = detect_orphans(_PRODUCTS, _GSC_URLS)
    md = render_markdown([], orphans, "2026-05-08")
    assert "Produit Orphelin" in md


def test_render_markdown_has_action_plan():
    md = render_markdown([], [], "2026-05-08")
    assert "Plan d'action" in md
