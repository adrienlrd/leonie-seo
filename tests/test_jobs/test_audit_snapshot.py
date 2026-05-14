"""Tests for read-only Shopify audit snapshot jobs."""

from __future__ import annotations

import json
import sqlite3

from app.db import init_db
from app.jobs.audit_snapshot import crawl_shopify_catalog_for_job


def test_crawl_shopify_catalog_for_job_writes_tenant_snapshot(tmp_path, monkeypatch):
    db = tmp_path / "history.db"
    raw_dir = tmp_path / "raw"
    init_db(db)

    products = [{"id": "gid://shopify/Product/1", "title": "Harnais chien"}]
    collections = [{"id": "gid://shopify/Collection/1", "title": "Chiens"}]
    monkeypatch.setattr("app.jobs.audit_snapshot.fetch_products", lambda **kw: products)
    monkeypatch.setattr("app.jobs.audit_snapshot.fetch_collections", lambda **kw: collections)

    result = crawl_shopify_catalog_for_job(
        "store.myshopify.com",
        "shpat_token",
        db_path=db,
        raw_dir=raw_dir,
    )

    latest = raw_dir / "store.myshopify.com" / "shopify_snapshot.json"
    timestamped = list((raw_dir / "store.myshopify.com").glob("snapshot_*.json"))
    assert result["products"] == 1
    assert result["collections"] == 1
    assert latest.exists()
    assert len(timestamped) == 1
    assert json.loads(latest.read_text())["products"] == products

    with sqlite3.connect(db) as conn:
        rows = conn.execute(
            "SELECT shop, resource_type, resource_id FROM snapshots ORDER BY resource_type"
        ).fetchall()
    assert rows == [
        ("store.myshopify.com", "collection", "gid://shopify/Collection/1"),
        ("store.myshopify.com", "product", "gid://shopify/Product/1"),
    ]


def test_crawl_shopify_catalog_for_job_uses_passed_shop_and_token(monkeypatch, tmp_path):
    calls: list[tuple[str, str]] = []

    def _fetch_products(endpoint, headers):
        calls.append((endpoint, headers["X-Shopify-Access-Token"]))
        return []

    monkeypatch.setattr("app.jobs.audit_snapshot.fetch_products", _fetch_products)
    monkeypatch.setattr("app.jobs.audit_snapshot.fetch_collections", lambda **kw: [])

    crawl_shopify_catalog_for_job(
        "store.myshopify.com",
        "shpat_real",
        db_path=tmp_path / "history.db",
        raw_dir=tmp_path / "raw",
    )

    assert calls == [("https://store.myshopify.com/admin/api/2025-01/graphql.json", "shpat_real")]
