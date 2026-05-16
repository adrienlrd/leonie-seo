"""Signed OAuth state tokens for Google integrations."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from secrets import token_urlsafe


class GoogleOAuthStateError(ValueError):
    """Raised when a Google OAuth state token is invalid or expired."""


def _secret() -> bytes:
    secret = os.getenv("GOOGLE_OAUTH_STATE_SECRET") or os.getenv("INTERNAL_API_SECRET")
    if not secret:
        raise GoogleOAuthStateError("GOOGLE_OAUTH_STATE_SECRET or INTERNAL_API_SECRET is required")
    return secret.encode()


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def _unb64(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def create_state(shop: str) -> str:
    """Return a signed state token carrying the Shopify shop domain."""
    payload = {
        "shop": shop,
        "nonce": token_urlsafe(16),
        "iat": int(time.time()),
    }
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    body = _b64(raw)
    sig = hmac.new(_secret(), body.encode(), hashlib.sha256).hexdigest()
    return f"{body}.{sig}"


def verify_state(state: str, *, max_age_seconds: int = 600) -> str:
    """Validate a signed state token and return its shop."""
    try:
        body, received_sig = state.split(".", 1)
    except ValueError as exc:
        raise GoogleOAuthStateError("Invalid OAuth state format") from exc

    expected_sig = hmac.new(_secret(), body.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(received_sig, expected_sig):
        raise GoogleOAuthStateError("Invalid OAuth state signature")

    try:
        payload = json.loads(_unb64(body))
    except (json.JSONDecodeError, ValueError) as exc:
        raise GoogleOAuthStateError("Invalid OAuth state payload") from exc

    shop = str(payload.get("shop") or "")
    issued_at = int(payload.get("iat") or 0)
    if not shop:
        raise GoogleOAuthStateError("OAuth state is missing shop")
    if int(time.time()) - issued_at > max_age_seconds:
        raise GoogleOAuthStateError("OAuth state expired")
    return shop
