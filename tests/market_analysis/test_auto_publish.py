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
        calls["tokens"].append(token)
        return {"results": {f: {"applied": True} for f in fields}, "applied_fields": {}}

    def fake_patch(shop, product_id, proposals):
        calls["patched"].append((product_id, proposals))
        return True

    calls["tokens"] = []
    calls["runs"] = []
    monkeypatch.setattr(ma, "_apply_proposals_core", fake_apply_core)
    monkeypatch.setattr(ma, "patch_product_proposals", fake_patch)
    monkeypatch.setattr(
        ma, "record_run", lambda **kwargs: calls["runs"].append(kwargs) or 1
    )
    # get_token returns a *record dict* (decrypted access_token inside), not a bare string.
    monkeypatch.setattr(ma, "get_token", lambda shop: {"shop": shop, "access_token": "shpua_tok"})
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


def test_token_record_dict_is_reduced_to_access_token_string(
    monkeypatch: pytest.MonkeyPatch, captured: dict
) -> None:
    # Regression: get_token returns a dict; the *string* access_token must reach
    # ShopifyWriter, otherwise every auto-publish write silently fails.
    _set_mode(monkeypatch, LearningMode.AUTO_APPLY)
    product = _product(proposed_meta_title="Harnais Premium pour Chien de Berger", current_meta_title="Old")
    summary = ma.auto_publish_checked_proposals("s.myshopify.com", {"products": [product]}, {})
    assert captured["tokens"] == ["shpua_tok"]
    assert summary["published"] == 1


def test_access_token_argument_is_preferred_over_token_store(
    monkeypatch: pytest.MonkeyPatch, captured: dict
) -> None:
    # The re-analysis job holds a valid token; it must be used even if the token
    # store is empty (ephemeral disk / out-of-sync shop_tokens on Render).
    _set_mode(monkeypatch, LearningMode.AUTO_APPLY)
    monkeypatch.setattr(ma, "get_token", lambda shop: None)
    product = _product(proposed_meta_title="Harnais Premium pour Chien de Berger", current_meta_title="Old")
    summary = ma.auto_publish_checked_proposals(
        "s.myshopify.com", {"products": [product]}, {}, access_token="shpua_from_job"
    )
    assert captured["tokens"] == ["shpua_from_job"]
    assert summary["published"] == 1


def test_empty_selection_publishes_nothing(monkeypatch: pytest.MonkeyPatch, captured: dict) -> None:
    # auto_publish_fields=[] (merchant unchecked everything) must publish nothing,
    # never fall back to the "all proposed fields" default.
    _set_mode(monkeypatch, LearningMode.AUTO_APPLY)
    product = _product(
        proposed_meta_title="Harnais Premium pour Chien de Berger",
        current_meta_title="Old",
        auto_publish_fields=[],
    )
    summary = ma.auto_publish_checked_proposals("s.myshopify.com", {"products": [product]}, {})
    assert captured["applied"] == []
    assert summary["published"] == 0


def test_out_of_scope_field_is_not_auto_published(
    monkeypatch: pytest.MonkeyPatch, captured: dict
) -> None:
    # Default scopes are meta_title/meta_description/alt_text: a checked product
    # description must stay a proposal, never be auto-applied.
    _set_mode(monkeypatch, LearningMode.AUTO_APPLY)
    product = _product(
        proposed_product_description="Nouvelle description produit détaillée et conforme.",
        current_product_description_summary="Ancienne description",
        auto_publish_fields=["description"],
    )
    summary = ma.auto_publish_checked_proposals("s.myshopify.com", {"products": [product]}, {})
    assert captured["applied"] == []
    assert summary["published"] == 0
    assert summary["skipped_out_of_scope"] == 1


def test_scope_setting_enables_description_publish(
    monkeypatch: pytest.MonkeyPatch, captured: dict
) -> None:
    monkeypatch.setattr(
        ma,
        "get_settings",
        lambda shop, db_path=None: MerchantLearningSettings(
            shop=shop,
            mode=LearningMode.AUTO_APPLY,
            auto_publish_scopes=["product_description"],
        ),
    )
    long_description = (
        "Ce harnais pour chien est fabriqué dans un cuir souple et résistant, pensé pour "
        "les promenades quotidiennes comme pour les longues randonnées avec votre animal. "
        "Les coutures sont renforcées et les boucles en métal assurent une fermeture fiable "
        "dans toutes les conditions. Le rembourrage intérieur protège le poitrail du chien "
        "et répartit la traction sur l'ensemble du buste pour un confort durable. "
        "Disponible en plusieurs tailles, il convient aux petits gabarits comme aux grands "
        "chiens, et son entretien se limite à un simple nettoyage avec un chiffon humide. "
        "Un choix durable pour les propriétaires attentifs à la qualité des accessoires."
    )
    product = _product(
        proposed_product_description=long_description,
        current_product_description_summary="Ancienne description",
        auto_publish_fields=["description"],
    )
    summary = ma.auto_publish_checked_proposals("s.myshopify.com", {"products": [product]}, {})
    assert captured["applied"] == [("gid://shopify/Product/1", ["description"])]
    assert summary["published"] == 1


def test_field_in_cooldown_is_skipped(monkeypatch: pytest.MonkeyPatch, captured: dict) -> None:
    # Re-applying before J+28 would recapture the baseline and the measurement
    # window would never mature.
    from datetime import UTC, datetime, timedelta

    _set_mode(monkeypatch, LearningMode.AUTO_APPLY)
    recent = (datetime.now(UTC) - timedelta(days=3)).isoformat()
    product = _product(
        proposed_meta_title="Harnais Premium pour Chien de Berger",
        current_meta_title="Old",
        auto_publish_fields=["meta_title"],
        applied_fields={"meta_title": recent},
    )
    summary = ma.auto_publish_checked_proposals("s.myshopify.com", {"products": [product]}, {})
    assert captured["applied"] == []
    assert summary["skipped_cooldown"] == 1


def test_field_past_cooldown_is_published(
    monkeypatch: pytest.MonkeyPatch, captured: dict
) -> None:
    from datetime import UTC, datetime, timedelta

    _set_mode(monkeypatch, LearningMode.AUTO_APPLY)
    old = (datetime.now(UTC) - timedelta(days=35)).isoformat()
    product = _product(
        proposed_meta_title="Harnais Premium pour Chien de Berger",
        current_meta_title="Old",
        auto_publish_fields=["meta_title"],
        applied_fields={"meta_title": old},
    )
    summary = ma.auto_publish_checked_proposals("s.myshopify.com", {"products": [product]}, {})
    assert summary["published"] == 1


def test_identical_image_alts_are_skipped(
    monkeypatch: pytest.MonkeyPatch, captured: dict
) -> None:
    _set_mode(monkeypatch, LearningMode.AUTO_APPLY)
    product = _product(
        proposed_image_alts=[{"image_id": "42", "proposed_alt": "Chat buvant à la fontaine"}],
        current_product_images=[{"id": "42", "current_alt": "Chat buvant à la fontaine"}],
        auto_publish_fields=["image_alts"],
    )
    summary = ma.auto_publish_checked_proposals("s.myshopify.com", {"products": [product]}, {})
    assert captured["applied"] == []
    assert summary["skipped_noop"] == 1


def test_auto_apply_cycle_records_a_learning_run(
    monkeypatch: pytest.MonkeyPatch, captured: dict
) -> None:
    _set_mode(monkeypatch, LearningMode.AUTO_APPLY)
    product = _product(
        proposed_meta_title="Harnais Premium pour Chien de Berger",
        current_meta_title="Old",
        auto_publish_fields=["meta_title"],
    )
    ma.auto_publish_checked_proposals("s.myshopify.com", {"products": [product]}, {})
    assert len(captured["runs"]) == 1
    assert captured["runs"][0]["auto_applied_count"] == 1


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
