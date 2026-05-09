"""Persistent storage of Shopify OAuth access tokens.

Tokens are stored encrypted at rest via Fernet (see app.oauth.crypto).
A plaintext token from a pre-encryption row will be decrypted as-is and
re-saved encrypted on the next save_token() call.
"""

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from app.oauth.crypto import decrypt, encrypt

DB_PATH = Path(__file__).parents[2] / "data" / "history.db"


def _connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_token_table(db_path: Path = DB_PATH) -> None:
    """Create the shop_tokens table if it does not exist."""
    with _connect(db_path) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS shop_tokens (
                shop         TEXT PRIMARY KEY,
                access_token TEXT NOT NULL,
                scope        TEXT,
                installed_at TEXT NOT NULL,
                updated_at   TEXT NOT NULL
            )
        """)


def save_token(shop: str, access_token: str, scope: str, db_path: Path = DB_PATH) -> None:
    """Insert or update the access token for a shop. Token is encrypted at rest."""
    now = datetime.now(UTC).isoformat()
    encrypted = encrypt(access_token)
    with _connect(db_path) as conn:
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


def get_token(shop: str, db_path: Path = DB_PATH) -> dict | None:
    """Return the token record for a shop with the access_token decrypted."""
    with _connect(db_path) as conn:
        row = conn.execute("SELECT * FROM shop_tokens WHERE shop = ?", (shop,)).fetchone()
    if row is None:
        return None
    record = dict(row)
    record["access_token"] = decrypt(record["access_token"])
    return record


def delete_token(shop: str, db_path: Path = DB_PATH) -> None:
    """Remove the token for a shop (uninstall webhook handler)."""
    with _connect(db_path) as conn:
        conn.execute("DELETE FROM shop_tokens WHERE shop = ?", (shop,))


def list_tokens(db_path: Path = DB_PATH) -> list[dict]:
    """Return all installed shops (without access_token) ordered by install date."""
    if not db_path.exists():
        return []
    with _connect(db_path) as conn:
        rows = conn.execute(
            "SELECT shop, scope, installed_at, updated_at FROM shop_tokens ORDER BY installed_at DESC"
        ).fetchall()
    return [dict(row) for row in rows]
