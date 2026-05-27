"""Regression tests for market-analysis proposal persistence boundaries."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import patch

from app.api.market_analysis import (
    _run_analysis_background,
    patch_market_analysis_proposals,
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
        "products": [{
            "product_id": "gid://shopify/Product/1",
            "content_test_pack": {
                "proposed_faq": [{"q": "Question ?", "a": "Réponse factuelle."}],
            },
        }],
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
    with patch("app.api.market_analysis.patch_product_proposals", return_value=True) as patch_proposals:
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
