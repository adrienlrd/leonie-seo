"""Tests for the daily blog publisher."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from app.agent_schedule import daily_blog
from app.db import init_db
from app.learning.models import LearningMode, MerchantLearningSettings

SHOP = "store.myshopify.com"


def _db(tmp_path: Path) -> Path:
    db = tmp_path / "history.db"
    init_db(db)
    return db


def _settings(mode: LearningMode = LearningMode.AUTO_APPLY, scopes: list[str] | None = None):
    return MerchantLearningSettings(
        shop=SHOP,
        mode=mode,
        auto_publish_scopes=scopes if scopes is not None else ["blog_article"],
    )


def _analysis() -> dict[str, Any]:
    return {
        "products": [
            {
                "product_id": "1",
                "product_title": "Harnais",
                "seo_keywords": [{"query": "harnais chien", "search_volume": 5000}],
                "content_test_pack": {
                    "proposed_blog_ideas": [
                        {"title": "Guide harnais", "target_keyword": "harnais chien", "outline": ["Q1"]}
                    ]
                },
            }
        ]
    }


@pytest.fixture()
def wired(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    calls: dict[str, Any] = {"published": [], "drafts": []}
    monkeypatch.setattr(daily_blog, "get_settings", lambda shop, db_path=None: _settings())
    monkeypatch.setattr(daily_blog, "load_latest_result", lambda shop: _analysis())
    monkeypatch.setattr(daily_blog, "list_drafts", lambda shop: [])
    monkeypatch.setattr(daily_blog, "build_blog_idea_suggestions", lambda **kwargs: [])
    monkeypatch.setattr(daily_blog, "get_shop_language", lambda shop: "fr")
    monkeypatch.setattr(daily_blog, "load_gsc_index", lambda shop: ({}, 28))
    monkeypatch.setattr(daily_blog, "_write_sections", lambda shop, draft: [{"h2": "Q1", "body": "…"}])
    monkeypatch.setattr(
        daily_blog, "save_draft", lambda shop, draft: calls["drafts"].append(draft) or {**draft, "id": "d1"}
    )
    monkeypatch.setattr(daily_blog, "record_usage", lambda shop, kind, db_path=None: None)
    return calls


def _patch_blog_api(monkeypatch: pytest.MonkeyPatch, calls: dict[str, Any]) -> None:
    import app.api.blog as blog_api

    def fake_draft(shop, product_id, *, idea_override=None, blog_idea_index=None):
        return {
            "product_id": product_id,
            "blog_title": (idea_override or {}).get("title", ""),
            "target_keyword": (idea_override or {}).get("target_keyword", ""),
            "outline": (idea_override or {}).get("outline", []),
            "image_url": "https://cdn.shopify.com/img.png",
            "internal_links": [{"target_url": "/products/harnais", "anchor": "harnais chien"}],
        }

    def fake_publish(shop, token, draft_id, **kwargs):
        calls["published"].append((draft_id, kwargs))
        return {"draft": {}, "article": {"handle": "guide-harnais"}}

    monkeypatch.setattr(blog_api, "_draft_from_product", fake_draft)
    monkeypatch.setattr(blog_api, "publish_draft_to_shopify", fake_publish)


def test_publishes_the_best_idea_live(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, wired: dict
) -> None:
    _patch_blog_api(monkeypatch, wired)

    result = daily_blog.run_daily_blog(SHOP, access_token="shpua_tok", db_path=_db(tmp_path))

    assert result["status"] == "published"
    assert result["title"] == "Guide harnais"
    assert result["article_handle"] == "guide-harnais"
    assert result["traffic_score"]["traffic_source"] == "dataforseo"
    # Live, not a hidden Shopify draft.
    assert wired["published"][0][1]["published"] is True
    # The product image and the link back to the product ride along.
    draft = wired["drafts"][0]
    assert draft["image_url"]
    assert draft["internal_links"][0]["target_url"] == "/products/harnais"


def test_manual_mode_publishes_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, wired: dict
) -> None:
    monkeypatch.setattr(
        daily_blog, "get_settings", lambda shop, db_path=None: _settings(LearningMode.SEMI_AUTO)
    )
    _patch_blog_api(monkeypatch, wired)

    result = daily_blog.run_daily_blog(SHOP, access_token="tok", db_path=_db(tmp_path))

    assert result == {"status": "skipped", "reason": "manual_mode"}
    assert wired["published"] == []


def test_scope_is_opt_in(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, wired: dict) -> None:
    """A shop in auto mode without the blog scope must not start publishing."""
    monkeypatch.setattr(
        daily_blog, "get_settings", lambda shop, db_path=None: _settings(scopes=["meta_title"])
    )
    _patch_blog_api(monkeypatch, wired)

    result = daily_blog.run_daily_blog(SHOP, access_token="tok", db_path=_db(tmp_path))

    assert result["reason"] == "scope_disabled"
    assert wired["published"] == []


def test_only_one_article_per_day(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, wired: dict
) -> None:
    now = datetime(2026, 9, 19, 6, 0, tzinfo=UTC)
    monkeypatch.setattr(
        daily_blog,
        "list_drafts",
        lambda shop: [{"status": "published_to_shopify", "updated_at": "2026-09-19T05:00:00+00:00"}],
    )
    _patch_blog_api(monkeypatch, wired)

    result = daily_blog.run_daily_blog(SHOP, access_token="tok", now=now, db_path=_db(tmp_path))

    assert result["reason"] == "already_published_today"
    assert wired["published"] == []


def test_an_already_written_title_is_never_rewritten(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, wired: dict
) -> None:
    monkeypatch.setattr(
        daily_blog, "list_drafts", lambda shop: [{"blog_title": "Guide harnais", "status": "draft"}]
    )
    _patch_blog_api(monkeypatch, wired)

    result = daily_blog.run_daily_blog(SHOP, access_token="tok", db_path=_db(tmp_path))

    assert result["reason"] == "no_new_idea"
    assert wired["published"] == []


def test_a_publish_failure_is_reported_not_raised(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, wired: dict
) -> None:
    import app.api.blog as blog_api

    _patch_blog_api(monkeypatch, wired)
    monkeypatch.setattr(
        blog_api,
        "publish_draft_to_shopify",
        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("Shopify 502")),
    )

    result = daily_blog.run_daily_blog(SHOP, access_token="tok", db_path=_db(tmp_path))

    assert result["status"] == "error"
    assert "Shopify 502" in result["error"]
