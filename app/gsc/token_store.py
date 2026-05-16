"""Encrypted storage for per-shop Google OAuth credentials."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from app.db_adapter import get_conn
from app.oauth.crypto import decrypt, encrypt


def save_google_token(
    shop: str,
    token_json: str,
    scopes: str,
    *,
    email: str | None = None,
    db_path: Path | None = None,
) -> None:
    """Insert or update encrypted Google OAuth credentials for a shop."""
    now = datetime.now(UTC).isoformat()
    encrypted = encrypt(token_json)
    with get_conn(db_path) as conn:
        conn.execute(
            """
            INSERT INTO google_tokens (shop, token_json, scopes, email, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(shop) DO UPDATE SET
                token_json = excluded.token_json,
                scopes     = excluded.scopes,
                email      = excluded.email,
                updated_at = excluded.updated_at
            """,
            (shop, encrypted, scopes, email, now, now),
        )


def get_google_token(shop: str, db_path: Path | None = None) -> dict | None:
    """Return decrypted Google OAuth credentials for a shop, if connected."""
    with get_conn(db_path) as conn:
        row = conn.execute("SELECT * FROM google_tokens WHERE shop = ?", (shop,)).fetchone()
    if row is None:
        return None
    row["token_json"] = decrypt(row["token_json"])
    return row


def delete_google_token(shop: str, db_path: Path | None = None) -> None:
    """Remove Google OAuth credentials for a shop."""
    with get_conn(db_path) as conn:
        conn.execute("DELETE FROM google_tokens WHERE shop = ?", (shop,))
