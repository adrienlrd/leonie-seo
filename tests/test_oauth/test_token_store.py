from pathlib import Path
from unittest.mock import patch

import pytest
from cryptography.fernet import Fernet

from app.oauth.token_store import delete_token, get_token, init_token_table, save_token

_TEST_KEY = Fernet.generate_key().decode()


@pytest.fixture(autouse=True)
def master_key():
    with patch.dict("os.environ", {"LEONIE_MASTER_KEY": _TEST_KEY}):
        yield


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


def test_token_is_encrypted_in_database(db: Path):
    """Critical: raw SQLite must never expose the plaintext access token."""
    import sqlite3

    save_token("mystore.myshopify.com", "shpat_super_secret", "read_products", db)
    with sqlite3.connect(db) as conn:
        raw = conn.execute(
            "SELECT access_token FROM shop_tokens WHERE shop = ?",
            ("mystore.myshopify.com",),
        ).fetchone()[0]
    assert raw.startswith("enc:")
    assert "shpat_super_secret" not in raw


def test_legacy_plaintext_token_still_readable(db: Path):
    """Tokens written before encryption was rolled out must keep working."""
    import sqlite3
    from datetime import UTC, datetime

    now = datetime.now(UTC).isoformat()
    with sqlite3.connect(db) as conn:
        conn.execute(
            "INSERT INTO shop_tokens VALUES (?, ?, ?, ?, ?)",
            ("legacy.myshopify.com", "shpat_unencrypted_legacy", "read_products", now, now),
        )
    record = get_token("legacy.myshopify.com", db)
    assert record["access_token"] == "shpat_unencrypted_legacy"
