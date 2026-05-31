"""Tests for the AI discovery template publication store."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.db import init_db
from app.llms_txt import store

SHOP = "shop.myshopify.com"


@pytest.fixture()
def db(tmp_path: Path) -> Path:
    path = tmp_path / "history.db"
    init_db(path)
    return path


def _save(db: Path, **overrides) -> None:
    defaults = dict(
        theme_id="gid://shopify/OnlineStoreTheme/1",
        agents_hash="ahash1",
        llms_hash="lhash1",
        full_hash="fhash1",
        published_at="2026-05-31T10:00:00+00:00",
    )
    defaults.update(overrides)
    store.save_publication(SHOP, db_path=db, **defaults)


def test_get_publication_returns_none_when_absent(db: Path) -> None:
    assert store.get_publication(SHOP, db_path=db) is None


def test_save_then_get_publication(db: Path) -> None:
    _save(db)
    row = store.get_publication(SHOP, db_path=db)
    assert row is not None
    assert row["is_published"] == 1
    assert row["theme_id"] == "gid://shopify/OnlineStoreTheme/1"
    assert row["llms_hash"] == "lhash1"


def test_save_upserts_existing_row(db: Path) -> None:
    _save(db)
    _save(db, llms_hash="lhash2", theme_id="gid://shopify/OnlineStoreTheme/2")
    row = store.get_publication(SHOP, db_path=db)
    assert row["llms_hash"] == "lhash2"
    assert row["theme_id"] == "gid://shopify/OnlineStoreTheme/2"


def test_mark_unpublished_clears_resources(db: Path) -> None:
    _save(db)
    store.mark_unpublished(SHOP, db_path=db)
    row = store.get_publication(SHOP, db_path=db)
    assert row["is_published"] == 0
    assert row["theme_id"] is None
    assert row["llms_hash"] is None


def test_record_webhook_tick_returns_previous(db: Path) -> None:
    first = store.record_webhook_tick(SHOP, "2026-05-31T10:00:00+00:00", db_path=db)
    assert first is None
    second = store.record_webhook_tick(SHOP, "2026-05-31T10:06:00+00:00", db_path=db)
    assert second == "2026-05-31T10:00:00+00:00"
    row = store.get_publication(SHOP, db_path=db)
    assert row["last_webhook_tick_at"] == "2026-05-31T10:06:00+00:00"


def test_webhook_tick_does_not_flip_published_flag(db: Path) -> None:
    _save(db)
    store.record_webhook_tick(SHOP, "2026-05-31T11:00:00+00:00", db_path=db)
    row = store.get_publication(SHOP, db_path=db)
    assert row["is_published"] == 1  # tick must not unpublish a live template
