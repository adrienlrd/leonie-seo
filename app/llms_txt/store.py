"""Persistence for AI discovery template publication state (one row per shop)."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.db_adapter import get_conn


def get_publication(shop: str, db_path: Path | None = None) -> dict[str, Any] | None:
    """Return the publication row for a shop, or None if never published."""
    with get_conn(db_path) as conn:
        return conn.execute(
            "SELECT * FROM llms_txt_publications WHERE shop = ?", (shop,)
        ).fetchone()


def save_publication(
    shop: str,
    *,
    theme_id: str,
    agents_hash: str,
    llms_hash: str,
    full_hash: str,
    published_at: str | None = None,
    db_path: Path | None = None,
) -> None:
    """Insert or update the publication row, marking the shop as published."""
    now = published_at or datetime.now(UTC).isoformat()
    with get_conn(db_path) as conn:
        conn.execute(
            """
            INSERT INTO llms_txt_publications (
                shop, theme_id, agents_hash, llms_hash, full_hash,
                last_published_at, is_published
            ) VALUES (?, ?, ?, ?, ?, ?, 1)
            ON CONFLICT(shop) DO UPDATE SET
                theme_id          = excluded.theme_id,
                agents_hash       = excluded.agents_hash,
                llms_hash         = excluded.llms_hash,
                full_hash         = excluded.full_hash,
                last_published_at = excluded.last_published_at,
                is_published      = 1
            """,
            (shop, theme_id, agents_hash, llms_hash, full_hash, now),
        )


def mark_unpublished(shop: str, db_path: Path | None = None) -> None:
    """Clear theme references and flag the shop as unpublished."""
    with get_conn(db_path) as conn:
        conn.execute(
            """
            UPDATE llms_txt_publications
            SET is_published = 0,
                theme_id = NULL,
                agents_hash = NULL,
                llms_hash = NULL,
                full_hash = NULL
            WHERE shop = ?
            """,
            (shop,),
        )


def log_theme_write(
    shop: str,
    *,
    action: str,
    filenames: list[str],
    theme_id: str | None = None,
    hash_before: dict[str, Any] | None = None,
    hash_after: dict[str, Any] | None = None,
    user_action: bool = False,
    db_path: Path | None = None,
) -> None:
    """Append an immutable audit row for a theme write.

    Args:
        action: ``publish`` | ``unpublish`` | ``regeneration_pending``.
        filenames: The theme files touched (always within the allowlist).
        hash_before / hash_after: Content hashes before/after the write.
        user_action: True when the merchant explicitly triggered the write.
    """
    with get_conn(db_path) as conn:
        conn.execute(
            """
            INSERT INTO theme_write_log (
                id, shop, theme_id, action, filenames,
                hash_before, hash_after, user_action, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                uuid.uuid4().hex,
                shop,
                theme_id,
                action,
                json.dumps(filenames),
                json.dumps(hash_before) if hash_before is not None else None,
                json.dumps(hash_after) if hash_after is not None else None,
                1 if user_action else 0,
                datetime.now(UTC).isoformat(),
            ),
        )


def get_theme_write_log(
    shop: str, db_path: Path | None = None, limit: int = 50
) -> list[dict[str, Any]]:
    """Return the most recent theme-write audit rows for a shop (newest first)."""
    with get_conn(db_path) as conn:
        return conn.execute(
            "SELECT * FROM theme_write_log WHERE shop = ? "
            "ORDER BY created_at DESC LIMIT ?",
            (shop, limit),
        ).fetchall()


def get_crawler_prefs(shop: str, db_path: Path | None = None) -> dict[str, Any] | None:
    """Return the merchant AI-crawler prefs for a shop, or None if never set."""
    with get_conn(db_path) as conn:
        row = conn.execute(
            "SELECT prefs_json FROM llms_txt_prefs WHERE shop = ?", (shop,)
        ).fetchone()
    if not row:
        return None
    try:
        return json.loads(row["prefs_json"])
    except (ValueError, TypeError):
        return None


def save_crawler_prefs(
    shop: str, prefs: dict[str, Any], db_path: Path | None = None
) -> None:
    """Insert or update the merchant AI-crawler prefs for a shop."""
    with get_conn(db_path) as conn:
        conn.execute(
            """
            INSERT INTO llms_txt_prefs (shop, prefs_json, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(shop) DO UPDATE SET
                prefs_json = excluded.prefs_json,
                updated_at = excluded.updated_at
            """,
            (shop, json.dumps(prefs), datetime.now(UTC).isoformat()),
        )


def record_webhook_tick(
    shop: str, tick_at: str | None = None, db_path: Path | None = None
) -> str | None:
    """Persist the latest catalogue webhook tick. Returns the previous tick time."""
    now = tick_at or datetime.now(UTC).isoformat()
    with get_conn(db_path) as conn:
        row = conn.execute(
            "SELECT last_webhook_tick_at FROM llms_txt_publications WHERE shop = ?", (shop,)
        ).fetchone()
        previous = row["last_webhook_tick_at"] if row else None
        conn.execute(
            """
            INSERT INTO llms_txt_publications (shop, last_webhook_tick_at, is_published)
            VALUES (?, ?, 0)
            ON CONFLICT(shop) DO UPDATE SET last_webhook_tick_at = excluded.last_webhook_tick_at
            """,
            (shop, now),
        )
    return previous
