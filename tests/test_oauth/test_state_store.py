"""Tests for the SQLite-backed CSRF state store."""

import time
from pathlib import Path

import pytest

from app.oauth.state_store import (
    consume_state,
    init_state_table,
    issue_state,
    purge_expired,
)


@pytest.fixture()
def db(tmp_path: Path) -> Path:
    path = tmp_path / "test_states.db"
    init_state_table(path)
    return path


def test_issue_returns_unique_uuid_strings(db: Path):
    s1 = issue_state(db)
    s2 = issue_state(db)
    assert s1 != s2
    assert len(s1) == 36  # UUID4 string length


def test_consume_existing_state_returns_true(db: Path):
    s = issue_state(db)
    assert consume_state(s, db) is True


def test_consume_unknown_state_returns_false(db: Path):
    assert consume_state("not-issued", db) is False


def test_state_can_only_be_consumed_once(db: Path):
    s = issue_state(db)
    assert consume_state(s, db) is True
    assert consume_state(s, db) is False  # already consumed


def test_expired_state_returns_false(db: Path):
    s = issue_state(db)
    # Use ttl=0 to force every state to look expired
    assert consume_state(s, db, ttl=0) is False


def test_purge_expired_removes_old_states(db: Path):
    # Issue a state, then move its created_at into the past via direct SQL
    s = issue_state(db)
    import sqlite3

    with sqlite3.connect(db) as conn:
        conn.execute(
            "UPDATE oauth_states SET created_at = ? WHERE state = ?", (time.time() - 10_000, s)
        )
    deleted = purge_expired(db, ttl=600)
    assert deleted == 1
    assert consume_state(s, db) is False
