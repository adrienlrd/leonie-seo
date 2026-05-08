"""Tests for scripts.apply.rollback."""

import sqlite3
from pathlib import Path

import pytest

from scripts.apply.rollback import (
    RollbackError,
    load_changes,
    mark_reverted,
    revert_row,
)

# ── Fixtures ──────────────────────────────────────────────────────────────────


def _make_db(path: str) -> None:
    conn = sqlite3.connect(path)
    conn.executescript("""
        CREATE TABLE seo_changes (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            applied_at    TEXT NOT NULL,
            resource_type TEXT NOT NULL,
            resource_id   TEXT NOT NULL,
            field         TEXT NOT NULL,
            old_value     TEXT,
            new_value     TEXT,
            status        TEXT NOT NULL DEFAULT 'applied'
        );
    """)
    conn.executemany(
        "INSERT INTO seo_changes (applied_at, resource_type, resource_id, field, old_value, new_value, status)"
        " VALUES (?, ?, ?, ?, ?, ?, ?)",
        [
            ("2026-05-05T10:00:00", "product", "gid://shopify/Product/1", "seo.title", "Old Title", "New Title", "applied"),
            ("2026-05-05T10:01:00", "product", "gid://shopify/Product/1", "seo.description", "Old Desc", "New Desc", "applied"),
            ("2026-05-05T10:02:00", "collection", "gid://shopify/Collection/2", "seo.title", "Old Col", "New Col", "applied"),
            ("2026-05-05T10:03:00", "product", "gid://shopify/Product/3", "image.altText:gid://shopify/ProductImage/99", None, "Alt text", "applied"),
            ("2026-05-05T10:04:00", "redirect", "/old-path", "url_redirect", None, "/new-path", "applied"),
            ("2026-05-05T10:05:00", "product", "gid://shopify/Product/5", "metafield.custom.json_ld", None, "{}", "applied"),
            ("2026-05-04T09:00:00", "product", "gid://shopify/Product/7", "seo.title", "Very Old", "Somewhat New", "reverted"),
        ],
    )
    conn.commit()
    conn.close()


@pytest.fixture()
def db_path(tmp_path: Path) -> str:
    path = str(tmp_path / "history.db")
    _make_db(path)
    return path


# ── load_changes ─────────────────────────────────────────────────────────────


def test_load_changes_returns_applied_only(db_path: str) -> None:
    rows = load_changes(db_path)
    assert all(r["status"] == "applied" for r in rows)
    assert len(rows) == 6  # row 7 is reverted


def test_load_changes_by_ids(db_path: str) -> None:
    rows = load_changes(db_path, ids=[1, 3])
    assert {r["id"] for r in rows} == {1, 3}


def test_load_changes_by_ids_skips_reverted(db_path: str) -> None:
    rows = load_changes(db_path, ids=[7])
    assert rows == []


def test_load_changes_since(db_path: str) -> None:
    rows = load_changes(db_path, since="2026-05-05T10:03:00")
    ids = {r["id"] for r in rows}
    assert 4 in ids and 5 in ids and 6 in ids
    assert 1 not in ids


def test_load_changes_since_ordered_desc(db_path: str) -> None:
    rows = load_changes(db_path, since="2026-05-05T10:00:00")
    ids = [r["id"] for r in rows]
    assert ids == sorted(ids, reverse=True)


# ── mark_reverted ─────────────────────────────────────────────────────────────


def test_mark_reverted_updates_status(db_path: str) -> None:
    mark_reverted(db_path, 1)
    conn = sqlite3.connect(db_path)
    row = conn.execute("SELECT status FROM seo_changes WHERE id = 1").fetchone()
    conn.close()
    assert row[0] == "reverted"


# ── revert_row ────────────────────────────────────────────────────────────────


def test_revert_row_product_seo_title(mocker) -> None:
    mock = mocker.patch("scripts.apply.rollback.update_product_seo")
    row = {
        "id": 1, "resource_type": "product", "resource_id": "gid://shopify/Product/1",
        "field": "seo.title", "old_value": "Old Title", "new_value": "New Title",
    }
    revert_row(row, endpoint="http://test", headers={})
    mock.assert_called_once_with(
        "gid://shopify/Product/1",
        seo_title="Old Title",
        seo_description=None,
        endpoint="http://test",
        headers={},
    )


def test_revert_row_collection_seo_description(mocker) -> None:
    mock = mocker.patch("scripts.apply.rollback.update_collection_seo")
    row = {
        "id": 3, "resource_type": "collection", "resource_id": "gid://shopify/Collection/2",
        "field": "seo.description", "old_value": "Old Desc", "new_value": "New Desc",
    }
    revert_row(row, endpoint="http://test", headers={})
    mock.assert_called_once_with(
        "gid://shopify/Collection/2",
        seo_title=None,
        seo_description="Old Desc",
        endpoint="http://test",
        headers={},
    )


def test_revert_row_image_alt_text(mocker) -> None:
    mock = mocker.patch("scripts.apply.rollback.update_image_alt")
    row = {
        "id": 4, "resource_type": "product", "resource_id": "gid://shopify/Product/3",
        "field": "image.altText:gid://shopify/ProductImage/99",
        "old_value": None, "new_value": "Alt text",
    }
    revert_row(row, endpoint="http://test", headers={})
    mock.assert_called_once_with(
        "gid://shopify/Product/3",
        "gid://shopify/ProductImage/99",
        "",  # old_value None becomes ""
        endpoint="http://test",
        headers={},
    )


def test_revert_row_url_redirect_raises(mocker) -> None:
    row = {
        "id": 5, "resource_type": "redirect", "resource_id": "/old-path",
        "field": "url_redirect", "old_value": None, "new_value": "/new-path",
    }
    with pytest.raises(RollbackError, match="cannot be reverted automatically"):
        revert_row(row)


def test_revert_row_metafield_raises(mocker) -> None:
    row = {
        "id": 6, "resource_type": "product", "resource_id": "gid://shopify/Product/5",
        "field": "metafield.custom.json_ld", "old_value": None, "new_value": "{}",
    }
    with pytest.raises(RollbackError, match="cannot be reverted automatically"):
        revert_row(row)


def test_revert_row_unknown_field_raises(mocker) -> None:
    row = {
        "id": 99, "resource_type": "product", "resource_id": "gid://shopify/Product/1",
        "field": "unknown.field", "old_value": "x", "new_value": "y",
    }
    with pytest.raises(RollbackError, match="Unknown field type"):
        revert_row(row)


def test_revert_row_wraps_shopify_error(mocker) -> None:
    from scripts.apply.update_meta import ShopifyUserError

    mocker.patch(
        "scripts.apply.rollback.update_product_seo",
        side_effect=ShopifyUserError("Shopify boom"),
    )
    row = {
        "id": 1, "resource_type": "product", "resource_id": "gid://shopify/Product/1",
        "field": "seo.title", "old_value": "Old", "new_value": "New",
    }
    with pytest.raises(RollbackError, match="Shopify boom"):
        revert_row(row, endpoint="http://test", headers={})
