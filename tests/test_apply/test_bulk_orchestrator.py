"""Tests for the bulk apply orchestrator."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from unittest.mock import MagicMock, patch

from app.apply.bulk_orchestrator import BulkApplyReport, apply_approved_meta
from app.apply.shopify_writer import ApplyResult, ShopifyWriter

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _init_db(db_path: Path) -> None:
    """Create minimal tables needed for orchestrator tests."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE IF NOT EXISTS meta_suggestions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            shop TEXT NOT NULL,
            product_id TEXT NOT NULL,
            product_title TEXT NOT NULL,
            generated_title TEXT,
            generated_description TEXT,
            provider TEXT,
            status TEXT DEFAULT 'pending',
            error TEXT,
            job_id TEXT,
            created_at TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS seo_changes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            shop TEXT,
            applied_at TEXT,
            resource_type TEXT,
            resource_id TEXT,
            field TEXT,
            old_value TEXT,
            new_value TEXT,
            status TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS shop_tokens (
            shop TEXT PRIMARY KEY,
            access_token TEXT,
            scope TEXT,
            installed_at TEXT,
            updated_at TEXT
        )
    """)
    conn.commit()
    conn.close()


def _insert_suggestion(db_path: Path, shop: str, product_id: str, status: str = "approved") -> int:
    conn = sqlite3.connect(db_path)
    cur = conn.execute(
        """INSERT INTO meta_suggestions
           (shop, product_id, product_title, generated_title, generated_description, status)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (
            shop,
            product_id,
            "Harnais chien",
            "New meta title",
            "New meta desc 140 chars " + "x" * 100,
            status,
        ),
    )
    conn.commit()
    row_id = cur.lastrowid
    conn.close()
    return row_id


_FAKE_TOKEN = {
    "shop": "test.myshopify.com",
    "access_token": "shpat_test_token",
    "scope": "write_products",
}


# ---------------------------------------------------------------------------
# ShopifyWriter unit tests
# ---------------------------------------------------------------------------


def test_shopify_writer_apply_product_seo_success():
    """Writer calls Shopify and returns ApplyResult(applied=True) on success."""
    mock_session = MagicMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "data": {"productUpdate": {"product": {"id": "gid://shopify/Product/1"}, "userErrors": []}}
    }
    mock_resp.raise_for_status = MagicMock()
    mock_session.post.return_value = mock_resp

    writer = ShopifyWriter("test.myshopify.com", "token", delay=0)
    writer._session = mock_session

    result = writer.apply_product_seo("gid://shopify/Product/1", "Title", "Desc")

    assert result.applied is True
    assert result.error is None
    assert mock_session.post.call_count == 1


def test_shopify_writer_returns_error_on_user_errors():
    mock_session = MagicMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "data": {"productUpdate": {"userErrors": [{"field": "title", "message": "too long"}]}}
    }
    mock_resp.raise_for_status = MagicMock()
    mock_session.post.return_value = mock_resp

    writer = ShopifyWriter("test.myshopify.com", "token", delay=0)
    writer._session = mock_session

    result = writer.apply_product_seo("gid://shopify/Product/1", "Title", None)

    assert result.applied is False
    assert "too long" in result.error


def test_shopify_writer_retries_on_429(tmp_path):
    """Writer retries up to max_retries on 429, then fails if still 429."""
    call_count = [0]

    mock_session = MagicMock()
    mock_resp_429 = MagicMock()
    mock_resp_429.status_code = 429
    mock_resp_429.headers = {"Retry-After": "0"}

    mock_resp_ok = MagicMock()
    mock_resp_ok.status_code = 200
    mock_resp_ok.json.return_value = {
        "data": {"productUpdate": {"product": {"id": "gid://shopify/Product/1"}, "userErrors": []}}
    }
    mock_resp_ok.raise_for_status = MagicMock()

    def side_effect(*args, **kwargs):
        call_count[0] += 1
        if call_count[0] < 2:
            return mock_resp_429
        return mock_resp_ok

    mock_session.post.side_effect = side_effect

    writer = ShopifyWriter("test.myshopify.com", "token", delay=0, max_retries=3)
    writer._session = mock_session

    result = writer.apply_product_seo("gid://shopify/Product/1", "Title", "Desc")

    assert result.applied is True
    assert call_count[0] == 2  # 1 retry was enough


def test_shopify_writer_skips_when_no_content():
    writer = ShopifyWriter("test.myshopify.com", "token", delay=0)
    result = writer.apply_product_seo("gid://shopify/Product/1", None, None)
    assert result.applied is False
    assert "no fields" in result.error


# ---------------------------------------------------------------------------
# BulkApplyReport
# ---------------------------------------------------------------------------


def test_bulk_apply_report_defaults():
    r = BulkApplyReport(shop="test.myshopify.com", dry_run=True)
    assert r.applied == 0
    assert r.skipped == 0
    assert r.errors == 0
    assert r.details == []


# ---------------------------------------------------------------------------
# apply_approved_meta — dry-run
# ---------------------------------------------------------------------------


def test_apply_approved_meta_dry_run(tmp_path):
    db = tmp_path / "test.db"
    _init_db(db)
    _insert_suggestion(db, "test.myshopify.com", "gid://shopify/Product/1")
    _insert_suggestion(db, "test.myshopify.com", "gid://shopify/Product/2")

    report = apply_approved_meta("test.myshopify.com", dry_run=True, db_path=db)

    assert report.dry_run is True
    assert report.skipped == 2
    assert report.applied == 0
    assert report.errors == 0
    assert len(report.details) == 2
    assert all(d["dry_run"] for d in report.details)


def test_apply_approved_meta_dry_run_no_suggestions(tmp_path):
    db = tmp_path / "test.db"
    _init_db(db)

    report = apply_approved_meta("no-shop.myshopify.com", dry_run=True, db_path=db)

    assert report.applied == 0
    assert report.skipped == 0


# ---------------------------------------------------------------------------
# apply_approved_meta — live mode
# ---------------------------------------------------------------------------


def test_apply_approved_meta_live_no_token(tmp_path):
    db = tmp_path / "test.db"
    _init_db(db)
    _insert_suggestion(db, "test.myshopify.com", "gid://shopify/Product/1")

    report = apply_approved_meta("test.myshopify.com", dry_run=False, db_path=db)

    assert report.skipped == 1
    assert report.applied == 0
    assert "no OAuth token" in report.details[0]["error"]


def test_apply_approved_meta_live_success(tmp_path):
    db = tmp_path / "test.db"
    _init_db(db)
    _insert_suggestion(db, "test.myshopify.com", "gid://shopify/Product/1")

    mock_result = ApplyResult(resource_id="gid://shopify/Product/1", applied=True)

    with patch("app.apply.bulk_orchestrator.get_token", return_value=_FAKE_TOKEN):
        with patch("app.apply.bulk_orchestrator.ShopifyWriter") as MockWriter:
            MockWriter.return_value.apply_product_seo.return_value = mock_result
            report = apply_approved_meta("test.myshopify.com", dry_run=False, delay=0, db_path=db)

    assert report.applied == 1
    assert report.errors == 0
    assert report.details[0]["applied"] is True


def test_apply_approved_meta_live_partial_failure(tmp_path):
    db = tmp_path / "test.db"
    _init_db(db)
    _insert_suggestion(db, "test.myshopify.com", "gid://shopify/Product/1")
    _insert_suggestion(db, "test.myshopify.com", "gid://shopify/Product/2")

    call_count = [0]

    def _side_effect(product_id, title, description):
        call_count[0] += 1
        if call_count[0] == 1:
            return ApplyResult(resource_id=product_id, applied=True)
        return ApplyResult(resource_id=product_id, applied=False, error="user error")

    with patch("app.apply.bulk_orchestrator.get_token", return_value=_FAKE_TOKEN):
        with patch("app.apply.bulk_orchestrator.ShopifyWriter") as MockWriter:
            MockWriter.return_value.apply_product_seo.side_effect = _side_effect
            report = apply_approved_meta("test.myshopify.com", dry_run=False, delay=0, db_path=db)

    assert report.applied == 1
    assert report.errors == 1


def test_apply_approved_meta_marks_applied_in_db(tmp_path):
    db = tmp_path / "test.db"
    _init_db(db)
    sid = _insert_suggestion(db, "test.myshopify.com", "gid://shopify/Product/1")

    mock_result = ApplyResult(resource_id="gid://shopify/Product/1", applied=True)

    with patch("app.apply.bulk_orchestrator.get_token", return_value=_FAKE_TOKEN):
        with patch("app.apply.bulk_orchestrator.ShopifyWriter") as MockWriter:
            MockWriter.return_value.apply_product_seo.return_value = mock_result
            apply_approved_meta("test.myshopify.com", dry_run=False, delay=0, db_path=db)

    conn = sqlite3.connect(db)
    row = conn.execute("SELECT status FROM meta_suggestions WHERE id = ?", (sid,)).fetchone()
    # Verify seo_changes rows are tagged with the shop (multi-tenant isolation).
    changes = conn.execute("SELECT shop FROM seo_changes").fetchall()
    conn.close()
    assert row[0] == "applied"
    assert all(c[0] == "test.myshopify.com" for c in changes)
    assert len(changes) >= 1


def test_apply_approved_meta_respects_max_per_run(tmp_path):
    db = tmp_path / "test.db"
    _init_db(db)
    for i in range(5):
        _insert_suggestion(db, "test.myshopify.com", f"gid://shopify/Product/{i}")

    with patch("app.apply.bulk_orchestrator.get_token", return_value=_FAKE_TOKEN):
        with patch("app.apply.bulk_orchestrator.ShopifyWriter") as MockWriter:
            MockWriter.return_value.apply_product_seo.return_value = ApplyResult(
                resource_id="x", applied=True
            )
            report = apply_approved_meta(
                "test.myshopify.com", dry_run=False, max_per_run=2, delay=0, db_path=db
            )

    assert report.applied == 2
