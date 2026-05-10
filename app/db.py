"""Centralized SQLite initialization for all app tables.

Called once at startup from app/main.py. Avoids hidden coupling where
crawl_shopify creates the seo_changes table that update_meta depends on.
"""

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parents[1] / "data" / "history.db"


def init_db(db_path: Path = DB_PATH) -> None:
    """Create every table the app depends on if missing."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        # OAuth tokens (Phase 5)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS shop_tokens (
                shop         TEXT PRIMARY KEY,
                access_token TEXT NOT NULL,
                scope        TEXT,
                installed_at TEXT NOT NULL,
                updated_at   TEXT NOT NULL
            )
        """)
        # OAuth CSRF states (Phase 5)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS oauth_states (
                state      TEXT PRIMARY KEY,
                created_at REAL NOT NULL
            )
        """)
        # SEO change log — used by scripts/apply/update_meta.py
        conn.execute("""
            CREATE TABLE IF NOT EXISTS seo_changes (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                applied_at    TEXT NOT NULL,
                resource_type TEXT NOT NULL,
                resource_id   TEXT NOT NULL,
                field         TEXT NOT NULL,
                old_value     TEXT,
                new_value     TEXT,
                status        TEXT NOT NULL
            )
        """)
        # Shopify catalog snapshots — created by crawl_shopify.py historically
        conn.execute("""
            CREATE TABLE IF NOT EXISTS snapshots (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                snapshot_date TEXT NOT NULL,
                resource_type TEXT NOT NULL,
                resource_id   TEXT NOT NULL,
                data_json     TEXT NOT NULL
            )
        """)
        # GDPR compliance audit trail (Phase 6, task 51)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS gdpr_requests (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                received_at TEXT NOT NULL,
                topic       TEXT NOT NULL,
                shop        TEXT NOT NULL,
                payload     TEXT NOT NULL
            )
        """)
