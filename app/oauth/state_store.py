"""Persistent OAuth CSRF state store backed by SQLite.

Replaces an in-memory dict so the state survives across uvicorn workers
and process restarts. Includes TTL purge on read.
"""

import sqlite3
import time
import uuid
from pathlib import Path

DB_PATH = Path(__file__).parents[2] / "data" / "history.db"
STATE_TTL_SECONDS = 600  # 10 minutes


def _connect(db_path: Path) -> sqlite3.Connection:
    return sqlite3.connect(db_path)


def init_state_table(db_path: Path = DB_PATH) -> None:
    """Create the oauth_states table if it does not exist."""
    with _connect(db_path) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS oauth_states (
                state      TEXT PRIMARY KEY,
                created_at REAL NOT NULL
            )
        """)


def issue_state(db_path: Path = DB_PATH) -> str:
    """Generate a fresh CSRF state token and persist it."""
    state = str(uuid.uuid4())
    with _connect(db_path) as conn:
        conn.execute(
            "INSERT INTO oauth_states (state, created_at) VALUES (?, ?)",
            (state, time.time()),
        )
    return state


def consume_state(state: str, db_path: Path = DB_PATH, ttl: int = STATE_TTL_SECONDS) -> bool:
    """Atomically validate and remove a state.

    Returns True only if the state existed and is younger than TTL.
    Always purges expired states as a side effect.
    """
    now = time.time()
    cutoff = now - ttl
    with _connect(db_path) as conn:
        # Purge expired states first
        conn.execute("DELETE FROM oauth_states WHERE created_at < ?", (cutoff,))
        # Try to consume
        row = conn.execute(
            "SELECT created_at FROM oauth_states WHERE state = ?", (state,)
        ).fetchone()
        if row is None:
            return False
        conn.execute("DELETE FROM oauth_states WHERE state = ?", (state,))
        return (now - row[0]) <= ttl


def purge_expired(db_path: Path = DB_PATH, ttl: int = STATE_TTL_SECONDS) -> int:
    """Manually purge all expired states. Returns the number of rows deleted."""
    cutoff = time.time() - ttl
    with _connect(db_path) as conn:
        cur = conn.execute("DELETE FROM oauth_states WHERE created_at < ?", (cutoff,))
        return cur.rowcount
