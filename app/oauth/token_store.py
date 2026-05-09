import sqlite3
from datetime import UTC, datetime
from pathlib import Path

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
    """Insert or update the access token for a shop.

    installed_at is preserved on update — only access_token, scope and
    updated_at are refreshed on re-install.
    """
    now = datetime.now(UTC).isoformat()
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
            (shop, access_token, scope, now, now),
        )


def get_token(shop: str, db_path: Path = DB_PATH) -> dict | None:
    """Return the token record for a shop, or None if not installed."""
    with _connect(db_path) as conn:
        row = conn.execute("SELECT * FROM shop_tokens WHERE shop = ?", (shop,)).fetchone()
    return dict(row) if row else None


def delete_token(shop: str, db_path: Path = DB_PATH) -> None:
    """Remove the token for a shop (uninstall webhook handler)."""
    with _connect(db_path) as conn:
        conn.execute("DELETE FROM shop_tokens WHERE shop = ?", (shop,))
