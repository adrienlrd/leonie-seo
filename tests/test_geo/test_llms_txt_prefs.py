"""Tests for AI-crawler preferences (content filters + welcomed agents)."""

from __future__ import annotations

from app.geo.llms_txt import (
    KNOWN_AI_AGENTS,
    build_llms_payload,
    build_llms_txt,
    resolve_crawler_prefs,
)

SHOP = "shop.myshopify.com"


def _snapshot() -> dict:
    return {
        "shop": {"name": "Demo", "primaryDomain": {"host": "demo.com"}},
        "products": [
            {
                "id": "1",
                "title": "Harnais chien cuir",
                "handle": "harnais-chien-cuir",
                "description": "Harnais en cuir pleine fleur cousu main, garantie 2 ans solide.",
            }
        ],
        "collections": [
            {"id": "10", "title": "Harnais", "handle": "harnais",
             "seo": {"description": "Sélection de harnais."}},
        ],
        "pages": [
            {"title": "À propos", "handle": "a-propos", "body": "Notre histoire et nos valeurs."},
        ],
    }


def test_default_prefs_list_all_sections_and_no_ai_access_block() -> None:
    out = build_llms_txt(SHOP, _snapshot())
    assert "## Products" in out
    assert "## Collections" in out
    assert "## Optional" in out  # the page
    assert "## AI access" not in out  # default welcomes all → no clutter


def test_include_products_false_drops_products_section() -> None:
    out = build_llms_txt(SHOP, _snapshot(), prefs={"include_products": False})
    assert "## Products" not in out
    assert "## Collections" in out  # other sections untouched


def test_include_collections_false_drops_collections_section() -> None:
    out = build_llms_txt(SHOP, _snapshot(), prefs={"include_collections": False})
    assert "## Collections" not in out
    assert "## Products" in out


def test_include_pages_false_drops_optional_section() -> None:
    out = build_llms_txt(SHOP, _snapshot(), prefs={"include_pages": False})
    assert "## Optional" not in out


def test_narrowed_welcomed_agents_emits_ai_access_block() -> None:
    out = build_llms_txt(SHOP, _snapshot(), prefs={"welcomed_agents": ["GPTBot"]})
    assert "## AI access" in out
    assert "GPTBot" in out
    assert "ClaudeBot" not in out.split("## AI access")[1].split("## Policies")[0]


def test_resolve_prefs_normalises_unknown_agents_and_defaults() -> None:
    resolved = resolve_crawler_prefs({"welcomed_agents": ["GPTBot", "EvilBot"]})
    assert resolved["welcomed_agents"] == ["GPTBot"]  # unknown dropped, known kept
    assert resolved["include_products"] is True  # default preserved


def test_payload_echoes_resolved_prefs() -> None:
    payload = build_llms_payload(SHOP, _snapshot(), prefs={"include_pages": False})
    assert payload["crawler_prefs"]["include_pages"] is False
    assert set(payload["crawler_prefs"]["welcomed_agents"]) == set(KNOWN_AI_AGENTS)
