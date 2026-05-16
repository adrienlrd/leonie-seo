"""Tests for signed Google OAuth state tokens."""

from __future__ import annotations

import pytest

from app.gsc.oauth_state import GoogleOAuthStateError, create_state, verify_state


def test_verify_state_returns_shop_when_signature_is_valid(monkeypatch) -> None:
    monkeypatch.setenv("INTERNAL_API_SECRET", "secret")

    state = create_state("store.myshopify.com")

    assert verify_state(state) == "store.myshopify.com"


def test_verify_state_rejects_tampered_signature(monkeypatch) -> None:
    monkeypatch.setenv("INTERNAL_API_SECRET", "secret")
    state = create_state("store.myshopify.com")

    with pytest.raises(GoogleOAuthStateError):
        verify_state(f"{state}tampered")
