"""Tests for SERP intelligence parsing (PAA capture) in the DataForSEO provider."""

from __future__ import annotations

from app.market_analysis.providers.dataforseo_provider import (
    _parse_serp_competitors,
    _parse_serp_intelligence,
)

_SERP_DATA = {
    "fontaine à chat": [
        {"type": "people_also_ask", "title": "Comment nettoyer une fontaine à chat ?"},
        {"type": "people_also_ask", "title": "Quelle fontaine à chat est la plus silencieuse ?"},
        {"type": "people_also_ask", "title": "Comment nettoyer une fontaine à chat ?"},  # dup
        {"type": "featured_snippet", "title": "Une fontaine à chat oxygène l'eau en continu."},
        {"type": "organic", "domain": "Concurrent-A.fr", "title": "Top fontaines à chat", "url": "https://a.fr/x", "rank_absolute": 1},
        {"type": "organic", "domain": "concurrent-b.fr", "title": "Guide fontaine chat", "url": "https://b.fr/y", "rank_absolute": 2},
    ]
}


def test_parse_serp_intelligence_captures_paa_questions():
    intel = _parse_serp_intelligence(_SERP_DATA)
    entry = intel["fontaine à chat"]

    # PAA questions are kept (and deduplicated) — regression vs the old discard.
    assert entry["paa"] == [
        "Comment nettoyer une fontaine à chat ?",
        "Quelle fontaine à chat est la plus silencieuse ?",
    ]
    assert entry["featured_snippet"] == "Une fontaine à chat oxygène l'eau en continu."
    assert len(entry["top_competitors"]) == 2
    assert entry["top_competitors"][0]["domain"] == "concurrent-a.fr"
    assert entry["top_competitors"][0]["rank"] == 1


def test_parse_serp_competitors_still_returns_domain_list():
    # The existing domain-level competitor parsing must be unchanged.
    signals = _parse_serp_competitors(_SERP_DATA)
    domains = {s["domain"] for s in signals}
    assert "concurrent-a.fr" in domains
    assert "concurrent-b.fr" in domains
    assert all(s["detected_from"] == "paid_provider" for s in signals)


def test_parse_serp_intelligence_handles_empty():
    assert _parse_serp_intelligence({}) == {}
