"""Tests for the AI templates publish / unpublish / webhook orchestration."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from app.apply.shopify_theme_files import ShopifyThemeError, ShopifyThemeScopeError
from app.db import init_db
from app.llms_txt import publisher, store

SHOP = "shop.myshopify.com"
THEME_ID = "gid://shopify/OnlineStoreTheme/1"

_BUSINESS = {"brand_name": "Léonie", "niche_summary": "Accessoires premium pour animaux."}


def _snapshot(extra_product: bool = False) -> dict:
    products = [
        {
            "id": "1",
            "title": "Harnais chien cuir",
            "handle": "harnais-chien-cuir",
            "description": "Harnais en cuir pleine fleur cousu main en France, garantie 2 ans.",
        }
    ]
    if extra_product:
        products.append(
            {
                "id": "2",
                "title": "Collier chat",
                "handle": "collier-chat",
                "description": "Collier réglable en cuir souple pour chat, fermoir sécurité inclus.",
            }
        )
    return {
        "shop": {"name": "Léonie", "primaryDomain": {"host": "leonie.com"}},
        "products": products,
        "collections": [],
        "pages": [],
    }


class FakeTheme:
    def __init__(self, theme_id: str = THEME_ID) -> None:
        self.theme_id = theme_id
        self.upserts: list[dict[str, str]] = []
        self.deletes: list[list[str]] = []

    def get_published_theme_id(self) -> str:
        return self.theme_id

    def upsert_templates(self, theme_id, files):  # noqa: ANN001
        self.upserts.append(files)
        return list(files.keys())

    def delete_templates(self, theme_id, filenames):  # noqa: ANN001
        self.deletes.append(filenames)
        return filenames


@pytest.fixture()
def db(tmp_path: Path) -> Path:
    path = tmp_path / "history.db"
    init_db(path)
    return path


def test_publish_writes_three_templates_and_saves_state(db: Path) -> None:
    theme = FakeTheme()
    result = publisher.publish(
        SHOP, "token", _snapshot(), _BUSINESS, db_path=db, theme_writer=theme
    )

    assert result["skipped"] is False
    assert result["public_url"] == "https://shop.myshopify.com/llms.txt"
    assert result["public_agents_url"] == "https://shop.myshopify.com/agents.md"
    # All three templates written, each wrapped in a raw block.
    written = theme.upserts[0]
    assert set(written) == {
        "templates/agents.md.liquid",
        "templates/llms.txt.liquid",
        "templates/llms-full.txt.liquid",
    }
    assert written["templates/llms.txt.liquid"].startswith("{% raw %}")

    row = store.get_publication(SHOP, db_path=db)
    assert row["is_published"] == 1
    assert row["theme_id"] == THEME_ID


def test_publish_is_idempotent_for_unchanged_content(db: Path) -> None:
    snap = _snapshot()
    publisher.publish(SHOP, "token", snap, _BUSINESS, db_path=db, theme_writer=FakeTheme())
    theme2 = FakeTheme()
    result = publisher.publish(SHOP, "token", snap, _BUSINESS, db_path=db, theme_writer=theme2)
    assert result["skipped"] is True
    assert theme2.upserts == []  # no re-write when content unchanged


def test_publish_rewrites_on_content_change(db: Path) -> None:
    publisher.publish(SHOP, "token", _snapshot(), _BUSINESS, db_path=db, theme_writer=FakeTheme())
    theme2 = FakeTheme()
    result = publisher.publish(
        SHOP, "token", _snapshot(extra_product=True), _BUSINESS, db_path=db, theme_writer=theme2
    )
    assert result["skipped"] is False
    assert len(theme2.upserts) == 1


def test_publish_propagates_scope_error(db: Path) -> None:
    class ScopeDenied(FakeTheme):
        def get_published_theme_id(self):
            raise ShopifyThemeScopeError("Reinstall the app")

    with pytest.raises(ShopifyThemeScopeError):
        publisher.publish(
            SHOP, "token", _snapshot(), _BUSINESS, db_path=db, theme_writer=ScopeDenied()
        )
    assert store.get_publication(SHOP, db_path=db) is None


def test_unpublish_deletes_templates(db: Path) -> None:
    publisher.publish(SHOP, "token", _snapshot(), _BUSINESS, db_path=db, theme_writer=FakeTheme())
    theme = FakeTheme()
    result = publisher.unpublish(SHOP, "token", db_path=db, theme_writer=theme)
    assert result["unpublished"] is True
    assert theme.deletes == [publisher.TEMPLATE_FILENAMES]
    assert store.get_publication(SHOP, db_path=db)["is_published"] == 0


def test_unpublish_noop_when_not_published(db: Path) -> None:
    result = publisher.unpublish(SHOP, "token", db_path=db, theme_writer=FakeTheme())
    assert result == {"unpublished": False, "reason": "not_published"}


def test_unpublish_is_best_effort_on_delete_error(db: Path) -> None:
    publisher.publish(SHOP, "token", _snapshot(), _BUSINESS, db_path=db, theme_writer=FakeTheme())

    class BadDelete(FakeTheme):
        def delete_templates(self, theme_id, filenames):
            raise ShopifyThemeError("not found")

    result = publisher.unpublish(SHOP, "token", db_path=db, theme_writer=BadDelete())
    assert result["unpublished"] is True  # local state cleared despite Shopify error
    assert store.get_publication(SHOP, db_path=db)["is_published"] == 0


def test_webhook_tick_noop_when_not_published(db: Path) -> None:
    result = publisher.handle_webhook_tick(
        SHOP, "token", _snapshot(), _BUSINESS, db_path=db, theme_writer=FakeTheme()
    )
    assert result["reason"] == "not_published"


def test_webhook_tick_is_debounced_within_window(db: Path) -> None:
    publisher.publish(SHOP, "token", _snapshot(), _BUSINESS, db_path=db, theme_writer=FakeTheme())
    t0 = datetime(2026, 5, 31, 12, 0, tzinfo=UTC)
    publisher.handle_webhook_tick(
        SHOP,
        "token",
        _snapshot(extra_product=True),
        _BUSINESS,
        now=t0,
        db_path=db,
        theme_writer=FakeTheme(),
    )
    second = publisher.handle_webhook_tick(
        SHOP,
        "token",
        _snapshot(extra_product=True),
        _BUSINESS,
        now=t0 + timedelta(minutes=2),
        db_path=db,
        theme_writer=FakeTheme(),
    )
    assert second == {"regenerated": False, "reason": "debounced"}


def test_webhook_tick_republishes_after_window(db: Path) -> None:
    publisher.publish(SHOP, "token", _snapshot(), _BUSINESS, db_path=db, theme_writer=FakeTheme())
    t0 = datetime(2026, 5, 31, 12, 0, tzinfo=UTC)
    store.record_webhook_tick(SHOP, t0.isoformat(), db_path=db)
    theme = FakeTheme()
    result = publisher.handle_webhook_tick(
        SHOP,
        "token",
        _snapshot(extra_product=True),
        _BUSINESS,
        now=t0 + timedelta(minutes=6),
        db_path=db,
        theme_writer=theme,
    )
    assert result["regenerated"] is True
    assert len(theme.upserts) == 1
