"""Read-only Shopify catalog crawl helpers for background audit jobs."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.db import DB_PATH
from app.db_adapter import get_conn
from app.shop_identity import persist_storefront_host
from scripts.audit.crawl_shopify import (
    fetch_articles,
    fetch_collections,
    fetch_pages,
    fetch_products,
    fetch_shop_metadata,
)

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).parents[2]
_RAW_DIR = _PROJECT_ROOT / "data" / "raw"

# A snapshot younger than this is considered fresh enough to skip the crawl
# unless `force=True` is passed (e.g. by the manual Refresh button).
_FRESH_SNAPSHOT_SECONDS = 300  # 5 minutes


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
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def _snapshot_path(shop: str, root: Path | None = None) -> Path:
    return (root or _RAW_DIR) / shop / "shopify_snapshot.json"


def _snapshot_age_seconds(path: Path) -> float | None:
    if not path.exists():
        return None
    return time.time() - path.stat().st_mtime


def _store_snapshot_rows(
    shop: str,
    products: list[dict[str, Any]],
    collections: list[dict[str, Any]],
    pages: list[dict[str, Any]] | None = None,
    articles: list[dict[str, Any]] | None = None,
    db_path: Path | None = None,
) -> None:
    now = datetime.now(UTC).isoformat()
    path = db_path if db_path is not None else DB_PATH
    pages = pages or []
    articles = articles or []
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


async def crawl_shopify_catalog_for_job(
    shop: str,
    access_token: str,
    db_path: Path | None = None,
    raw_dir: Path | None = None,
    include_content_pages: bool = False,
    force: bool = False,
    **_legacy_kwargs: Any,
) -> dict[str, Any]:
    """Run a read-only Shopify catalog crawl and persist a tenant snapshot.

    Args:
        shop: Shopify shop domain.
        access_token: Shopify Admin API access token from the embedded session.
        db_path: Optional SQLite override for tests.
        raw_dir: Optional raw-data directory override for tests.
        include_content_pages: When True, also crawl CMS pages + blog articles.
            Default False — these are only consumed by ``/crawl/l3`` and are
            skipped on the fast refresh path to keep the job under 30 s.
        force: Bypass the freshness check and always re-crawl.

    Returns:
        Summary containing product/collection counts and snapshot paths.
        When the existing snapshot is fresh and ``force`` is False, returns
        ``status="skipped_fresh"`` without contacting Shopify.

    Notes:
        ``url_redirects`` is no longer fetched — the field was unused in the
        codebase. ``include_content_pages=True`` re-enables the heavier crawl
        for technical audits.

        Legacy keyword ``products_only`` is accepted for backward compatibility
        (``products_only=True`` == ``include_content_pages=False``).
    """
    # Backward-compat: translate the old `products_only` flag.
    if "products_only" in _legacy_kwargs:
        include_content_pages = not bool(_legacy_kwargs["products_only"])

    root = raw_dir or _RAW_DIR
    shop_dir = root / shop
    latest_path = shop_dir / "shopify_snapshot.json"

    # ── Freshness short-circuit ───────────────────────────────────────────
    age = _snapshot_age_seconds(latest_path)
    if not force and age is not None and age < _FRESH_SNAPSHOT_SECONDS:
        try:
            existing = json.loads(latest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            existing = {}
        logger.info("Snapshot for %s is fresh (%.0fs old) — skipping crawl", shop, age)
        return {
            "status": "skipped_fresh",
            "shop": shop,
            "snapshot_age_seconds": int(age),
            "products": len(existing.get("products", [])),
            "collections": len(existing.get("collections", [])),
            "pages": len(existing.get("pages", [])),
            "articles": len(existing.get("articles", [])),
            "snapshot_path": str(latest_path),
        }

    endpoint = _admin_endpoint(shop)
    headers = _admin_headers(access_token)

    # ── Parallel fetch of the 3 always-on resources ───────────────────────
    fetchers = [
        asyncio.to_thread(fetch_products, endpoint=endpoint, headers=headers),
        asyncio.to_thread(fetch_collections, endpoint=endpoint, headers=headers),
        asyncio.to_thread(fetch_shop_metadata, endpoint=endpoint, headers=headers),
    ]
    if include_content_pages:
        fetchers.extend([
            asyncio.to_thread(fetch_pages, endpoint=endpoint, headers=headers),
            asyncio.to_thread(fetch_articles, endpoint=endpoint, headers=headers),
        ])

    started = time.perf_counter()
    results = await asyncio.gather(*fetchers)
    elapsed = time.perf_counter() - started
    logger.info(
        "Shopify crawl for %s done in %.2fs (content_pages=%s)",
        shop, elapsed, include_content_pages,
    )

    products: list[dict[str, Any]] = results[0]
    collections: list[dict[str, Any]] = results[1]
    shop_metadata: dict[str, Any] = results[2]

    if include_content_pages:
        pages: list[dict[str, Any]] = results[3]
        articles: list[dict[str, Any]] = results[4]
    else:
        # Reuse existing pages/articles from the last full snapshot.
        existing: dict[str, Any] = {}
        if latest_path.exists():
            try:
                existing = json.loads(latest_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                pass
        pages = existing.get("pages", [])
        articles = existing.get("articles", [])

    payload = {
        "shop": shop_metadata,
        # ISO timestamp so the dashboard can compute snapshot age; without it
        # `_snapshot_age_days` returns None and the "data older than 7 days"
        # banner stays on permanently even right after a refresh.
        "snapshot_date": datetime.now(UTC).isoformat(),
        "products": products,
        "collections": collections,
        "pages": pages,
        "articles": articles,
        # `redirects` kept as empty list for snapshot shape stability; no consumers read it.
        "redirects": [],
    }
    timestamp = _timestamp()
    timestamped_path = shop_dir / f"snapshot_{timestamp}.json"

    _write_json(latest_path, payload)
    # Cache the shop's real primary domain so every feature can resolve the
    # storefront host generically (even when only the DB snapshot is available).
    persist_storefront_host(shop, shop_metadata)
    # Skip timestamped history copy on the fast refresh path — only write for full audits.
    if include_content_pages:
        _write_json(timestamped_path, payload)
    # Only persist the rows that were actually fetched; reused pages/articles
    # are already in the DB from the previous full snapshot.
    _store_snapshot_rows(
        shop,
        products,
        collections,
        pages=pages if include_content_pages else [],
        articles=articles if include_content_pages else [],
        db_path=db_path,
    )

    return {
        "status": "completed",
        "shop": shop,
        "elapsed_seconds": round(elapsed, 2),
        "products": len(products),
        "collections": len(collections),
        "pages": len(pages),
        "articles": len(articles),
        "snapshot_path": str(latest_path),
        "timestamped_snapshot_path": str(timestamped_path) if include_content_pages else None,
    }
