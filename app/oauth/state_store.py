"""Persistent OAuth CSRF state store.

Replaces an in-memory dict so the state survives across uvicorn workers
and process restarts. Includes TTL purge on read.
"""

from __future__ import annotations

import time
import uuid
from pathlib import Path

from app.db_adapter import get_conn

STATE_TTL_SECONDS = 600  # 10 minutes


def init_state_table(db_path: Path | None = None) -> None:
    """Create the oauth_states table if it does not exist (delegate to init_db)."""
    from app.db import init_db  # noqa: PLC0415

    init_db(db_path)


def issue_state(db_path: Path | None = None) -> str:
    """Generate a fresh CSRF state token and persist it."""
    state = str(uuid.uuid4())
    with get_conn(db_path) as conn:
        conn.execute(
            "INSERT INTO oauth_states (state, created_at) VALUES (?, ?)",
            (state, time.time()),
        )
    return state


def consume_state(state: str, db_path: Path | None = None, ttl: int = STATE_TTL_SECONDS) -> bool:
    """Atomically validate and remove a state.

    Returns True only if the state existed and is younger than TTL.
    Always purges expired states as a side effect.
    """
    now = time.time()
    cutoff = now - ttl
    with get_conn(db_path) as conn:
        conn.execute("DELETE FROM oauth_states WHERE created_at < ?", (cutoff,))
        row = conn.execute(
            "SELECT created_at FROM oauth_states WHERE state = ?", (state,)
        ).fetchone()
        if row is None:
            return False
        conn.execute("DELETE FROM oauth_states WHERE state = ?", (state,))
        return (now - row["created_at"]) <= ttl


def purge_expired(db_path: Path | None = None, ttl: int = STATE_TTL_SECONDS) -> int:
    """Manually purge all expired states. Returns the number of rows deleted."""
    cutoff = time.time() - ttl
    with get_conn(db_path) as conn:
        cur = conn.execute("DELETE FROM oauth_states WHERE created_at < ?", (cutoff,))
        return cur.rowcount
