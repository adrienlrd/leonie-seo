"""Persistence for competitor crawl cache and run summaries."""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from app.db_adapter import DB_PATH, get_conn


def ensure_competitor_crawl_tables(db_path: Path | None = None) -> None:
    """Create competitor crawl tables when missing."""
    path = db_path if db_path is not None else DB_PATH
    is_postgres = os.getenv("DATABASE_URL") and (db_path is None or path == DB_PATH)
    id_type = "SERIAL PRIMARY KEY" if is_postgres else "INTEGER PRIMARY KEY AUTOINCREMENT"
    allowed_type = "BOOLEAN NOT NULL DEFAULT FALSE" if is_postgres else "INTEGER NOT NULL DEFAULT 0"
    with get_conn(path) as conn:
        conn.execute(
            f"""
            CREATE TABLE IF NOT EXISTS competitor_crawl_cache (
                id {id_type},
                url TEXT NOT NULL UNIQUE,
                domain TEXT NOT NULL,
                fetched_at TEXT NOT NULL,
                status_code INTEGER,
                final_url TEXT,
                allowed_by_robots {allowed_type},
                html_hash TEXT NOT NULL DEFAULT '',
                features_json TEXT NOT NULL DEFAULT '{{}}',
                error TEXT
            )
            """
        )
        conn.execute(
            f"""
            CREATE TABLE IF NOT EXISTS competitor_crawl_runs (
                id {id_type},
                shop TEXT NOT NULL,
                created_at TEXT NOT NULL,
                enabled {allowed_type},
                urls_selected INTEGER NOT NULL DEFAULT 0,
                urls_fetched INTEGER NOT NULL DEFAULT 0,
                urls_from_cache INTEGER NOT NULL DEFAULT 0,
                errors_count INTEGER NOT NULL DEFAULT 0,
                summary_json TEXT NOT NULL DEFAULT '{{}}'
            )
            """
        )


def get_cached_features(
    url: str,
    *,
    ttl_days: int,
    db_path: Path | None = None,
) -> dict[str, Any] | None:
    """Return cached crawl features when fresh enough."""
    ensure_competitor_crawl_tables(db_path)
    cutoff = datetime.now(UTC) - timedelta(days=ttl_days)
    path = db_path if db_path is not None else DB_PATH
    with get_conn(path) as conn:
        row = conn.execute(
            """
            SELECT url, domain, fetched_at, status_code, final_url, allowed_by_robots,
                   html_hash, features_json, error
            FROM competitor_crawl_cache
            WHERE url = ?
            """,
            (url,),
        ).fetchone()
    if not row:
        return None
    try:
        fetched_at = datetime.fromisoformat(str(row["fetched_at"]))
    except ValueError:
        return None
    if fetched_at < cutoff:
        return None
    features = _loads(row.get("features_json"), {})
    if not isinstance(features, dict):
        features = {}
    return {
        "url": row.get("url"),
        "domain": row.get("domain"),
        "fetched_at": row.get("fetched_at"),
        "status_code": row.get("status_code"),
        "final_url": row.get("final_url"),
        "allowed_by_robots": bool(row.get("allowed_by_robots")),
        "html_hash": row.get("html_hash") or "",
        "features": features,
        "error": row.get("error"),
    }


def upsert_cached_features(
    *,
    url: str,
    domain: str,
    status_code: int | None,
    final_url: str | None,
    allowed_by_robots: bool,
    html_hash: str,
    features: dict[str, Any],
    error: str | None,
    db_path: Path | None = None,
) -> None:
    """Store crawl features without storing full HTML."""
    ensure_competitor_crawl_tables(db_path)
    now = datetime.now(UTC).isoformat()
    path = db_path if db_path is not None else DB_PATH
    with get_conn(path) as conn:
        conn.execute(
            """
            INSERT INTO competitor_crawl_cache
                (url, domain, fetched_at, status_code, final_url, allowed_by_robots,
                 html_hash, features_json, error)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(url) DO UPDATE SET
                domain = excluded.domain,
                fetched_at = excluded.fetched_at,
                status_code = excluded.status_code,
                final_url = excluded.final_url,
                allowed_by_robots = excluded.allowed_by_robots,
                html_hash = excluded.html_hash,
                features_json = excluded.features_json,
                error = excluded.error
            """,
            (
                url,
                domain,
                now,
                status_code,
                final_url,
                1 if allowed_by_robots else 0,
                html_hash,
                json.dumps(features, ensure_ascii=False),
                error,
            ),
        )


def record_competitor_crawl_run(
    *,
    shop: str,
    enabled: bool,
    urls_selected: int,
    urls_fetched: int,
    urls_from_cache: int,
    errors_count: int,
    summary: dict[str, Any],
    db_path: Path | None = None,
) -> None:
    """Persist a compact competitor crawl run summary."""
    ensure_competitor_crawl_tables(db_path)
    path = db_path if db_path is not None else DB_PATH
    with get_conn(path) as conn:
        conn.execute(
            """
            INSERT INTO competitor_crawl_runs
                (shop, created_at, enabled, urls_selected, urls_fetched,
                 urls_from_cache, errors_count, summary_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                shop,
                datetime.now(UTC).isoformat(),
                1 if enabled else 0,
                urls_selected,
                urls_fetched,
                urls_from_cache,
                errors_count,
                json.dumps(summary, ensure_ascii=False),
            ),
        )


def _loads(value: Any, fallback: Any) -> Any:
    if not isinstance(value, str):
        return fallback
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return fallback
