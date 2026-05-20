"""Read-only Shopify catalog crawl helpers for background audit jobs."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.db import DB_PATH
from app.db_adapter import get_conn
from scripts.audit.crawl_shopify import (
    fetch_articles,
    fetch_collections,
    fetch_pages,
    fetch_products,
    fetch_shop_metadata,
    fetch_url_redirects,
)

_PROJECT_ROOT = Path(__file__).parents[2]
_RAW_DIR = _PROJECT_ROOT / "data" / "raw"


def _timestamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


def _admin_endpoint(shop: str) -> str:
    return f"https://{shop}/admin/api/2025-01/graphql.json"


def _admin_headers(access_token: str) -> dict[str, str]:
    return {
        "X-Shopify-Access-Token": access_token,
        "Content-Type": "application/json",
    }


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _store_snapshot_rows(
    shop: str,
    products: list[dict[str, Any]],
    collections: list[dict[str, Any]],
    pages: list[dict[str, Any]] | None = None,
    articles: list[dict[str, Any]] | None = None,
    redirects: list[dict[str, Any]] | None = None,
    db_path: Path | None = None,
) -> None:
    now = datetime.now(UTC).isoformat()
    path = db_path if db_path is not None else DB_PATH
    pages = pages or []
    articles = articles or []
    redirects = redirects or []
    rows = [
        (shop, now, "product", product["id"], json.dumps(product, ensure_ascii=False))
        for product in products
    ] + [
        (shop, now, "collection", collection["id"], json.dumps(collection, ensure_ascii=False))
        for collection in collections
    ] + [
        (shop, now, "page", page["id"], json.dumps(page, ensure_ascii=False))
        for page in pages
    ] + [
        (shop, now, "article", article["id"], json.dumps(article, ensure_ascii=False))
        for article in articles
    ] + [
        (shop, now, "url_redirect", redirect["id"], json.dumps(redirect, ensure_ascii=False))
        for redirect in redirects
    ]

    if not rows:
        return

    with get_conn(path) as conn:
        for row in rows:
            conn.execute(
                """
                INSERT INTO snapshots
                    (shop, snapshot_date, resource_type, resource_id, data_json)
                VALUES (?, ?, ?, ?, ?)
                """,
                row,
            )


def crawl_shopify_catalog_for_job(
    shop: str,
    access_token: str,
    db_path: Path | None = None,
    raw_dir: Path | None = None,
) -> dict[str, Any]:
    """Run a read-only Shopify catalog crawl and persist a tenant snapshot.

    Args:
        shop: Shopify shop domain.
        access_token: Shopify Admin API access token from the embedded session.
        db_path: Optional SQLite override for tests.
        raw_dir: Optional raw-data directory override for tests.

    Returns:
        Summary containing product/collection counts and snapshot paths.
    """
    endpoint = _admin_endpoint(shop)
    headers = _admin_headers(access_token)
    products = fetch_products(endpoint=endpoint, headers=headers)
    collections = fetch_collections(endpoint=endpoint, headers=headers)
    pages = fetch_pages(endpoint=endpoint, headers=headers)
    articles = fetch_articles(endpoint=endpoint, headers=headers)
    redirects = fetch_url_redirects(endpoint=endpoint, headers=headers)
    shop_metadata = fetch_shop_metadata(endpoint=endpoint, headers=headers)

    payload = {
        "shop": shop_metadata,
        "products": products,
        "collections": collections,
        "pages": pages,
        "articles": articles,
        "redirects": redirects,
    }
    timestamp = _timestamp()
    root = raw_dir or _RAW_DIR
    shop_dir = root / shop
    latest_path = shop_dir / "shopify_snapshot.json"
    timestamped_path = shop_dir / f"snapshot_{timestamp}.json"

    _write_json(latest_path, payload)
    _write_json(timestamped_path, payload)
    _store_snapshot_rows(
        shop,
        products,
        collections,
        pages=pages,
        articles=articles,
        redirects=redirects,
        db_path=db_path,
    )

    return {
        "status": "completed",
        "shop": shop,
        "products": len(products),
        "collections": len(collections),
        "pages": len(pages),
        "articles": len(articles),
        "redirects": len(redirects),
        "snapshot_path": str(latest_path),
        "timestamped_snapshot_path": str(timestamped_path),
    }
