"""Persistent storage of Shopify OAuth access tokens.

Tokens are stored encrypted at rest via Fernet (see app.oauth.crypto).
"""

from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path

from app.db import DB_PATH
from app.db_adapter import get_conn
from app.oauth.crypto import decrypt, encrypt


def init_token_table(db_path: Path | None = None) -> None:
    """Create the shop_tokens table if it does not exist (delegate to init_db)."""
    from app.db import init_db  # noqa: PLC0415

    init_db(db_path)


def save_token(shop: str, access_token: str, scope: str, db_path: Path | None = None) -> None:
    """Insert or update the access token for a shop. Token is encrypted at rest."""
    now = datetime.now(UTC).isoformat()
    encrypted = encrypt(access_token)
    with get_conn(db_path) as conn:
        conn.execute(
            """
            INSERT INTO shop_tokens (shop, access_token, scope, installed_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(shop) DO UPDATE SET
                access_token = excluded.access_token,
                scope        = excluded.scope,
                updated_at   = excluded.updated_at
            """,
            (shop, encrypted, scope, now, now),
        )


def get_token(shop: str, db_path: Path | None = None) -> dict | None:
    """Return the token record for a shop with the access_token decrypted."""
    with get_conn(db_path) as conn:
        row = conn.execute("SELECT * FROM shop_tokens WHERE shop = ?", (shop,)).fetchone()
    if row is None:
        return None
    row["access_token"] = decrypt(row["access_token"])
    return row


def delete_token(shop: str, db_path: Path | None = None) -> None:
    """Remove the token for a shop (uninstall webhook handler)."""
    with get_conn(db_path) as conn:
        conn.execute("DELETE FROM shop_tokens WHERE shop = ?", (shop,))


def list_tokens(db_path: Path | None = None) -> list[dict]:
    """Return all installed shops (without access_token) ordered by install date."""
    # For SQLite mode, avoid error if the file doesn't exist yet
    if not os.getenv("DATABASE_URL"):
        _path = db_path if db_path is not None else DB_PATH
        if not _path.exists():
            return []
    with get_conn(db_path) as conn:
        return conn.execute(
            "SELECT shop, scope, installed_at, updated_at FROM shop_tokens ORDER BY installed_at DESC"
        ).fetchall()
