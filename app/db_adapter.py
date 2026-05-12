"""Unified database connection factory — SQLite for tests/local, Postgres for production.

Selection logic:
- db_path provided AND differs from the default DB_PATH → always SQLite (test isolation)
- db_path is None OR equal to the default DB_PATH, AND DATABASE_URL is set → Postgres
- otherwise → SQLite at the default DB_PATH

This preserves the existing test isolation pattern (monkeypatch DB_PATH) while
enabling Neon Postgres in production deployments.
"""

from __future__ import annotations

import os
import re
import sqlite3
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

DB_PATH = Path(__file__).parents[1] / "data" / "history.db"


def _to_pg(sql: str) -> str:
    """Translate SQLite ? positional placeholders to Postgres %s."""
    return re.sub(r"\?", "%s", sql)


class _Cursor:
    """Unified cursor — always returns dict rows, exposes rowcount."""

    def __init__(self, raw, is_pg: bool) -> None:
        self._raw = raw
        self._is_pg = is_pg

    @property
    def rowcount(self) -> int:
        return self._raw.rowcount

    def fetchone(self) -> dict | None:
        row = self._raw.fetchone()
        return dict(row) if row is not None else None

    def fetchall(self) -> list[dict]:
        return [dict(r) for r in self._raw.fetchall()]


class _Conn:
    """Unified connection wrapper — normalises execute() across backends."""

    def __init__(self, raw, is_pg: bool) -> None:
        self._raw = raw
        self._is_pg = is_pg

    def execute(self, sql: str, params: tuple = ()) -> _Cursor:
        if self._is_pg:
            cur = self._raw.cursor()
            cur.execute(_to_pg(sql), params)
        else:
            cur = self._raw.execute(sql, params)
        return _Cursor(cur, self._is_pg)


@contextmanager
def get_conn(db_path: Path | None = None) -> Generator[_Conn, None, None]:
    """Yield a unified DB connection. Commits on success, rolls back on exception.

    Args:
        db_path: When provided and different from the default DB_PATH, forces
                 SQLite at that path (test isolation). Pass None (or omit) for
                 production behaviour — Postgres if DATABASE_URL is set, else
                 SQLite at the default path.
    """
    is_default = db_path is None or db_path == DB_PATH
    database_url = os.getenv("DATABASE_URL") if is_default else None

    if database_url:
        import psycopg2  # noqa: PLC0415
        import psycopg2.extras  # noqa: PLC0415

        raw = psycopg2.connect(database_url, cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            yield _Conn(raw, is_pg=True)
            raw.commit()
        except psycopg2.Error:
            raw.rollback()
            raise
        finally:
            raw.close()
    else:
        path = db_path if db_path is not None else DB_PATH
        raw = sqlite3.connect(path)
        raw.row_factory = sqlite3.Row
        try:
            yield _Conn(raw, is_pg=False)
            raw.commit()
        except sqlite3.Error:
            raw.rollback()
            raise
        finally:
            raw.close()
