"""Read-only Shopify catalog crawl helpers for background audit jobs."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.db import DB_PATH
from app.db_adapter import get_conn
from scripts.audit.crawl_shopify import fetch_collections, fetch_products

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
    db_path: Path | None = None,
) -> None:
    now = datetime.now(UTC).isoformat()
    path = db_path if db_path is not None else DB_PATH
    rows = [
        (shop, now, "product", product["id"], json.dumps(product, ensure_ascii=False))
        for product in products
    ] + [
        (shop, now, "collection", collection["id"], json.dumps(collection, ensure_ascii=False))
        for collection in collections
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

    payload = {"products": products, "collections": collections}
    timestamp = _timestamp()
    root = raw_dir or _RAW_DIR
    shop_dir = root / shop
    latest_path = shop_dir / "shopify_snapshot.json"
    timestamped_path = shop_dir / f"snapshot_{timestamp}.json"

    _write_json(latest_path, payload)
    _write_json(timestamped_path, payload)
    _store_snapshot_rows(shop, products, collections, db_path=db_path)

    return {
        "status": "completed",
        "shop": shop,
        "products": len(products),
        "collections": len(collections),
        "snapshot_path": str(latest_path),
        "timestamped_snapshot_path": str(timestamped_path),
    }
