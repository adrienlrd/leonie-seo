"""Snapshot loading helpers shared by app API routes."""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Any

from app.db_adapter import DB_PATH, get_conn

# In-process cache for file-based snapshots. Snapshots are read on every
# dashboard/audit request and can weigh several MB; re-parsing them from disk on
# each call blocks worker threads needlessly. The cache key embeds the file path
# and its mtime, so a fresh crawl (which rewrites the file) invalidates the entry
# automatically and distinct files never collide. The DB-only fallback path is
# intentionally NOT cached: it is the degraded (ephemeral-disk) path and caching
# it would risk staleness without an mtime to key on.
_SNAPSHOT_CACHE_TTL_S = 60.0
_snapshot_cache: dict[str, tuple[float, float, dict[str, Any]]] = {}
_snapshot_cache_lock = threading.Lock()


def clear_snapshot_cache() -> None:
    """Drop all cached snapshots (used by tests and after forced re-crawls)."""
    with _snapshot_cache_lock:
        _snapshot_cache.clear()


def load_latest_snapshot_from_db(shop: str, db_path: Path | None = None) -> dict[str, Any] | None:
    """Return the latest product/collection snapshot for a shop from the DB."""
    path = db_path if db_path is not None else DB_PATH
    with get_conn(path) as conn:
        latest = conn.execute(
            """
            SELECT snapshot_date
            FROM snapshots
            WHERE shop = ?
            ORDER BY snapshot_date DESC
            LIMIT 1
            """,
            (shop,),
        ).fetchone()
        if latest is None:
            return None

        rows = conn.execute(
            """
            SELECT resource_type, data_json
            FROM snapshots
            WHERE shop = ? AND snapshot_date = ?
            ORDER BY resource_type, resource_id
            """,
            (shop, latest["snapshot_date"]),
        ).fetchall()

    products: list[dict[str, Any]] = []
    collections: list[dict[str, Any]] = []
    pages: list[dict[str, Any]] = []
    articles: list[dict[str, Any]] = []
    redirects: list[dict[str, Any]] = []
    for row in rows:
        try:
            resource = json.loads(row["data_json"])
        except (json.JSONDecodeError, TypeError):
            continue
        if row["resource_type"] == "product":
            products.append(resource)
        elif row["resource_type"] == "collection":
            collections.append(resource)
        elif row["resource_type"] == "page":
            pages.append(resource)
        elif row["resource_type"] == "article":
            articles.append(resource)
        elif row["resource_type"] == "url_redirect":
            redirects.append(resource)

    return {
        "snapshot_date": latest["snapshot_date"],
        "products": products,
        "collections": collections,
        "pages": pages,
        "articles": articles,
        "redirects": redirects,
    }


def load_snapshot_from_file_or_db(
    shop: str,
    snapshot_path: Path,
    db_path: Path | None = None,
) -> dict[str, Any] | None:
    """Load a tenant snapshot from disk, falling back to the DB.

    File-based results are cached in-process keyed by the file path + its mtime
    (so a re-crawl invalidates the entry) with a short TTL ceiling. A shallow copy
    is returned so callers cannot mutate the cached payload's top-level keys. The
    DB fallback is never cached.
    """
    try:
        mtime = snapshot_path.stat().st_mtime
    except OSError:
        mtime = None  # file missing -> DB fallback path (not cached)

    if mtime is None:
        return load_latest_snapshot_from_db(shop, db_path=db_path)

    now = time.monotonic()
    cache_key = str(snapshot_path)

    with _snapshot_cache_lock:
        cached = _snapshot_cache.get(cache_key)
        if cached is not None:
            cached_mtime, expires_at, payload = cached
            if cached_mtime == mtime and now < expires_at:
                return dict(payload)

    try:
        payload = json.loads(snapshot_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise RuntimeError("Snapshot file is corrupted") from exc

    if isinstance(payload, dict):
        with _snapshot_cache_lock:
            _snapshot_cache[cache_key] = (mtime, now + _SNAPSHOT_CACHE_TTL_S, payload)
        return dict(payload)

    return payload
