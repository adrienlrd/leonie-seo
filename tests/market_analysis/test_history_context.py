"""Tests for the optimization-history context fed into the analysis prompts (Task 6)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from app.db import init_db
from app.geo.auto_tracking import record_applied_change
from app.learning.store import upsert_weight
from app.market_analysis import engine
from app.market_analysis.history_context import (
    build_optimization_history,
    format_optimization_history,
)

_SHOP = "test.myshopify.com"
_PRODUCT_ID = "gid://shopify/Product/1"

_PASS1_JSON = json.dumps(
    {
        "product_summary": "Fontaine à eau pour chat, 2 litres, filtre charbon.",
        "target_customer": "Propriétaires de chats exigeants.",
        "buying_intents": ["hydratation", "silence"],
        "seo_keywords": [
            {
                "query": "fontaine à chat",
                "intent_type": "commercial",
                "demand_score": 50,
                "competition_score": 40,
                "product_fit_score": 90,
                "reason": "produit principal",
            }
        ],
        "geo_questions": [],
    }
)

_PASS2_JSON = json.dumps(
    {
        "proposed_meta_title": "Fontaine à chat silencieuse 2L — eau filtrée en continu",
        "proposed_meta_description": "Hydratez votre chat avec une eau toujours fraîche et filtrée.",
        "proposed_product_title_if_different": "Fontaine à chat 2L",
        "proposed_product_description": "Une fontaine silencieuse qui oxygène l'eau.",
        "proposed_faq": [],
        "proposed_geo_answer_block": "La fontaine à chat oxygène l'eau en continu.",
        "proposed_blog_title": "",
        "proposed_blog_outline": [],
        "proposed_blog_intro": "",
        "recommended_content_actions": [],
        "facts_used": [],
        "facts_missing": [],
        "claims_used": [],
        "confidence": "high",
    }
)


class _FakeDataForSEO:
    available = False


def _product():
    return {
        "id": _PRODUCT_ID,
        "title": "Fontaine à chat",
        "handle": "fontaine-chat",
        "status": "ACTIVE",
        "body_html": "<p>Fontaine 2L</p>",
        "seo": {"title": "Fontaine chat", "description": ""},
        "variants": [{"price": "29.90", "inventory_quantity": 15}],
    }


def _router(*texts):
    from app.llm.provider import CompletionResult  # noqa: PLC0415

    router = MagicMock()
    router.complete.side_effect = [
        CompletionResult(text=t, provider="openai", model="gpt-4o-mini") for t in texts
    ]
    return router


def _run(router, *, db_path: Path):
    budget = {
        "over_budget": False,
        "budget_usd": 20.0,
        "spent_usd": 0.0,
        "remaining_usd": 20.0,
        "usage_pct": 0.0,
        "alert": None,
    }
    with (
        patch.object(engine, "get_router", return_value=router),
        patch.object(engine, "check_budget", return_value=budget),
        patch.object(engine, "_fetch_trends_once", return_value=[]),
        patch.object(engine, "fetch_suggestions_bulk", return_value=[]),
        patch.object(engine, "DataForSEOProvider", return_value=_FakeDataForSEO()),
    ):
        return engine.run_market_analysis(
            [_product()],
            _SHOP,
            {},
            [],
            db_path=db_path,
        )


def test_build_optimization_history_empty_when_no_events(tmp_path: Path) -> None:
    db = tmp_path / "history.db"
    init_db(db)

    history = build_optimization_history(_SHOP, _PRODUCT_ID, db_path=db)

    assert history["events"] == []
    assert history["older_count"] == 0
    assert history["shop_summary"] == ""
    assert format_optimization_history(history) == ""


def test_build_optimization_history_includes_applied_event_and_shop_summary(
    tmp_path: Path,
) -> None:
    db = tmp_path / "history.db"
    init_db(db)

    record_applied_change(
        shop=_SHOP,
        resource_type="product",
        resource_id=_PRODUCT_ID,
        resource_title="Fontaine à chat",
        action_type="meta_title",
        field="meta_title",
        old_value="Ancien titre",
        new_value="Nouveau titre",
        db_path=db,
    )
    upsert_weight(
        scope="merchant",
        shop=_SHOP,
        feature_key="action_type",
        feature_value="meta_title",
        weight=0.8,
        sample_size=3,
        confidence=70,
        db_path=db,
    )
    upsert_weight(
        scope="merchant",
        shop=_SHOP,
        feature_key="action_type",
        feature_value="blog_publish",
        weight=-0.5,
        sample_size=2,
        confidence=60,
        db_path=db,
    )

    history = build_optimization_history(_SHOP, _PRODUCT_ID, db_path=db)

    assert len(history["events"]) == 1
    event = history["events"][0]
    assert event["field"] == "meta_title"
    assert event["old_value"] == "Ancien titre"
    assert event["new_value"] == "Nouveau titre"
    assert "meta_title" in history["shop_summary"]
    assert "blog_publish" in history["shop_summary"]

    rendered = format_optimization_history(history)
    assert "HISTORIQUE D'OPTIMISATION" in rendered
    assert "Ancien titre" in rendered
    assert "Nouveau titre" in rendered
    assert "RÈGLE HISTORIQUE" in rendered


def test_format_optimization_history_handles_event_without_old_or_new_value() -> None:
    """Continuous-agent applied events have no before/after text, only field+verdict."""
    history = {
        "events": [
            {
                "field": "meta_title",
                "old_value": None,
                "new_value": None,
                "applied_at": "2026-05-01T00:00:00+00:00",
                "verdict": "neutre",
                "confidence": 40,
            }
        ],
        "older_count": 0,
        "shop_summary": "",
    }

    rendered = format_optimization_history(history)

    assert '" → "' not in rendered
    assert "  - [2026-05-01] meta_title — verdict: neutre (confiance 40/100)" in rendered


def test_run_market_analysis_omits_history_section_when_no_past_events(tmp_path: Path) -> None:
    db = tmp_path / "history.db"
    init_db(db)

    router = _router(_PASS1_JSON, _PASS2_JSON)
    _run(router, db_path=db)

    pass1_prompt = router.complete.call_args_list[0].args[0]
    pass2_prompt = router.complete.call_args_list[1].args[0]
    assert "HISTORIQUE D'OPTIMISATION" not in pass1_prompt
    assert "HISTORIQUE D'OPTIMISATION" not in pass2_prompt


def test_run_market_analysis_includes_history_section_when_past_event_exists(
    tmp_path: Path,
) -> None:
    db = tmp_path / "history.db"
    init_db(db)

    record_applied_change(
        shop=_SHOP,
        resource_type="product",
        resource_id=_PRODUCT_ID,
        resource_title="Fontaine à chat",
        action_type="meta_title",
        field="meta_title",
        old_value="Ancien titre",
        new_value="Nouveau titre",
        db_path=db,
    )

    router = _router(_PASS1_JSON, _PASS2_JSON)
    _run(router, db_path=db)

    pass1_prompt = router.complete.call_args_list[0].args[0]
    pass2_prompt = router.complete.call_args_list[1].args[0]
    assert "HISTORIQUE D'OPTIMISATION" in pass1_prompt
    assert "Ancien titre" in pass1_prompt
    assert "HISTORIQUE D'OPTIMISATION" in pass2_prompt
    assert "RÈGLE HISTORIQUE" in pass2_prompt
