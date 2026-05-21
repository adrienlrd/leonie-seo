"""Tests for rollback history and revert endpoints."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app

SHOP = "287c4a-bb.myshopify.com"

ENV = {
    "SHOPIFY_STORE_DOMAIN": SHOP,
    "SHOPIFY_ACCESS_TOKEN": "shpat_test",
    "SHOPIFY_CLIENT_ID": "client_id",
    "SHOPIFY_CLIENT_SECRET": "client_secret",
    "SHOPIFY_SCOPES": "read_products",
    "APP_URL": "https://example.com",
}


def _seed_changes(db_path: Path, shop: str) -> list[int]:
    """Insert test rows into seo_changes, return their IDs."""
    now = datetime.now(UTC).isoformat()
    rows = [
        (shop, now, "product", "gid://shopify/Product/1", "seo.title", "Old Title", "New Title", "applied"),
        (shop, now, "product", "gid://shopify/Product/1", "seo.description", "Old desc", "New desc", "applied"),
        (shop, now, "product", "gid://shopify/Product/2", "seo.title", None, "New Title 2", "applied"),
        (shop, now, "image", "gid://shopify/ProductImage/10", "image.alt_text", "old alt", "New Alt", "applied"),
        (shop, now, "product", "gid://shopify/Product/3", "seo.title", "Reverted Title", "Changed", "reverted"),
    ]
    with sqlite3.connect(db_path) as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS seo_changes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            shop TEXT, applied_at TEXT NOT NULL,
            resource_type TEXT NOT NULL, resource_id TEXT NOT NULL,
            field TEXT NOT NULL, old_value TEXT, new_value TEXT,
            status TEXT NOT NULL)""")
        for row in rows:
            conn.execute(
                "INSERT INTO seo_changes (shop, applied_at, resource_type, resource_id, field, old_value, new_value, status) VALUES (?,?,?,?,?,?,?,?)",
                row,
            )
        return [r[0] for r in conn.execute("SELECT id FROM seo_changes ORDER BY id").fetchall()]


@pytest.fixture()
def client():
    with patch.dict("os.environ", ENV):
        yield TestClient(app)


@pytest.fixture()
def db_with_changes(tmp_path: Path):
    db = tmp_path / "history.db"
    ids = _seed_changes(db, SHOP)
    return db, ids


def test_history_returns_changes(client, db_with_changes) -> None:
    db, ids = db_with_changes
    with (
        patch("app.api.deps.get_token", return_value=None),
        patch("app.api.rollback.DB_PATH", db),
    ):
        resp = client.get(f"/api/shops/{SHOP}/rollback/history")

    assert resp.status_code == 200
    data = resp.json()
    assert data["shop"] == SHOP
    assert data["total"] == 5
    assert len(data["changes"]) == 5


def test_history_revertible_flag(client, db_with_changes) -> None:
    db, ids = db_with_changes
    with (
        patch("app.api.deps.get_token", return_value=None),
        patch("app.api.rollback.DB_PATH", db),
    ):
        resp = client.get(f"/api/shops/{SHOP}/rollback/history")

    changes = resp.json()["changes"]
    by_field = {c["field"]: c for c in changes}
    # seo.title with old_value → revertible
    assert by_field["seo.title"]["revertible"] is True or any(
        c["field"] == "seo.title" and c["old_value"] and c["revertible"] for c in changes
    )
    # image.alt_text → NOT revertible (not in _REVERTIBLE_FIELDS)
    alt_entry = next(c for c in changes if c["field"] == "image.alt_text")
    assert alt_entry["revertible"] is False
    # reverted status → NOT revertible
    reverted_entry = next(c for c in changes if c["status"] == "reverted")
    assert reverted_entry["revertible"] is False


def test_history_no_old_value_not_revertible(client, db_with_changes) -> None:
    db, ids = db_with_changes
    with (
        patch("app.api.deps.get_token", return_value=None),
        patch("app.api.rollback.DB_PATH", db),
    ):
        resp = client.get(f"/api/shops/{SHOP}/rollback/history")

    changes = resp.json()["changes"]
    # Row with old_value=None should not be revertible
    no_old = next(c for c in changes if c["resource_id"] == "gid://shopify/Product/2")
    assert no_old["revertible"] is False


def test_history_filter_by_resource_type(client, db_with_changes) -> None:
    db, ids = db_with_changes
    with (
        patch("app.api.deps.get_token", return_value=None),
        patch("app.api.rollback.DB_PATH", db),
    ):
        resp = client.get(f"/api/shops/{SHOP}/rollback/history?resource_type=image")

    data = resp.json()
    assert all(c["resource_type"] == "image" for c in data["changes"])


def test_revert_dry_run(client, db_with_changes) -> None:
    db, ids = db_with_changes
    change_id = ids[0]  # seo.title with old_value
    with (
        patch("app.api.deps.get_token", return_value=None),
        patch("app.api.rollback.DB_PATH", db),
    ):
        resp = client.post(
            f"/api/shops/{SHOP}/rollback/{change_id}/revert",
            json={"dry_run": True, "confirm_live_write": False},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["dry_run"] is True
    assert data["status"] == "preview"
    assert "Old Title" in data["detail"]


def test_revert_unsupported_field_raises_422(client, db_with_changes) -> None:
    db, ids = db_with_changes
    image_change_id = ids[3]  # image.alt_text — not revertible
    with (
        patch("app.api.deps.get_token", return_value=None),
        patch("app.api.rollback.DB_PATH", db),
    ):
        resp = client.post(
            f"/api/shops/{SHOP}/rollback/{image_change_id}/revert",
            json={"dry_run": True},
        )

    assert resp.status_code == 422


def test_revert_no_old_value_raises_422(client, db_with_changes) -> None:
    db, ids = db_with_changes
    no_old_id = ids[2]  # seo.title with old_value=None
    with (
        patch("app.api.deps.get_token", return_value=None),
        patch("app.api.rollback.DB_PATH", db),
    ):
        resp = client.post(
            f"/api/shops/{SHOP}/rollback/{no_old_id}/revert",
            json={"dry_run": True},
        )

    assert resp.status_code == 422


def test_revert_already_reverted_raises_422(client, db_with_changes) -> None:
    db, ids = db_with_changes
    reverted_id = ids[4]  # status='reverted'
    with (
        patch("app.api.deps.get_token", return_value=None),
        patch("app.api.rollback.DB_PATH", db),
    ):
        resp = client.post(
            f"/api/shops/{SHOP}/rollback/{reverted_id}/revert",
            json={"dry_run": True},
        )

    assert resp.status_code == 422


def test_revert_not_found_raises_404(client, db_with_changes) -> None:
    db, _ = db_with_changes
    with (
        patch("app.api.deps.get_token", return_value=None),
        patch("app.api.rollback.DB_PATH", db),
    ):
        resp = client.post(
            f"/api/shops/{SHOP}/rollback/99999/revert",
            json={"dry_run": True},
        )

    assert resp.status_code == 404


def test_revert_live_calls_writer(client, db_with_changes) -> None:
    db, ids = db_with_changes
    change_id = ids[0]  # seo.title, old_value="Old Title"
    mock_result = MagicMock(applied=True, error=None)

    with (
        patch("app.api.deps.get_token", return_value=None),
        patch("app.api.rollback.DB_PATH", db),
        patch("app.api.rollback.ShopifyWriter") as MockWriter,
    ):
        MockWriter.return_value.apply_product_seo.return_value = mock_result
        resp = client.post(
            f"/api/shops/{SHOP}/rollback/{change_id}/revert",
            json={"dry_run": False, "confirm_live_write": True},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "reverted"
    assert data["dry_run"] is False

    # Verify DB status updated
    with sqlite3.connect(db) as conn:
        row = conn.execute("SELECT status FROM seo_changes WHERE id = ?", (change_id,)).fetchone()
    assert row[0] == "reverted"


def test_revert_stale_change_requires_confirm_stale(client, tmp_path) -> None:
    """Change > 90 days old must require confirm_stale_revert=true for live writes."""
    db = tmp_path / "stale.db"
    stale_date = (datetime.now(UTC) - timedelta(days=100)).isoformat()
    with sqlite3.connect(db) as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS seo_changes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            shop TEXT, applied_at TEXT NOT NULL,
            resource_type TEXT NOT NULL, resource_id TEXT NOT NULL,
            field TEXT NOT NULL, old_value TEXT, new_value TEXT,
            status TEXT NOT NULL)""")
        conn.execute(
            "INSERT INTO seo_changes VALUES (1,?,?,?,?,?,?,?,?)",
            (SHOP, stale_date, "product", "gid://shopify/Product/99",
             "seo.title", "Old Stale", "New Stale", "applied"),
        )

    with (
        patch("app.api.deps.get_token", return_value=None),
        patch("app.api.rollback.DB_PATH", db),
    ):
        # dry_run → OK but should include stale_warning
        resp_dry = client.post(
            f"/api/shops/{SHOP}/rollback/1/revert",
            json={"dry_run": True},
        )
        assert resp_dry.status_code == 200
        assert resp_dry.json().get("stale_warning") is not None

        # live without confirm_stale_revert → 409
        resp_live = client.post(
            f"/api/shops/{SHOP}/rollback/1/revert",
            json={"dry_run": False, "confirm_live_write": True, "confirm_stale_revert": False},
        )
        assert resp_live.status_code == 409
        assert "90" in resp_live.json()["detail"]

        # live with confirm_stale_revert → proceeds (writer called)
        mock_result = MagicMock(applied=True, error=None)
        with patch("app.api.rollback.ShopifyWriter") as MockWriter:
            MockWriter.return_value.apply_product_seo.return_value = mock_result
            resp_confirm = client.post(
                f"/api/shops/{SHOP}/rollback/1/revert",
                json={"dry_run": False, "confirm_live_write": True, "confirm_stale_revert": True},
            )
        assert resp_confirm.status_code == 200
        assert resp_confirm.json()["status"] == "reverted"


def test_log_seo_change_writes_to_db(tmp_path: Path) -> None:
    from app.api.rollback import log_seo_change

    db = tmp_path / "test.db"
    with sqlite3.connect(db) as conn:
        conn.execute("""CREATE TABLE seo_changes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            shop TEXT, applied_at TEXT NOT NULL,
            resource_type TEXT NOT NULL, resource_id TEXT NOT NULL,
            field TEXT NOT NULL, old_value TEXT, new_value TEXT,
            status TEXT NOT NULL)""")

    log_seo_change("shop.myshopify.com", "product", "gid://shopify/Product/1",
                   "seo.title", "Old", "New", db_path=db)

    with sqlite3.connect(db) as conn:
        row = conn.execute("SELECT * FROM seo_changes").fetchone()
    assert row is not None
    # id(0), shop(1), applied_at(2), resource_type(3), resource_id(4), field(5), old_value(6), new_value(7), status(8)
    assert row[3] == "product"
    assert row[4] == "gid://shopify/Product/1"
    assert row[8] == "applied"
