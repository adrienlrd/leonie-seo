"""Regression tests for market-analysis proposal persistence boundaries."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import patch

from app.api.market_analysis import (
    _run_analysis_background,
    get_latest_market_analysis,
    patch_market_analysis_proposals,
    save_market_analysis_facts,
)
from app.business_profile.context import build_business_profile_context_meta


def _analysis_result() -> dict:
    return {
        "analyzed_at": "2026-05-27T10:00:00+00:00",
        "active_product_count": 1,
        "analyzed_product_count": 1,
        "total_opportunity_count": 1,
        "sources_used": ["shopify_snapshot"],
        "provider_status": {"free": True},
        "competitor_signals": [],
        "cannibalization_alerts": [
            {
                "cluster_head": "harnais chien",
                "product_ids": ["gid://shopify/Product/1", "gid://shopify/Product/2"],
                "products": [],
                "winner_suggested": "gid://shopify/Product/1",
                "action": "reorient_secondary",
            }
        ],
        "orphan_products": ["gid://shopify/Product/1"],
        "blog_gap_suggestions": [
            {
                "cluster_head": "comment choisir un harnais chien",
                "suggested_title": "Comment choisir un harnais chien",
                "reason": "informational_intent_uncovered",
            }
        ],
        "products": [
            {
                "product_id": "gid://shopify/Product/1",
                "content_test_pack": {
                    "proposed_faq": [{"q": "Question ?", "a": "Réponse factuelle."}],
                },
            }
        ],
    }


def test_faq_is_not_published_when_analysis_job_completes() -> None:
    """Content generation stays a proposal until a publication mode applies it."""
    with (
        patch("app.api.market_analysis.run_market_analysis", return_value=_analysis_result()),
        patch("app.api.market_analysis.save_latest_result") as save_result,
        patch("app.api.market_analysis.update_job"),
    ):
        _run_analysis_background(
            "job-1",
            [],
            "shop.myshopify.com",
            {},
            [],
            {},
            None,
            None,
        )

    persisted = save_result.call_args.args[1]
    assert "faq_sync" not in persisted["products"][0]["content_test_pack"]


def test_analysis_background_persists_market_intelligence_fields() -> None:
    """Top-level analysis diagnostics remain visible after job completion."""
    with (
        patch("app.api.market_analysis.run_market_analysis", return_value=_analysis_result()),
        patch("app.api.market_analysis.save_latest_result") as save_result,
        patch("app.api.market_analysis.update_job") as update_job,
    ):
        _run_analysis_background(
            "job-intel",
            [],
            "shop.myshopify.com",
            {},
            [],
            {},
            None,
            None,
        )

    persisted = save_result.call_args.args[1]
    completed_update = update_job.call_args.kwargs
    assert persisted["cannibalization_alerts"][0]["cluster_head"] == "harnais chien"
    assert persisted["orphan_products"] == ["gid://shopify/Product/1"]
    assert persisted["blog_gap_suggestions"][0]["reason"] == "informational_intent_uncovered"
    assert completed_update["cannibalization_alerts"] == persisted["cannibalization_alerts"]


def test_analysis_background_passes_validated_business_profile_to_engine() -> None:
    """Product analysis uses the merchant-validated strategic profile when provided."""
    profile = {"brand_name": "Léonie", "status": "validated"}
    with (
        patch(
            "app.api.market_analysis.run_market_analysis", return_value=_analysis_result()
        ) as run,
        patch("app.api.market_analysis.save_latest_result"),
        patch("app.api.market_analysis.update_job"),
    ):
        _run_analysis_background(
            "job-profile",
            [],
            "shop.myshopify.com",
            {},
            [],
            {},
            None,
            None,
            business_profile=profile,
        )

    assert run.call_args.kwargs["business_profile"] == profile


def test_analysis_background_enables_reflection_by_default_for_product_analysis() -> None:
    """Standard product analysis now uses the guardrail reflection loop."""
    with (
        patch(
            "app.api.market_analysis.run_market_analysis", return_value=_analysis_result()
        ) as run,
        patch("app.api.market_analysis.save_latest_result") as save_result,
        patch("app.api.market_analysis.update_job"),
    ):
        _run_analysis_background(
            "job-reflection",
            [],
            "shop.myshopify.com",
            {},
            [],
            {},
            None,
            None,
        )

    assert run.call_args.kwargs["reflection_test"] is True
    assert save_result.call_args.args[1]["reflection_test"] is True


def test_faq_is_not_published_when_edited_proposal_is_saved() -> None:
    """The existing edit button persists a proposal without becoming a push."""
    ctx = SimpleNamespace(shop="shop.myshopify.com")
    with patch(
        "app.api.market_analysis.patch_product_proposals", return_value=True
    ) as patch_proposals:
        result = asyncio.run(
            patch_market_analysis_proposals(
                ctx=ctx,
                product_id="gid://shopify/Product/1",
                body={"proposed_faq": [{"q": "Question ?", "a": "Réponse."}]},
            )
        )

    assert result == {"saved": True, "faq_sync": None}
    patch_proposals.assert_called_once()
    saved_proposals = patch_proposals.call_args.args[2]
    assert saved_proposals["content_quality"] == {
        "publish_ready": False,
        "issues": ["merchant_edit_requires_revalidation"],
    }


def test_merchant_answers_are_saved_without_shopify_write() -> None:
    """Questionnaire answers only enrich the generation evidence store."""
    ctx = SimpleNamespace(shop="shop.myshopify.com")
    with patch(
        "app.api.market_analysis.save_merchant_facts",
        return_value={"warranty": "Garantie 2 ans."},
    ) as save_facts:
        result = asyncio.run(
            save_market_analysis_facts(
                ctx=ctx,
                product_id="gid://shopify/Product/1",
                body={
                    "answers": {
                        "warranty": "Garantie 2 ans.",
                        "unsupported_promise": "Meilleur du marché",
                    },
                },
            )
        )

    assert result["shopify_write"] is False
    assert result["saved"] == 1
    save_facts.assert_called_once_with(
        "shop.myshopify.com",
        "gid://shopify/Product/1",
        {"warranty": "Garantie 2 ans."},
    )


def test_fact_enriched_single_generation_replaces_proposal_without_shopify_write() -> None:
    """A completed questionnaire regeneration persists only its analysis result."""
    with (
        patch("app.api.market_analysis.run_market_analysis", return_value=_analysis_result()),
        patch("app.api.market_analysis.save_latest_result") as save_result,
        patch("app.api.market_analysis.replace_product_analysis") as replace_product,
        patch("app.api.market_analysis.update_job"),
    ):
        _run_analysis_background(
            "job-2",
            [],
            "shop.myshopify.com",
            {},
            [],
            {},
            None,
            None,
            persist=False,
            persist_product_results=True,
        )

    save_result.assert_not_called()
    replace_product.assert_called_once_with(
        "shop.myshopify.com",
        {
            **_analysis_result()["products"][0],
            "business_profile_context_status": "missing_profile",
        },
        "2026-05-27T10:00:00+00:00",
    )


def test_latest_analysis_marks_context_current_when_profile_hash_matches() -> None:
    """The latest endpoint reports that products used the current business profile."""
    profile = {"brand_name": "Léonie", "niche_summary": "Accessoires premium."}
    result = _analysis_result()
    context = build_business_profile_context_meta(profile)
    result["business_profile_context"] = context
    result["products"][0]["business_profile_context_hash"] = context["hash"]
    ctx = SimpleNamespace(shop="shop.myshopify.com")

    with (
        patch("app.api.market_analysis.load_latest_result", return_value=result),
        patch("app.api.market_analysis.load_business_profile", return_value=profile),
    ):
        latest = asyncio.run(get_latest_market_analysis(ctx=ctx))

    assert latest["business_profile_context_status"] == "current"
    assert latest["products"][0]["business_profile_context_status"] == "current"


def test_latest_analysis_marks_context_stale_when_profile_hash_changed() -> None:
    """The latest endpoint flags products generated with an older business profile."""
    old_profile = {"brand_name": "Léonie", "niche_summary": "Accessoires premium."}
    current_profile = {"brand_name": "Léonie", "niche_summary": "Accessoires chats urbains."}
    result = _analysis_result()
    context = build_business_profile_context_meta(old_profile)
    result["business_profile_context"] = context
    result["products"][0]["business_profile_context_hash"] = context["hash"]
    ctx = SimpleNamespace(shop="shop.myshopify.com")

    with (
        patch("app.api.market_analysis.load_latest_result", return_value=result),
        patch("app.api.market_analysis.load_business_profile", return_value=current_profile),
    ):
        latest = asyncio.run(get_latest_market_analysis(ctx=ctx))

    assert latest["business_profile_context_status"] == "stale"
    assert latest["products"][0]["business_profile_context_status"] == "stale"
