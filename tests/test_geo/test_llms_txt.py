"""Tests for the deterministic llms.txt / llms-full.txt generator."""

from __future__ import annotations

import pytest

from app.geo.llms_txt import (
    LlmsTxtGenerationError,
    build_agents_md,
    build_llms_full_txt,
    build_llms_payload,
    build_llms_txt,
    content_hash,
    wrap_liquid_raw,
)


def _snapshot() -> dict:
    return {
        "shop": {
            "name": "Léonie Delacroix",
            "myshopifyDomain": "leonie.myshopify.com",
            "primaryDomain": {"host": "leoniedelacroix.com"},
        },
        "products": [
            {
                "id": "1",
                "title": "Harnais chien cuir",
                "handle": "harnais-chien-cuir",
                "description": (
                    "Harnais en cuir pleine fleur réglable, cousu main en France. "
                    "Boucles laiton et garantie 2 ans."
                ),
            },
            {
                "id": "2",
                "title": "Bol chat",
                "handle": "bol-chat",
                "description": "Bol design.",
            },
            {
                "id": "3",
                "title": "",
                "handle": "no-title",
                "description": "Un produit sans titre mais avec assez de mots pour passer le filtre copy.",
            },
        ],
        "collections": [
            {
                "id": "10",
                "title": "Harnais chien",
                "handle": "harnais-chien",
                "seo": {"description": "Sélection de harnais pour chien."},
            }
        ],
        "pages": [
            {
                "id": "20",
                "title": "À propos",
                "handle": "about",
                "body": "<p>Léonie crée des accessoires pour animaux depuis 2018.</p>",
            },
            {
                "id": "21",
                "title": "Contact",
                "handle": "contact",
                "body": "<p>Nous écrire.</p>",
            },
        ],
    }


def _business_profile() -> dict:
    return {
        "brand_name": "Léonie Delacroix",
        "niche_summary": "Léonie Delacroix conçoit des accessoires premium pour chiens et chats.",
    }


def test_llms_txt_is_spec_compliant() -> None:
    text = build_llms_txt("leonie.myshopify.com", _snapshot(), _business_profile())

    lines = text.splitlines()
    assert lines[0] == "# Léonie Delacroix"
    assert text.count("\n# ") == 0  # single H1
    assert "> Léonie Delacroix conçoit des accessoires premium" in text
    assert "## Policies" in text
    assert "## Collections" in text
    assert "## Products" in text
    assert "## Optional" in text
    # Absolute HTTPS links on the primary domain.
    assert "https://leoniedelacroix.com/products/harnais-chien-cuir" in text
    assert "http://" not in text.replace("https://", "")


def test_llms_txt_excludes_thin_and_untitled_products() -> None:
    text = build_llms_txt("leonie.myshopify.com", _snapshot(), _business_profile())

    assert "/products/bol-chat" not in text  # thin copy excluded
    assert "/products/no-title" not in text  # missing title excluded


def test_optional_section_excludes_policy_handles() -> None:
    text = build_llms_txt("leonie.myshopify.com", _snapshot(), _business_profile())

    optional_block = text.split("## Optional", 1)[1]
    assert "/pages/about" in optional_block
    assert "/pages/contact" not in optional_block  # contact is a policy path


def test_summary_falls_back_to_factual_counts_without_profile() -> None:
    text = build_llms_txt("leonie.myshopify.com", _snapshot(), None)

    assert "# Léonie Delacroix" in text
    assert "is an online store" in text


def test_excludes_draft_and_unpublished_products() -> None:
    snapshot = _snapshot()
    snapshot["products"].append(
        {
            "id": "9",
            "title": "Produit brouillon",
            "handle": "produit-brouillon",
            "status": "DRAFT",
            "description": "Un brouillon avec assez de mots pour passer le filtre de copie.",
        }
    )
    snapshot["products"].append(
        {
            "id": "10",
            "title": "Produit dépublié",
            "handle": "produit-depublie",
            "status": "ACTIVE",
            "onlineStoreUrl": None,
            "description": "Un produit actif mais non publié sur le canal Online Store ici.",
        }
    )
    text = build_llms_txt("leonie.myshopify.com", snapshot, _business_profile())
    assert "/products/harnais-chien-cuir" in text  # active + published stays
    assert "/products/produit-brouillon" not in text
    assert "/products/produit-depublie" not in text


def test_excludes_frontpage_collection() -> None:
    snapshot = _snapshot()
    snapshot["collections"].append(
        {"id": "99", "title": "Home page", "handle": "frontpage"}
    )
    text = build_llms_txt("leonie.myshopify.com", snapshot, _business_profile())
    assert "/collections/harnais-chien" in text
    assert "/collections/frontpage" not in text


def test_raises_when_no_listable_content() -> None:
    empty = {"shop": {"name": "Empty"}, "products": [], "collections": [], "pages": []}
    with pytest.raises(LlmsTxtGenerationError):
        build_llms_txt("empty.myshopify.com", empty, None)


def test_full_txt_includes_bodies_and_respects_budget() -> None:
    snapshot = _snapshot()
    full = build_llms_full_txt("leonie.myshopify.com", snapshot, _business_profile())
    assert "Harnais en cuir pleine fleur" in full
    assert "Léonie crée des accessoires" in full

    tiny = build_llms_full_txt(
        "leonie.myshopify.com", snapshot, _business_profile(), budget_bytes=200
    )
    assert len(tiny.encode("utf-8")) <= 400  # header + at most one block


def test_content_hash_is_stable_for_unchanged_snapshot() -> None:
    snapshot = _snapshot()
    first = build_llms_txt("leonie.myshopify.com", snapshot, _business_profile())
    second = build_llms_txt("leonie.myshopify.com", snapshot, _business_profile())
    assert content_hash(first) == content_hash(second)


def test_payload_reports_omitted_pages_warning() -> None:
    payload = build_llms_payload(
        "leonie.myshopify.com", _snapshot(), _business_profile(), budget_bytes=200
    )
    assert payload["summary"]["omitted_full_pages"] >= 1
    assert any("omitted" in w for w in payload["warnings"])
    assert payload["content_hash"] == content_hash(payload["llms_txt"])
    assert payload["domain"] == "leoniedelacroix.com"


def test_payload_includes_agents_md() -> None:
    payload = build_llms_payload("leonie.myshopify.com", _snapshot(), _business_profile())
    assert payload["agents_md"].startswith("# Léonie Delacroix")
    assert payload["agents_content_hash"] == content_hash(payload["agents_md"])


def test_build_agents_md_mirrors_index_v1() -> None:
    snapshot, profile = _snapshot(), _business_profile()
    assert build_agents_md("leonie.myshopify.com", snapshot, profile) == build_llms_txt(
        "leonie.myshopify.com", snapshot, profile
    )


def test_wrap_liquid_raw_neutralizes_injection() -> None:
    wrapped = wrap_liquid_raw("Buy {{ shop.name }} now {% assign x = 1 %}")
    assert wrapped.startswith("{% raw %}\n")
    assert wrapped.endswith("\n{% endraw %}")
    # The merchant content is preserved verbatim inside the raw block.
    assert "{{ shop.name }}" in wrapped


def test_wrap_liquid_raw_defuses_literal_endraw() -> None:
    wrapped = wrap_liquid_raw("text {% endraw %} more")
    # Only the wrapper's own closing tag may remain; the embedded one is defused.
    assert wrapped.count("{% endraw %}") == 1
    assert "{% endraw_ %}" in wrapped
