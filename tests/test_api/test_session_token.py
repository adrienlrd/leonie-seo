"""Tests for Shopify session token verification."""

import time
from unittest.mock import patch

import jwt
import pytest

from app.api.session_token import SessionTokenError, shop_from_payload, verify_session_token

CLIENT_ID = "test_client_id"
CLIENT_SECRET = "test_client_secret"
SHOP = "mystore.myshopify.com"

ENV = {"SHOPIFY_CLIENT_ID": CLIENT_ID, "SHOPIFY_CLIENT_SECRET": CLIENT_SECRET}


def _make_token(
    secret: str = CLIENT_SECRET,
    aud: str = CLIENT_ID,
    iss: str = f"https://{SHOP}/admin",
    dest: str = f"https://{SHOP}/admin",
    exp_offset: int = 60,
    nbf_offset: int = -60,
    extra: dict | None = None,
) -> str:
    now = int(time.time())
    payload = {
        "iss": iss,
        "dest": dest,
        "aud": aud,
        "sub": "12345",
        "exp": now + exp_offset,
        "nbf": now + nbf_offset,
        "iat": now,
        "jti": "abc",
        "sid": "session_id",
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, secret, algorithm="HS256")


@pytest.fixture(autouse=True)
def env():
    with patch.dict("os.environ", ENV):
        yield


def test_verify_valid_token_returns_payload():
    token = _make_token()
    payload = verify_session_token(token)
    assert payload["aud"] == CLIENT_ID
    assert shop_from_payload(payload) == SHOP


def test_verify_expired_token_raises():
    token = _make_token(exp_offset=-100)
    with pytest.raises(SessionTokenError, match="expired"):
        verify_session_token(token)


def test_verify_wrong_audience_raises():
    token = _make_token(aud="other_app_id")
    with pytest.raises(SessionTokenError, match="audience"):
        verify_session_token(token)


def test_verify_wrong_signature_raises():
    token = _make_token(secret="wrong_secret")
    with pytest.raises(SessionTokenError):
        verify_session_token(token)


def test_verify_invalid_iss_format_raises():
    token = _make_token(iss="https://evil.example.com/admin")
    with pytest.raises(SessionTokenError, match="iss/dest"):
        verify_session_token(token)


def test_verify_iss_dest_mismatch_raises():
    token = _make_token(
        iss=f"https://{SHOP}/admin",
        dest="https://other.myshopify.com/admin",
    )
    with pytest.raises(SessionTokenError, match="mismatch"):
        verify_session_token(token)


def test_verify_missing_iss_raises():
    token = _make_token(iss="")
    with pytest.raises(SessionTokenError):
        verify_session_token(token)


def test_verify_missing_env_raises():
    with patch.dict("os.environ", {}, clear=True), pytest.raises(SessionTokenError):
        verify_session_token(_make_token())


def test_verify_garbage_token_raises():
    with pytest.raises(SessionTokenError):
        verify_session_token("not.a.jwt")
