"""Tests for read-only Shopify audit snapshot jobs."""

from __future__ import annotations

import asyncio
import json
import sqlite3

from app.db import init_db
from app.jobs.audit_snapshot import crawl_shopify_catalog_for_job


def _run(coro):
    return asyncio.run(coro)


def test_default_skips_content_pages_and_redirects(tmp_path, monkeypatch):
    db = tmp_path / "history.db"
    raw_dir = tmp_path / "raw"
    init_db(db)

    fetched: list[str] = []

    def _track(name, value):
        def _fn(**_kw):
            fetched.append(name)
            return value
        return _fn

    monkeypatch.setattr(
        "app.jobs.audit_snapshot.fetch_products",
        _track("products", [{"id": "gid://shopify/Product/1", "title": "Harnais chien"}]),
    )
    monkeypatch.setattr(
        "app.jobs.audit_snapshot.fetch_collections",
        _track("collections", [{"id": "gid://shopify/Collection/1", "title": "Chiens"}]),
    )
    monkeypatch.setattr(
        "app.jobs.audit_snapshot.fetch_shop_metadata",
        _track("shop", {"myshopifyDomain": "store.myshopify.com"}),
    )
    monkeypatch.setattr(
        "app.jobs.audit_snapshot.fetch_pages",
        _track("pages", [{"id": "x"}]),
    )
    monkeypatch.setattr(
        "app.jobs.audit_snapshot.fetch_articles",
        _track("articles", [{"id": "y"}]),
    )

    result = _run(
        crawl_shopify_catalog_for_job(
            "store.myshopify.com",
            "shpat_token",
            db_path=db,
            raw_dir=raw_dir,
        )
    )

    # Fast path: only products + collections + shop metadata fetched.
    assert sorted(fetched) == ["collections", "products", "shop"]
    assert result["status"] == "completed"
    assert result["products"] == 1
    assert result["collections"] == 1
    assert result["pages"] == 0
    assert result["articles"] == 0

    # No timestamped history copy on the fast path.
    timestamped = list((raw_dir / "store.myshopify.com").glob("snapshot_*.json"))
    assert timestamped == []


def test_include_content_pages_fetches_pages_and_articles(tmp_path, monkeypatch):
    db = tmp_path / "history.db"
    raw_dir = tmp_path / "raw"
    init_db(db)

    products = [{"id": "gid://shopify/Product/1", "title": "Harnais chien"}]
    collections = [{"id": "gid://shopify/Collection/1", "title": "Chiens"}]
    pages = [{"id": "gid://shopify/Page/1", "title": "About", "handle": "about"}]
    articles = [{"id": "gid://shopify/Article/1", "title": "Guide", "handle": "guide"}]
    monkeypatch.setattr("app.jobs.audit_snapshot.fetch_products", lambda **kw: products)
    monkeypatch.setattr("app.jobs.audit_snapshot.fetch_collections", lambda **kw: collections)
    monkeypatch.setattr("app.jobs.audit_snapshot.fetch_pages", lambda **kw: pages)
    monkeypatch.setattr("app.jobs.audit_snapshot.fetch_articles", lambda **kw: articles)
    monkeypatch.setattr(
        "app.jobs.audit_snapshot.fetch_shop_metadata",
        lambda **kw: {"myshopifyDomain": "store.myshopify.com"},
    )

    result = _run(
        crawl_shopify_catalog_for_job(
            "store.myshopify.com",
            "shpat_token",
            db_path=db,
            raw_dir=raw_dir,
            include_content_pages=True,
        )
    )

    assert result["products"] == 1
    assert result["pages"] == 1
    assert result["articles"] == 1
    assert result["timestamped_snapshot_path"] is not None

    latest = raw_dir / "store.myshopify.com" / "shopify_snapshot.json"
    payload = json.loads(latest.read_text())
    assert payload["products"] == products
    assert payload["pages"] == pages
    assert payload["articles"] == articles
    # url_redirects is no longer fetched
    assert payload["redirects"] == []

    timestamped = list((raw_dir / "store.myshopify.com").glob("snapshot_*.json"))
    assert len(timestamped) == 1

    with sqlite3.connect(db) as conn:
        rows = conn.execute(
            "SELECT resource_type FROM snapshots ORDER BY resource_type"
        ).fetchall()
    assert [r[0] for r in rows] == ["article", "collection", "page", "product"]


def test_passes_shop_and_token_to_endpoint(monkeypatch, tmp_path):
    calls: list[tuple[str, str]] = []

    def _fetch_products(endpoint, headers):
        calls.append((endpoint, headers["X-Shopify-Access-Token"]))
        return []

    monkeypatch.setattr("app.jobs.audit_snapshot.fetch_products", _fetch_products)
    monkeypatch.setattr("app.jobs.audit_snapshot.fetch_collections", lambda **kw: [])
    monkeypatch.setattr("app.jobs.audit_snapshot.fetch_shop_metadata", lambda **kw: {})

    _run(
        crawl_shopify_catalog_for_job(
            "store.myshopify.com",
            "shpat_real",
            db_path=tmp_path / "history.db",
            raw_dir=tmp_path / "raw",
        )
    )

    assert calls == [("https://store.myshopify.com/admin/api/2025-01/graphql.json", "shpat_real")]


def test_fresh_snapshot_skips_crawl(tmp_path, monkeypatch):
    """A snapshot less than 5 min old should short-circuit without hitting Shopify."""
    raw_dir = tmp_path / "raw"
    shop_dir = raw_dir / "store.myshopify.com"
    shop_dir.mkdir(parents=True)
    (shop_dir / "shopify_snapshot.json").write_text(
        json.dumps({"products": [{"id": "x"}], "collections": [], "pages": [], "articles": []}),
        encoding="utf-8",
    )

    called = False

    def _should_not_be_called(**_kw):
        nonlocal called
        called = True
        return []

    monkeypatch.setattr("app.jobs.audit_snapshot.fetch_products", _should_not_be_called)
    monkeypatch.setattr("app.jobs.audit_snapshot.fetch_collections", _should_not_be_called)
    monkeypatch.setattr("app.jobs.audit_snapshot.fetch_shop_metadata", _should_not_be_called)

    result = _run(
        crawl_shopify_catalog_for_job(
            "store.myshopify.com",
            "shpat_token",
            db_path=tmp_path / "history.db",
            raw_dir=raw_dir,
        )
    )

    assert result["status"] == "skipped_fresh"
    assert result["products"] == 1
    assert called is False


def test_force_bypasses_freshness_check(tmp_path, monkeypatch):
    raw_dir = tmp_path / "raw"
    shop_dir = raw_dir / "store.myshopify.com"
    shop_dir.mkdir(parents=True)
    (shop_dir / "shopify_snapshot.json").write_text(
        json.dumps({"products": [], "collections": [], "pages": [], "articles": []}),
        encoding="utf-8",
    )

    monkeypatch.setattr("app.jobs.audit_snapshot.fetch_products", lambda **kw: [{"id": "new"}])
    monkeypatch.setattr("app.jobs.audit_snapshot.fetch_collections", lambda **kw: [])
    monkeypatch.setattr("app.jobs.audit_snapshot.fetch_shop_metadata", lambda **kw: {})

    init_db(tmp_path / "history.db")
    result = _run(
        crawl_shopify_catalog_for_job(
            "store.myshopify.com",
            "shpat_token",
            db_path=tmp_path / "history.db",
            raw_dir=raw_dir,
            force=True,
        )
    )

    assert result["status"] == "completed"
    assert result["products"] == 1


def test_snapshot_written_with_fresh_date(tmp_path, monkeypatch):
    """The written snapshot must carry a parseable snapshot_date so the dashboard
    does not flag a just-refreshed catalog as stale (age None -> always stale)."""
    from app.api.audit import _snapshot_age_days

    raw_dir = tmp_path / "raw"

    monkeypatch.setattr("app.jobs.audit_snapshot.fetch_products", lambda **kw: [{"id": "p1"}])
    monkeypatch.setattr("app.jobs.audit_snapshot.fetch_collections", lambda **kw: [])
    monkeypatch.setattr("app.jobs.audit_snapshot.fetch_shop_metadata", lambda **kw: {})

    init_db(tmp_path / "history.db")
    _run(
        crawl_shopify_catalog_for_job(
            "store.myshopify.com",
            "shpat_token",
            db_path=tmp_path / "history.db",
            raw_dir=raw_dir,
        )
    )

    payload = json.loads(
        (raw_dir / "store.myshopify.com" / "shopify_snapshot.json").read_text(encoding="utf-8")
    )
    assert "snapshot_date" in payload
    age = _snapshot_age_days(payload)
    assert age == 0


def test_legacy_products_only_kwarg_still_accepted(tmp_path, monkeypatch):
    """products_only=True (legacy) ≡ include_content_pages=False."""
    fetched: list[str] = []

    monkeypatch.setattr(
        "app.jobs.audit_snapshot.fetch_products",
        lambda **_kw: (fetched.append("products") or []),
    )
    monkeypatch.setattr(
        "app.jobs.audit_snapshot.fetch_collections",
        lambda **_kw: (fetched.append("collections") or []),
    )
    monkeypatch.setattr(
        "app.jobs.audit_snapshot.fetch_shop_metadata",
        lambda **_kw: (fetched.append("shop") or {}),
    )

    init_db(tmp_path / "history.db")
    result = _run(
        crawl_shopify_catalog_for_job(
            "store.myshopify.com",
            "shpat_token",
            db_path=tmp_path / "history.db",
            raw_dir=tmp_path / "raw",
            products_only=True,
        )
    )

    assert sorted(fetched) == ["collections", "products", "shop"]
    assert result["status"] == "completed"
