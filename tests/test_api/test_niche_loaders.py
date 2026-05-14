"""Tests for the per-shop snapshot/GSC loaders in app.api.niche.

Covers two lot 4 wave 2 fixes:
- multi-tenant isolation: _load_snapshot/_load_gsc must only read from
  data/raw/{shop}/, never from the legacy flat path
- exception bug: the `except` tuple on _load_gsc had a nested tuple
  (KeyError, IndexError) wrapped inside another tuple, which raises
  TypeError at runtime instead of catching the inner exceptions
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from unittest.mock import patch

import pytest

from app.api import niche as niche_module
from app.db import init_db


@pytest.fixture()
def data_dir(tmp_path: Path):
    with patch.object(niche_module, "_DATA_DIR", tmp_path):
        yield tmp_path


def _write_snapshot(root: Path, shop: str, products: list[dict]) -> None:
    shop_dir = root / shop
    shop_dir.mkdir(parents=True, exist_ok=True)
    (shop_dir / "snapshot_2026-05-12.json").write_text(
        json.dumps({"products": products}), encoding="utf-8"
    )


def _write_gsc(root: Path, shop: str, rows: list[dict]) -> None:
    shop_dir = root / shop
    shop_dir.mkdir(parents=True, exist_ok=True)
    (shop_dir / "gsc_2026-05-12.json").write_text(json.dumps({"rows": rows}), encoding="utf-8")


def test_load_snapshot_returns_empty_when_shop_dir_missing(data_dir):
    assert niche_module._load_snapshot("nonexistent.myshopify.com") == []


def test_load_snapshot_returns_per_shop_products(data_dir):
    _write_snapshot(data_dir, "shop-a.myshopify.com", [{"id": 1, "title": "A1"}])
    _write_snapshot(data_dir, "shop-b.myshopify.com", [{"id": 2, "title": "B1"}])

    a = niche_module._load_snapshot("shop-a.myshopify.com")
    b = niche_module._load_snapshot("shop-b.myshopify.com")

    assert a == [{"id": 1, "title": "A1"}]
    assert b == [{"id": 2, "title": "B1"}]


def test_load_snapshot_does_not_fall_back_to_flat_path(data_dir):
    """Multi-tenant isolation: a legacy flat file must NOT be returned for
    a shop that has no per-shop snapshot directory. This used to leak one
    tenant's snapshot to all other tenants."""
    (data_dir / "snapshot_2026-05-12.json").write_text(
        json.dumps({"products": [{"id": 99, "title": "LEAK"}]}), encoding="utf-8"
    )
    result = niche_module._load_snapshot("any.myshopify.com")
    assert result == []


def test_load_snapshot_falls_back_to_db_snapshot(data_dir, tmp_path):
    db = tmp_path / "history.db"
    init_db(db)
    with sqlite3.connect(db) as conn:
        conn.execute(
            """
            INSERT INTO snapshots
                (shop, snapshot_date, resource_type, resource_id, data_json)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                "shop.myshopify.com",
                "2026-05-14T12:00:00Z",
                "product",
                "gid://shopify/Product/1",
                json.dumps({"id": "gid://shopify/Product/1", "title": "Harnais"}),
            ),
        )

    with patch("app.api.snapshot_store.DB_PATH", db):
        result = niche_module._load_snapshot("shop.myshopify.com")

    assert result == [{"id": "gid://shopify/Product/1", "title": "Harnais"}]


def test_load_gsc_returns_empty_when_shop_dir_missing(data_dir):
    assert niche_module._load_gsc("nonexistent.myshopify.com") == []


def test_load_gsc_returns_per_shop_rows(data_dir):
    _write_gsc(
        data_dir,
        "shop-a.myshopify.com",
        [{"query": "harnais", "impressions": 100, "clicks": 5, "position": 4.2}],
    )
    result = niche_module._load_gsc("shop-a.myshopify.com")
    assert len(result) == 1
    assert result[0]["query"] == "harnais"


def test_load_gsc_does_not_fall_back_to_flat_path(data_dir):
    (data_dir / "gsc_2026-05-12.json").write_text(
        json.dumps({"rows": [{"query": "leak", "impressions": 1, "clicks": 0, "position": 1.0}]}),
        encoding="utf-8",
    )
    assert niche_module._load_gsc("any.myshopify.com") == []


def test_load_gsc_swallows_malformed_json(data_dir):
    """The `except` block on _load_gsc had a nested-tuple typo that would
    raise TypeError instead of catching JSONDecodeError. Regression test."""
    shop_dir = data_dir / "shop.myshopify.com"
    shop_dir.mkdir(parents=True, exist_ok=True)
    (shop_dir / "gsc_2026-05-12.json").write_text("not-json", encoding="utf-8")
    # Must NOT raise; must return empty list.
    assert niche_module._load_gsc("shop.myshopify.com") == []
