"""Centralized database initialization for all app tables.

Called once at startup from app/main.py. Uses Postgres when DATABASE_URL is set
(production / Neon), SQLite otherwise (local dev / tests).
"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

from app.db_adapter import DB_PATH  # single canonical path, re-exported for consumers

__all__ = ["DB_PATH", "init_db"]

# ── SQLite DDL ─────────────────────────────────────────────────────────────────

_SQLITE_DDL = [
    """CREATE TABLE IF NOT EXISTS shop_tokens (
        shop         TEXT PRIMARY KEY,
        access_token TEXT NOT NULL,
        scope        TEXT,
        installed_at TEXT NOT NULL,
        updated_at   TEXT NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS google_tokens (
        shop         TEXT PRIMARY KEY,
        token_json   TEXT NOT NULL,
        scopes       TEXT,
        email        TEXT,
        created_at   TEXT NOT NULL,
        updated_at   TEXT NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS oauth_states (
        state      TEXT PRIMARY KEY,
        created_at REAL NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS seo_changes (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        shop          TEXT,
        applied_at    TEXT NOT NULL,
        resource_type TEXT NOT NULL,
        resource_id   TEXT NOT NULL,
        field         TEXT NOT NULL,
        old_value     TEXT,
        new_value     TEXT,
        status        TEXT NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS snapshots (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        shop          TEXT,
        snapshot_date TEXT NOT NULL,
        resource_type TEXT NOT NULL,
        resource_id   TEXT NOT NULL,
        data_json     TEXT NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS gdpr_requests (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        received_at TEXT NOT NULL,
        topic       TEXT NOT NULL,
        shop        TEXT NOT NULL,
        payload     TEXT NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS subscriptions (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        shop            TEXT NOT NULL UNIQUE,
        subscription_id TEXT,
        plan            TEXT NOT NULL DEFAULT 'free',
        status          TEXT NOT NULL DEFAULT 'pending',
        created_at      TEXT NOT NULL,
        updated_at      TEXT NOT NULL
    )""",
    # LLM meta suggestions (Phase 7, task 60)
    """CREATE TABLE IF NOT EXISTS meta_suggestions (
        id                  INTEGER PRIMARY KEY AUTOINCREMENT,
        shop                TEXT NOT NULL,
        product_id          TEXT NOT NULL,
        product_title       TEXT NOT NULL,
        generated_title     TEXT,
        generated_description TEXT,
        provider            TEXT,
        status              TEXT NOT NULL DEFAULT 'pending',
        error               TEXT,
        job_id              TEXT,
        created_at          TEXT NOT NULL DEFAULT (datetime('now'))
    )""",
    # LLM usage metrics (Phase 7, task 68)
    """CREATE TABLE IF NOT EXISTS llm_metrics (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        shop        TEXT,
        provider    TEXT NOT NULL,
        model       TEXT NOT NULL,
        tokens_in   INTEGER NOT NULL DEFAULT 0,
        tokens_out  INTEGER NOT NULL DEFAULT 0,
        cost_usd    REAL NOT NULL DEFAULT 0.0,
        latency_ms  REAL NOT NULL DEFAULT 0.0,
        error       TEXT,
        called_at   TEXT NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS llm_cache (
        shop           TEXT NOT NULL,
        task_name      TEXT NOT NULL,
        prompt_version TEXT NOT NULL,
        content_hash   TEXT NOT NULL,
        response_json  TEXT NOT NULL,
        tokens_in      INTEGER NOT NULL DEFAULT 0,
        tokens_out     INTEGER NOT NULL DEFAULT 0,
        created_at     TEXT NOT NULL,
        expires_at     TEXT NOT NULL,
        PRIMARY KEY (shop, task_name, prompt_version, content_hash)
    )""",
    # Semantic embeddings (Phase 8, task 70) — stored as JSON text for SQLite
    """CREATE TABLE IF NOT EXISTS product_embeddings (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        shop          TEXT NOT NULL,
        product_id    TEXT NOT NULL,
        product_title TEXT NOT NULL DEFAULT '',
        embedding     TEXT NOT NULL,
        model         TEXT NOT NULL DEFAULT 'intfloat/multilingual-e5-base',
        created_at    TEXT NOT NULL DEFAULT (datetime('now')),
        UNIQUE(shop, product_id)
    )""",
    """CREATE TABLE IF NOT EXISTS query_embeddings (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        shop       TEXT NOT NULL,
        query      TEXT NOT NULL,
        embedding  TEXT NOT NULL,
        model      TEXT NOT NULL DEFAULT 'intfloat/multilingual-e5-base',
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        UNIQUE(shop, query)
    )""",
    # Generic per-shop key/value config (Phase 10, task 89+)
    """CREATE TABLE IF NOT EXISTS shop_config (
        shop  TEXT NOT NULL,
        key   TEXT NOT NULL,
        value TEXT NOT NULL,
        PRIMARY KEY (shop, key)
    )""",
    # Async job queue (Phase 6, task 55)
    """CREATE TABLE IF NOT EXISTS jobs (
        id           TEXT PRIMARY KEY,
        queue        TEXT NOT NULL,
        payload      TEXT NOT NULL,
        shop         TEXT,
        status       TEXT NOT NULL DEFAULT 'pending',
        priority     INTEGER NOT NULL DEFAULT 0,
        retries      INTEGER NOT NULL DEFAULT 0,
        max_retries  INTEGER NOT NULL DEFAULT 3,
        scheduled_at TEXT NOT NULL,
        started_at   TEXT,
        completed_at TEXT,
        result       TEXT,
        created_at   TEXT NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS geo_impact_events (
        id                 INTEGER PRIMARY KEY AUTOINCREMENT,
        shop               TEXT NOT NULL,
        created_at         TEXT NOT NULL,
        event_type         TEXT NOT NULL,
        resource_type      TEXT NOT NULL,
        resource_id        TEXT NOT NULL,
        resource_title     TEXT NOT NULL DEFAULT '',
        action_type        TEXT NOT NULL,
        status             TEXT NOT NULL DEFAULT 'planned',
        source             TEXT NOT NULL DEFAULT 'geo',
        job_id             TEXT,
        snapshot_id        INTEGER,
        hypothesis         TEXT,
        score_before       INTEGER,
        score_after        INTEGER,
        measurement_status TEXT NOT NULL DEFAULT 'not_started',
        status_history     TEXT,
        before_snapshot    TEXT NOT NULL,
        after_snapshot     TEXT,
        metrics_before     TEXT NOT NULL,
        metrics_after      TEXT,
        estimated_impact   TEXT NOT NULL,
        observed_impact    TEXT,
        notes              TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS geo_optimization_snapshots (
        id                 INTEGER PRIMARY KEY AUTOINCREMENT,
        shop               TEXT NOT NULL,
        created_at         TEXT NOT NULL,
        resource_type      TEXT NOT NULL,
        resource_id        TEXT NOT NULL,
        resource_title     TEXT NOT NULL DEFAULT '',
        action_type        TEXT NOT NULL,
        source             TEXT NOT NULL DEFAULT 'geo',
        hypothesis         TEXT,
        snapshot_json      TEXT NOT NULL,
        metrics_json       TEXT NOT NULL,
        readiness_score    INTEGER NOT NULL DEFAULT 0,
        seo_score          INTEGER NOT NULL DEFAULT 0,
        content_hash       TEXT NOT NULL DEFAULT '',
        notes              TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS crawl_findings (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        shop          TEXT NOT NULL,
        created_at    TEXT NOT NULL,
        source        TEXT NOT NULL DEFAULT 'crawl_l3',
        url           TEXT NOT NULL,
        issue_type    TEXT NOT NULL,
        severity      TEXT NOT NULL,
        detail        TEXT NOT NULL,
        metadata_json TEXT NOT NULL DEFAULT '{}'
    )""",
    # Unified content actions drafts (Phase 11.8, task 145)
    """CREATE TABLE IF NOT EXISTS content_actions (
        action_id      TEXT PRIMARY KEY,
        shop           TEXT NOT NULL,
        content_type   TEXT NOT NULL,
        resource_id    TEXT NOT NULL,
        resource_handle TEXT NOT NULL DEFAULT '',
        result_json    TEXT NOT NULL,
        status         TEXT NOT NULL DEFAULT 'draft',
        retry_count    INTEGER NOT NULL DEFAULT 0,
        created_at     TEXT NOT NULL,
        updated_at     TEXT NOT NULL
    )""",
]

# ── Postgres DDL ───────────────────────────────────────────────────────────────
_PG_SHOP_CONFIG = """CREATE TABLE IF NOT EXISTS shop_config (
    shop  TEXT NOT NULL,
    key   TEXT NOT NULL,
    value TEXT NOT NULL,
    PRIMARY KEY (shop, key)
)"""
_PG_EMBEDDINGS = [
    "CREATE EXTENSION IF NOT EXISTS vector",
    """CREATE TABLE IF NOT EXISTS product_embeddings (
        id            SERIAL PRIMARY KEY,
        shop          TEXT NOT NULL,
        product_id    TEXT NOT NULL,
        product_title TEXT NOT NULL DEFAULT '',
        embedding     vector(768),
        model         TEXT NOT NULL DEFAULT 'intfloat/multilingual-e5-base',
        created_at    TIMESTAMP NOT NULL DEFAULT NOW(),
        UNIQUE(shop, product_id)
    )""",
    """CREATE TABLE IF NOT EXISTS query_embeddings (
        id         SERIAL PRIMARY KEY,
        shop       TEXT NOT NULL,
        query      TEXT NOT NULL,
        embedding  vector(768),
        model      TEXT NOT NULL DEFAULT 'intfloat/multilingual-e5-base',
        created_at TIMESTAMP NOT NULL DEFAULT NOW(),
        UNIQUE(shop, query)
    )""",
]

_PG_LLM_METRICS = """CREATE TABLE IF NOT EXISTS llm_metrics (
    id          SERIAL PRIMARY KEY,
    shop        TEXT,
    provider    TEXT NOT NULL,
    model       TEXT NOT NULL,
    tokens_in   INTEGER NOT NULL DEFAULT 0,
    tokens_out  INTEGER NOT NULL DEFAULT 0,
    cost_usd    DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    latency_ms  DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    error       TEXT,
    called_at   TEXT NOT NULL
)"""

_PG_LLM_CACHE = """CREATE TABLE IF NOT EXISTS llm_cache (
    shop           TEXT NOT NULL,
    task_name      TEXT NOT NULL,
    prompt_version TEXT NOT NULL,
    content_hash   TEXT NOT NULL,
    response_json  TEXT NOT NULL,
    tokens_in      INTEGER NOT NULL DEFAULT 0,
    tokens_out     INTEGER NOT NULL DEFAULT 0,
    created_at     TEXT NOT NULL,
    expires_at     TEXT NOT NULL,
    PRIMARY KEY (shop, task_name, prompt_version, content_hash)
)"""

_PG_DDL = [
    """CREATE TABLE IF NOT EXISTS meta_suggestions (
        id                    SERIAL PRIMARY KEY,
        shop                  TEXT NOT NULL,
        product_id            TEXT NOT NULL,
        product_title         TEXT NOT NULL,
        generated_title       TEXT,
        generated_description TEXT,
        provider              TEXT,
        status                TEXT NOT NULL DEFAULT 'pending',
        error                 TEXT,
        job_id                TEXT,
        created_at            TIMESTAMP NOT NULL DEFAULT NOW()
    )""",
    """CREATE TABLE IF NOT EXISTS shop_tokens (
        shop         TEXT PRIMARY KEY,
        access_token TEXT NOT NULL,
        scope        TEXT,
        installed_at TEXT NOT NULL,
        updated_at   TEXT NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS google_tokens (
        shop         TEXT PRIMARY KEY,
        token_json   TEXT NOT NULL,
        scopes       TEXT,
        email        TEXT,
        created_at   TEXT NOT NULL,
        updated_at   TEXT NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS oauth_states (
        state      TEXT PRIMARY KEY,
        created_at DOUBLE PRECISION NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS seo_changes (
        id            SERIAL PRIMARY KEY,
        shop          TEXT,
        applied_at    TEXT NOT NULL,
        resource_type TEXT NOT NULL,
        resource_id   TEXT NOT NULL,
        field         TEXT NOT NULL,
        old_value     TEXT,
        new_value     TEXT,
        status        TEXT NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS snapshots (
        id            SERIAL PRIMARY KEY,
        shop          TEXT,
        snapshot_date TEXT NOT NULL,
        resource_type TEXT NOT NULL,
        resource_id   TEXT NOT NULL,
        data_json     TEXT NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS gdpr_requests (
        id          SERIAL PRIMARY KEY,
        received_at TEXT NOT NULL,
        topic       TEXT NOT NULL,
        shop        TEXT NOT NULL,
        payload     TEXT NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS subscriptions (
        id              SERIAL PRIMARY KEY,
        shop            TEXT NOT NULL UNIQUE,
        subscription_id TEXT,
        plan            TEXT NOT NULL DEFAULT 'free',
        status          TEXT NOT NULL DEFAULT 'pending',
        created_at      TEXT NOT NULL,
        updated_at      TEXT NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS jobs (
        id           TEXT PRIMARY KEY,
        queue        TEXT NOT NULL,
        payload      TEXT NOT NULL,
        shop         TEXT,
        status       TEXT NOT NULL DEFAULT 'pending',
        priority     INTEGER NOT NULL DEFAULT 0,
        retries      INTEGER NOT NULL DEFAULT 0,
        max_retries  INTEGER NOT NULL DEFAULT 3,
        scheduled_at TEXT NOT NULL,
        started_at   TEXT,
        completed_at TEXT,
        result       TEXT,
        created_at   TEXT NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS geo_impact_events (
        id                 SERIAL PRIMARY KEY,
        shop               TEXT NOT NULL,
        created_at         TEXT NOT NULL,
        event_type         TEXT NOT NULL,
        resource_type      TEXT NOT NULL,
        resource_id        TEXT NOT NULL,
        resource_title     TEXT NOT NULL DEFAULT '',
        action_type        TEXT NOT NULL,
        status             TEXT NOT NULL DEFAULT 'planned',
        source             TEXT NOT NULL DEFAULT 'geo',
        job_id             TEXT,
        snapshot_id        INTEGER,
        hypothesis         TEXT,
        score_before       INTEGER,
        score_after        INTEGER,
        measurement_status TEXT NOT NULL DEFAULT 'not_started',
        status_history     TEXT,
        before_snapshot    TEXT NOT NULL,
        after_snapshot     TEXT,
        metrics_before     TEXT NOT NULL,
        metrics_after      TEXT,
        estimated_impact   TEXT NOT NULL,
        observed_impact    TEXT,
        notes              TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS geo_optimization_snapshots (
        id                 SERIAL PRIMARY KEY,
        shop               TEXT NOT NULL,
        created_at         TEXT NOT NULL,
        resource_type      TEXT NOT NULL,
        resource_id        TEXT NOT NULL,
        resource_title     TEXT NOT NULL DEFAULT '',
        action_type        TEXT NOT NULL,
        source             TEXT NOT NULL DEFAULT 'geo',
        hypothesis         TEXT,
        snapshot_json      TEXT NOT NULL,
        metrics_json       TEXT NOT NULL,
        readiness_score    INTEGER NOT NULL DEFAULT 0,
        seo_score          INTEGER NOT NULL DEFAULT 0,
        content_hash       TEXT NOT NULL DEFAULT '',
        notes              TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS crawl_findings (
        id            SERIAL PRIMARY KEY,
        shop          TEXT NOT NULL,
        created_at    TEXT NOT NULL,
        source        TEXT NOT NULL DEFAULT 'crawl_l3',
        url           TEXT NOT NULL,
        issue_type    TEXT NOT NULL,
        severity      TEXT NOT NULL,
        detail        TEXT NOT NULL,
        metadata_json TEXT NOT NULL DEFAULT '{}'
    )""",
]


# ── Migrations ────────────────────────────────────────────────────────────────
# Idempotent ALTER TABLE for tables that pre-date the multi-tenant `shop` column.
# Run after CREATE TABLE IF NOT EXISTS so brand-new tables already have the column.

_TABLES_NEEDING_SHOP_COLUMN = ("seo_changes", "snapshots")
_GEO_IMPACT_EVENT_COLUMNS = {
    "snapshot_id": "INTEGER",
    "score_before": "INTEGER",
    "score_after": "INTEGER",
    "measurement_status": "TEXT NOT NULL DEFAULT 'not_started'",
    "status_history": "TEXT",
}


def _sqlite_has_column(conn: sqlite3.Connection, table: str, column: str) -> bool:
    """Return True if `table.column` exists (SQLite introspection via pragma)."""
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return any(r[1] == column for r in rows)


def _migrate_sqlite_add_shop_columns(conn: sqlite3.Connection) -> None:
    """Add the multi-tenant `shop` column to legacy tables if missing."""
    for table in _TABLES_NEEDING_SHOP_COLUMN:
        if not _sqlite_has_column(conn, table, "shop"):
            conn.execute(f"ALTER TABLE {table} ADD COLUMN shop TEXT")


def _migrate_sqlite_geo_impact_events(conn: sqlite3.Connection) -> None:
    """Add optimization tracking columns to legacy GEO impact ledgers."""
    for column, definition in _GEO_IMPACT_EVENT_COLUMNS.items():
        if not _sqlite_has_column(conn, "geo_impact_events", column):
            conn.execute(f"ALTER TABLE geo_impact_events ADD COLUMN {column} {definition}")


def _pg_has_column(cur, table: str, column: str) -> bool:
    """Return True if `table.column` exists (Postgres information_schema)."""
    cur.execute(
        "SELECT 1 FROM information_schema.columns WHERE table_name = %s AND column_name = %s",
        (table, column),
    )
    return cur.fetchone() is not None


def _migrate_postgres_add_shop_columns(cur) -> None:
    """Add the multi-tenant `shop` column to legacy Postgres tables if missing."""
    for table in _TABLES_NEEDING_SHOP_COLUMN:
        if not _pg_has_column(cur, table, "shop"):
            cur.execute(f"ALTER TABLE {table} ADD COLUMN shop TEXT")


def _migrate_postgres_geo_impact_events(cur) -> None:
    """Add optimization tracking columns to legacy GEO impact ledgers."""
    for column, definition in _GEO_IMPACT_EVENT_COLUMNS.items():
        if not _pg_has_column(cur, "geo_impact_events", column):
            cur.execute(f"ALTER TABLE geo_impact_events ADD COLUMN {column} {definition}")


def _init_postgres(database_url: str) -> None:
    import psycopg2  # noqa: PLC0415

    with psycopg2.connect(database_url) as conn:
        with conn.cursor() as cur:
            for stmt in _PG_DDL:
                cur.execute(stmt)
            cur.execute(_PG_LLM_METRICS)
            cur.execute(_PG_LLM_CACHE)
            for stmt in _PG_EMBEDDINGS:
                cur.execute(stmt)
            cur.execute(_PG_SHOP_CONFIG)
            _migrate_postgres_add_shop_columns(cur)
            _migrate_postgres_geo_impact_events(cur)
        conn.commit()


def init_db(db_path: Path | None = None) -> None:
    """Create every table the app depends on if missing.

    Args:
        db_path: Explicit SQLite path (tests only). When None, uses Postgres if
                 DATABASE_URL is set, otherwise SQLite at the default data/history.db.
    """
    if db_path is None:
        database_url = os.getenv("DATABASE_URL")
        if database_url:
            _init_postgres(database_url)
            return
        db_path = DB_PATH

    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        for stmt in _SQLITE_DDL:
            conn.execute(stmt)
        _migrate_sqlite_add_shop_columns(conn)
        _migrate_sqlite_geo_impact_events(conn)
