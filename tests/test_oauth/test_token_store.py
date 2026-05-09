from pathlib import Path

import pytest

from app.oauth.token_store import delete_token, get_token, init_token_table, save_token


@pytest.fixture()
def db(tmp_path: Path) -> Path:
    path = tmp_path / "test.db"
    init_token_table(path)
    return path


def test_save_and_retrieve_token(db: Path):
    save_token("mystore.myshopify.com", "shpat_abc", "read_products", db)
    record = get_token("mystore.myshopify.com", db)
    assert record is not None
    assert record["access_token"] == "shpat_abc"
    assert record["scope"] == "read_products"


def test_get_unknown_shop_returns_none(db: Path):
    assert get_token("nobody.myshopify.com", db) is None


def test_save_token_updates_access_token_and_scope(db: Path):
    save_token("mystore.myshopify.com", "shpat_v1", "read_products", db)
    save_token("mystore.myshopify.com", "shpat_v2", "write_products", db)
    record = get_token("mystore.myshopify.com", db)
    assert record["access_token"] == "shpat_v2"
    assert record["scope"] == "write_products"


def test_installed_at_preserved_on_update(db: Path):
    save_token("mystore.myshopify.com", "shpat_v1", "read_products", db)
    r1 = get_token("mystore.myshopify.com", db)
    save_token("mystore.myshopify.com", "shpat_v2", "write_products", db)
    r2 = get_token("mystore.myshopify.com", db)
    assert r1["installed_at"] == r2["installed_at"]


def test_delete_removes_token(db: Path):
    save_token("mystore.myshopify.com", "shpat_abc", "read_products", db)
    delete_token("mystore.myshopify.com", db)
    assert get_token("mystore.myshopify.com", db) is None


def test_delete_nonexistent_is_noop(db: Path):
    delete_token("nobody.myshopify.com", db)  # must not raise
