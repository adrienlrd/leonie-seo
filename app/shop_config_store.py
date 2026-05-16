"""Simple key-value config store per shop, backed by the shared DB."""

from __future__ import annotations

import os
import sqlite3

from app.db_adapter import DB_PATH


def get_shop_config(shop: str, key: str) -> str | None:
    """Return the stored value for (shop, key), or None if absent."""
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        return _pg_get(database_url, shop, key)
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(
            "SELECT value FROM shop_config WHERE shop = ? AND key = ?", (shop, key)
        ).fetchone()
    return row[0] if row else None


def set_shop_config(shop: str, key: str, value: str) -> None:
    """Upsert (shop, key) → value."""
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        _pg_set(database_url, shop, key, value)
        return
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT INTO shop_config (shop, key, value) VALUES (?, ?, ?)"
            " ON CONFLICT(shop, key) DO UPDATE SET value = excluded.value",
            (shop, key, value),
        )


def delete_shop_config(shop: str, key: str) -> None:
    """Remove (shop, key) if present."""
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        _pg_delete(database_url, shop, key)
        return
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "DELETE FROM shop_config WHERE shop = ? AND key = ?", (shop, key)
        )


def _pg_get(database_url: str, shop: str, key: str) -> str | None:
    import psycopg2  # noqa: PLC0415

    with psycopg2.connect(database_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT value FROM shop_config WHERE shop = %s AND key = %s", (shop, key)
            )
            row = cur.fetchone()
    return row[0] if row else None


def _pg_set(database_url: str, shop: str, key: str, value: str) -> None:
    import psycopg2  # noqa: PLC0415

    with psycopg2.connect(database_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO shop_config (shop, key, value) VALUES (%s, %s, %s)"
                " ON CONFLICT (shop, key) DO UPDATE SET value = EXCLUDED.value",
                (shop, key, value),
            )
        conn.commit()


def _pg_delete(database_url: str, shop: str, key: str) -> None:
    import psycopg2  # noqa: PLC0415

    with psycopg2.connect(database_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM shop_config WHERE shop = %s AND key = %s", (shop, key)
            )
        conn.commit()
