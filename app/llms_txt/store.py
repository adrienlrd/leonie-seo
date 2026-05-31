"""Persistence for AI discovery template publication state (one row per shop)."""

from __future__ import annotations

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
