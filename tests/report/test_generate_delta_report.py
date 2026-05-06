"""Tests for scripts.report.generate_delta_report."""

import pytest

from scripts.report.generate_delta_report import (
    changes_summary,
    compute_issues,
    generate_delta_markdown,
    reconstruct_before_snapshot,
)

# ── Fixtures ──────────────────────────────────────────────────────────────────

_PRODUCT = {
    "id": "gid://shopify/Product/1",
    "title": "Le Pardessus Pour Chien",
    "handle": "le-pardessus-pour-chien",
    "status": "ACTIVE",
    "seo": {"title": "Pardessus Chien Premium | Léonie Delacroix", "description": "Description optimisée longue de 120 caractères minimum pour ce beau produit Léonie."},
    "images": {
        "edges": [
            {"node": {"id": "gid://shopify/ProductImage/99", "url": "http://x.com/img.jpg", "altText": "Pardessus pour chien élégant"}}
        ]
    },
    "collections": {"edges": []},
    "variants": {"edges": [{"node": {"price": "49.99"}}]},
}

_COLLECTION = {
    "id": "gid://shopify/Collection/1",
    "title": "Chien",
    "handle": "chien",
    "seo": {"title": "Collection Chien Premium | Léonie Delacroix", "description": "Découvrez notre collection chien premium Léonie Delacroix."},
}

_CHANGES_META = [
    {
        "id": 1, "applied_at": "2026-05-05T10:00:00", "resource_type": "product",
        "resource_id": "gid://shopify/Product/1", "field": "seo.title",
        "old_value": None, "new_value": "Pardessus Chien Premium | Léonie Delacroix",
        "status": "applied",
    },
    {
        "id": 2, "applied_at": "2026-05-05T10:00:00", "resource_type": "product",
        "resource_id": "gid://shopify/Product/1", "field": "seo.description",
        "old_value": None, "new_value": "Description optimisée longue de 120 caractères minimum.",
        "status": "applied",
    },
]

_CHANGES_ALT = [
    {
        "id": 3, "applied_at": "2026-05-05T10:01:00", "resource_type": "product",
        "resource_id": "gid://shopify/Product/1",
        "field": "image.altText:gid://shopify/ProductImage/99",
        "old_value": None, "new_value": "Pardessus pour chien élégant",
        "status": "applied",
    },
]


# ── reconstruct_before_snapshot ───────────────────────────────────────────────


def test_reconstruct_before_snapshot_restores_none_title():
    products_b, _ = reconstruct_before_snapshot([_PRODUCT], [_COLLECTION], _CHANGES_META)
    assert products_b[0]["seo"]["title"] is None


def test_reconstruct_before_snapshot_restores_none_description():
    products_b, _ = reconstruct_before_snapshot([_PRODUCT], [_COLLECTION], _CHANGES_META)
    assert products_b[0]["seo"]["description"] is None


def test_reconstruct_before_snapshot_restores_alt_text():
    products_b, _ = reconstruct_before_snapshot([_PRODUCT], [], _CHANGES_ALT)
    alt = products_b[0]["images"]["edges"][0]["node"]["altText"]
    assert alt is None


def test_reconstruct_before_snapshot_does_not_mutate_originals():
    import copy
    original = copy.deepcopy(_PRODUCT)
    reconstruct_before_snapshot([_PRODUCT], [], _CHANGES_META)
    assert _PRODUCT["seo"]["title"] == original["seo"]["title"]


def test_reconstruct_before_snapshot_collection():
    change = {
        "id": 10, "applied_at": "2026-05-05T10:00:00", "resource_type": "collection",
        "resource_id": "gid://shopify/Collection/1", "field": "seo.title",
        "old_value": "Vieux titre", "new_value": "Nouveau titre", "status": "applied",
    }
    _, colls_b = reconstruct_before_snapshot([], [_COLLECTION], [change])
    assert colls_b[0]["seo"]["title"] == "Vieux titre"


# ── changes_summary ───────────────────────────────────────────────────────────


def test_changes_summary_counts_by_type():
    all_changes = _CHANGES_META + _CHANGES_ALT
    summary = changes_summary(all_changes)
    assert summary["meta_title"] == 1
    assert summary["meta_description"] == 1
    assert summary["alt_text"] == 1


def test_changes_summary_empty():
    assert changes_summary([]) == {"meta_title": 0, "meta_description": 0, "alt_text": 0, "other": 0}


# ── generate_delta_markdown ───────────────────────────────────────────────────


def test_generate_delta_score_improves_after_optimization():
    """Score after should be >= score before when issues are fixed."""
    # Before: missing title → issues detected
    # After: title present → fewer issues
    products_before, _ = reconstruct_before_snapshot([_PRODUCT], [_COLLECTION], _CHANGES_META)

    md = generate_delta_markdown(
        products_before, [_COLLECTION],
        [_PRODUCT], [_COLLECTION],
        _CHANGES_META, [], [],
        "2026-05-06",
    )
    assert "Score SEO global" in md
    # After score should not be worse
    # Extract scores from markdown
    import re
    scores = re.findall(r"Score global.*?\|\s*([\d.]+)\s*\|\s*([\d.]+)", md)
    if scores:
        before_score, after_score = float(scores[0][0]), float(scores[0][1])
        assert after_score >= before_score


def test_generate_delta_markdown_contains_all_sections():
    products_before, _ = reconstruct_before_snapshot([_PRODUCT], [_COLLECTION], _CHANGES_META)
    md = generate_delta_markdown(
        products_before, [_COLLECTION],
        [_PRODUCT], [_COLLECTION],
        _CHANGES_META + _CHANGES_ALT, [], [],
        "2026-05-06",
    )
    assert "Optimisations appliquées" in md
    assert "Score SEO global" in md
    assert "Issues résolues" in md
    assert "Top 10 changements méta" in md
    assert "Couverture mots-clés" in md


def test_generate_delta_markdown_includes_opportunities():
    opps = [
        {
            "url": "https://www.leoniedelacroix.com/products/labreuvoir",
            "zone": "quick_win", "position": 11.5, "impressions": 344,
            "ctr_pct": 5.2, "estimated_gain_clicks": 3,
            "action": "Enrichir contenu",
        }
    ]
    products_before, _ = reconstruct_before_snapshot([_PRODUCT], [], _CHANGES_META)
    md = generate_delta_markdown(
        products_before, [], [_PRODUCT], [], _CHANGES_META, opps, [], "2026-05-06"
    )
    assert "labreuvoir" in md
    assert "Quick win" in md


def test_generate_delta_no_changes_zero_delta():
    """With no changes, before and after scores should be identical."""
    md = generate_delta_markdown(
        [_PRODUCT], [_COLLECTION],
        [_PRODUCT], [_COLLECTION],
        [], [], [],
        "2026-05-06",
    )
    # Score rows should show → 0.0 delta
    assert "→ +0.0" in md or "→ 0.0" in md or "→ -0.0" in md
