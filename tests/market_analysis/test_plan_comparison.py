"""Tests for the Pro vs Grande boutique comparison tool (read-only diagnostic)."""

from __future__ import annotations

from unittest.mock import patch

from app.market_analysis import plan_comparison

SHOP = "store.myshopify.com"


def _inputs() -> dict:
    return {
        "snapshot": {"collections": ["c1"], "articles": []},
        "products": [{"id": str(i), "title": f"Product {i}"} for i in range(40)],
        "shop_domain": SHOP,
        "niche_hypothesis": {"primary_niche": "accessoires pour chats"},
        "crawl_findings": [],
        "gsc_page_rows": {},
        "gsc_query_rows": [],
        "ga4_page_rows": {},
        "identifications": {},
        "merchant_facts": {},
        "retired_questions": {},
        "business_profile": {},
        "merged_articles": [],
    }


def _fake_run_market_analysis(products, *args, **kwargs):  # noqa: ARG001
    plan = kwargs["plan"]
    sources = ["shopify_snapshot"]
    if kwargs.get("fetch_realtime") and kwargs.get("fetch_realtime_force"):
        sources.append("realtime_grounding")
    return {
        "shop": SHOP,
        "analyzed_at": "2026-07-15T00:00:00+00:00",
        "products": products,
        "sources_used": sources,
        "plan_seen": plan,
        "product_count_seen": len(products),
    }


def test_runs_pro_then_agency_on_shared_inputs() -> None:
    phases: list[str] = []
    with (
        patch.object(plan_comparison, "_gather_analysis_inputs", return_value=_inputs()) as mock_gather,
        patch.object(
            plan_comparison, "run_market_analysis", side_effect=_fake_run_market_analysis
        ) as mock_run,
    ):
        result = plan_comparison.run_plan_comparison(
            SHOP, access_token="shpat_test", on_phase=phases.append
        )

    # Inputs gathered exactly once — both runs must share identical source data.
    mock_gather.assert_called_once()
    assert phases == ["pro", "agency"]
    assert mock_run.call_count == 2

    pro_kwargs = mock_run.call_args_list[0].kwargs
    agency_kwargs = mock_run.call_args_list[1].kwargs
    assert pro_kwargs["plan"] == "pro"
    assert pro_kwargs["fetch_realtime"] is False
    assert pro_kwargs["fetch_realtime_force"] is False
    assert agency_kwargs["plan"] == "agency"
    assert agency_kwargs["fetch_realtime"] is True
    assert agency_kwargs["fetch_realtime_force"] is True

    assert result["pro"]["realtime_grounding_used"] is False
    assert result["agency"]["realtime_grounding_used"] is True
    assert "compared_at" in result
    assert result["shop"] == SHOP


def test_caps_products_per_plan_quota() -> None:
    with (
        patch.object(plan_comparison, "_gather_analysis_inputs", return_value=_inputs()),
        patch.object(
            plan_comparison, "run_market_analysis", side_effect=_fake_run_market_analysis
        ),
    ):
        result = plan_comparison.run_plan_comparison(SHOP, access_token="shpat_test")

    # 40 seed products, capped to each plan's product quota (pro=15, agency=35).
    assert result["pro"]["product_count_seen"] == 15
    assert result["agency"]["product_count_seen"] == 35


def test_never_persists_or_writes_to_shopify() -> None:
    """The module must not import any persistence or Shopify-write helper — a
    comparison run is purely diagnostic. Checking module globals (not the
    docstring/source text, which legitimately names these functions to explain
    what is deliberately NOT called).
    """
    module_names = set(vars(plan_comparison).keys())
    for forbidden in (
        "save_latest_result",
        "auto_publish_checked_proposals",
        "_auto_sync_schema_facts",
        "auto_create_orphan_drafts",
        "enrich_market_analysis_result",
    ):
        assert forbidden not in module_names
