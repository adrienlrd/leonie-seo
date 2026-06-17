"""Tests for auto_publish_checked_proposals (per-product checkbox auto-apply)."""

from __future__ import annotations

from typing import Any

import pytest

import app.api.market_analysis as ma
from app.learning.models import LearningMode, MerchantLearningSettings


def _product(**pack: Any) -> dict[str, Any]:
    return {
        "product_id": "gid://shopify/Product/1",
        "product_title": "Harnais",
        "product_handle": "harnais",
        "content_test_pack": pack,
    }


@pytest.fixture()
def captured(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    calls: dict[str, Any] = {"applied": [], "patched": []}

    def fake_apply_core(shop, token, product, fields):
        calls["applied"].append((product["product_id"], list(fields)))
        return {"results": {}, "applied_fields": {}}

    def fake_patch(shop, product_id, proposals):
        calls["patched"].append((product_id, proposals))
        return True

    monkeypatch.setattr(ma, "_apply_proposals_core", fake_apply_core)
    monkeypatch.setattr(ma, "patch_product_proposals", fake_patch)
    monkeypatch.setattr(ma, "get_token", lambda shop: "tok")
    return calls


def _set_mode(monkeypatch: pytest.MonkeyPatch, mode: LearningMode) -> None:
    monkeypatch.setattr(
        ma, "get_settings", lambda shop, db_path=None: MerchantLearningSettings(shop=shop, mode=mode)
    )


def test_manual_mode_publishes_nothing(monkeypatch: pytest.MonkeyPatch, captured: dict) -> None:
    _set_mode(monkeypatch, LearningMode.SEMI_AUTO)
    data = {"products": [_product(proposed_meta_title="Harnais Premium pour Chien de Berger")]}
    summary = ma.auto_publish_checked_proposals("s.myshopify.com", data, {})
    assert summary["mode"] == "manual"
    assert summary["published"] == 0
    assert captured["applied"] == []


def test_auto_mode_without_token_skips(monkeypatch: pytest.MonkeyPatch, captured: dict) -> None:
    _set_mode(monkeypatch, LearningMode.AUTO_APPLY)
    monkeypatch.setattr(ma, "get_token", lambda shop: None)
    data = {"products": [_product(proposed_meta_title="Harnais Premium pour Chien de Berger")]}
    summary = ma.auto_publish_checked_proposals("s.myshopify.com", data, {})
    assert summary.get("skipped_reason") == "no_token"
    assert captured["applied"] == []


def test_auto_mode_publishes_safe_holds_unsafe(
    monkeypatch: pytest.MonkeyPatch, captured: dict
) -> None:
    _set_mode(monkeypatch, LearningMode.AUTO_APPLY)
    product = _product(
        proposed_meta_title="Harnais Premium pour Chien de Berger Allemand",
        current_meta_title="Vieux titre",
        proposed_meta_description=(
            "Cette croquette guérit votre chien de toutes ses maladies, résultat garanti "
            "sous une semaine pour tous les chiens adultes et chiots en croissance."
        ),
        current_meta_description="Ancienne description",
        auto_publish_fields=["meta_title", "meta_description"],
    )
    data = {"products": [product]}
    niche = {"forbidden_promises": ["guérit", "garanti"]}
    summary = ma.auto_publish_checked_proposals("s.myshopify.com", data, niche)

    # meta_title is safe → applied; meta_description has a forbidden promise → held.
    assert captured["applied"] == [("gid://shopify/Product/1", ["meta_title"])]
    assert summary["published"] == 1
    held_patch = next(p for pid, p in captured["patched"] if "auto_publish_held" in p)
    assert "meta_description" in held_patch["auto_publish_held"]


def test_identical_proposal_is_skipped(monkeypatch: pytest.MonkeyPatch, captured: dict) -> None:
    _set_mode(monkeypatch, LearningMode.AUTO_APPLY)
    product = _product(
        proposed_meta_title="Harnais Premium pour Chien de Berger",
        current_meta_title="Harnais Premium pour Chien de Berger",
        auto_publish_fields=["meta_title"],
    )
    summary = ma.auto_publish_checked_proposals("s.myshopify.com", {"products": [product]}, {})
    assert captured["applied"] == []
    assert summary["published"] == 0


def test_default_fields_when_no_checkboxes_persisted(
    monkeypatch: pytest.MonkeyPatch, captured: dict
) -> None:
    _set_mode(monkeypatch, LearningMode.AUTO_APPLY)
    # No auto_publish_fields key → default to all fields that have a proposal.
    product = _product(
        proposed_meta_title="Harnais Premium pour Chien de Berger Malinois",
        current_meta_title="Old",
    )
    summary = ma.auto_publish_checked_proposals("s.myshopify.com", {"products": [product]}, {})
    assert captured["applied"] == [("gid://shopify/Product/1", ["meta_title"])]
    assert summary["published"] == 1
