"""Tests for shop_config_store CRUD."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.shop_config_store import delete_shop_config, get_shop_config, set_shop_config


@pytest.fixture(autouse=True)
def _use_tmp_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db = tmp_path / "test.db"
    monkeypatch.setattr("app.shop_config_store.DB_PATH", db)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    from app.db import init_db
    init_db(db_path=db)


def test_get_returns_none_when_absent() -> None:
    assert get_shop_config("shop.myshopify.com", "pagespeed_api_key") is None


def test_set_and_get_roundtrip() -> None:
    set_shop_config("shop.myshopify.com", "pagespeed_api_key", "AIzaSy_test")
    assert get_shop_config("shop.myshopify.com", "pagespeed_api_key") == "AIzaSy_test"


def test_set_upserts_existing_key() -> None:
    set_shop_config("shop.myshopify.com", "pagespeed_api_key", "first")
    set_shop_config("shop.myshopify.com", "pagespeed_api_key", "second")
    assert get_shop_config("shop.myshopify.com", "pagespeed_api_key") == "second"


def test_delete_removes_key() -> None:
    set_shop_config("shop.myshopify.com", "pagespeed_api_key", "AIzaSy_test")
    delete_shop_config("shop.myshopify.com", "pagespeed_api_key")
    assert get_shop_config("shop.myshopify.com", "pagespeed_api_key") is None


def test_keys_are_shop_scoped() -> None:
    set_shop_config("shop-a.myshopify.com", "pagespeed_api_key", "key-a")
    set_shop_config("shop-b.myshopify.com", "pagespeed_api_key", "key-b")
    assert get_shop_config("shop-a.myshopify.com", "pagespeed_api_key") == "key-a"
    assert get_shop_config("shop-b.myshopify.com", "pagespeed_api_key") == "key-b"
