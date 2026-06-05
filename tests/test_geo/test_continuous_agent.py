"""Tests for the continuous improvement GEO agent."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.db import init_db
from app.geo.continuous_agent import run_continuous_improvement_agent
from app.geo.continuous_improvement import set_product_tag
from app.geo.ledger import create_geo_event, list_geo_events

SHOP = "store.myshopify.com"
PRODUCT_ID = "gid://shopify/Product/1"


class _FakeRouter:
    def complete(
        self,
        prompt: str,
        *,
        system: str = "",
        max_tokens: int = 512,
        temperature: float = 0.3,
        json_mode: bool = False,
    ):
        from app.llm.provider import CompletionResult

        return CompletionResult(
            text="Meta title harnais chien confortable",
            provider="openai",
            model="gpt-4o-mini",
            tokens_in=10,
            tokens_out=8,
        )


def _latest_result() -> dict:
    return {
        "products": [
            {
                "product_id": PRODUCT_ID,
                "product_title": "Harnais chien",
                "product_handle": "harnais-chien",
                "target_customer": "Chien sensible",
                "buying_intents": ["choisir un harnais confortable"],
                "opportunity_score": 70,
                "seo_keywords": [
                    {
                        "query": "harnais chien confortable",
                        "product_fit_score": 80,
                        "data_source": "gsc",
                        "gsc_impressions": 320,
                        "gsc_clicks": 16,
                        "gsc_position": 8.5,
                        "reason": "Good fit.",
                    }
                ],
                "content_test_pack": {
                    "current_meta_title": "Harnais",
                    "current_meta_description": "",
                    "current_product_description_summary": "",
                    "proposed_meta_title": "",
                    "proposed_meta_description": "",
                    "proposed_product_description": "",
                    "proposed_faq": [],
                    "proposed_geo_answer_block": "",
                    "proposed_blog_title": "",
                    "proposed_image_alts": [],
                    "facts_missing": [],
                },
            }
        ]
    }


def test_agent_updates_tags_from_positive_feedback_and_creates_proposal(
    tmp_path: Path,
    monkeypatch,
) -> None:
    db = tmp_path / "history.db"
    init_db(db)
    data_dir = tmp_path / "data"
    shop_dir = data_dir / SHOP
    shop_dir.mkdir(parents=True)
    (shop_dir / "market_analysis_latest.json").write_text(
        json.dumps(_latest_result(), ensure_ascii=False),
        encoding="utf-8",
    )
    monkeypatch.setattr("app.market_analysis.jobs._DATA_DIR", data_dir)
    monkeypatch.setattr("app.geo.continuous_agent.DB_PATH", db)
    monkeypatch.setattr("app.geo.continuous_improvement.DB_PATH", db)
    monkeypatch.setattr("app.content_actions.runner.DB_PATH", db, raising=False)
    monkeypatch.setattr(
        "app.geo.continuous_agent.get_validated_niche_hypothesis", lambda shop: None
    )

    set_product_tag(
        SHOP,
        PRODUCT_ID,
        label="harnais chien confortable",
        tag_type="keyword",
        status="neutral",
        db_path=db,
    )
    event_id = create_geo_event(
        shop=SHOP,
        event_type="content_applied",
        resource_type="product",
        resource_id=PRODUCT_ID,
        resource_title="Harnais chien",
        action_type="meta_title",
        before_snapshot={},
        metrics_before={"clicks": 1},
        metrics_after={"clicks": 4},
        estimated_impact={},
        score_before=40,
        score_after=55,
        db_path=db,
    )
    created_at = (datetime.now(UTC) - timedelta(days=31)).isoformat()
    with __import__("app.db_adapter", fromlist=["get_conn"]).get_conn(db) as conn:
        conn.execute(
            "UPDATE geo_impact_events SET created_at = ? WHERE id = ?",
            (created_at, event_id),
        )

    result = run_continuous_improvement_agent(
        SHOP,
        plan="free",
        max_actions=1,
        llm_router=_FakeRouter(),
        db_path=db,
    )

    assert result["summary"]["feedback_tag_decisions"] >= 1
    assert result["summary"]["proposals_created"] == 1
    assert result["tag_decisions"][0]["status_after"] == "positive"
    assert result["proposals"][0]["content_type"] == "meta_title"
    assert result["proposals"][0]["applied"] is False
    events = list_geo_events(SHOP, limit=10, db_path=db)["events"]
    proposal_event = next(
        event for event in events if event["event_type"] == "continuous_improvement_proposal"
    )
    attribution = proposal_event["before_snapshot"]["optimization_attribution"]
    assert attribution["target_keyword"] == "harnais chien confortable"
    assert attribution["keyword_source"] == "gsc"
    assert "reinforce_tags" in attribution
    assert proposal_event["metrics_before"]["gsc"]["impressions"] == 320
    assert proposal_event["metrics_before"]["gsc"]["clicks"] == 16
