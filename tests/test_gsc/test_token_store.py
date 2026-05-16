"""Tests for encrypted Google OAuth token storage."""

from __future__ import annotations

from cryptography.fernet import Fernet

from app.db import init_db
from app.gsc.token_store import get_google_token, save_google_token


def test_google_token_round_trips_encrypted_json(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("LEONIE_MASTER_KEY", Fernet.generate_key().decode())
    db = tmp_path / "history.db"
    init_db(db)

    save_google_token("store.myshopify.com", '{"token":"ya29"}', "scope", email="a@example.com", db_path=db)

    record = get_google_token("store.myshopify.com", db_path=db)
    assert record is not None
    assert record["token_json"] == '{"token":"ya29"}'
    assert record["email"] == "a@example.com"
