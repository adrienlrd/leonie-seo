"""Regression tests for market-analysis proposal persistence boundaries."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import patch

from app.api.market_analysis import (
    _run_analysis_background,
    patch_market_analysis_proposals,
    save_market_analysis_facts,
)


def _analysis_result() -> dict:
    return {
        "analyzed_at": "2026-05-27T10:00:00+00:00",
        "active_product_count": 1,
        "analyzed_product_count": 1,
        "total_opportunity_count": 1,
        "sources_used": ["shopify_snapshot"],
        "provider_status": {"free": True},
        "competitor_signals": [],
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
        _analysis_result()["products"][0],
        "2026-05-27T10:00:00+00:00",
    )
