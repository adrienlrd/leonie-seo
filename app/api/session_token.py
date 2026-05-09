"""Verify Shopify App Bridge session tokens (JWT, HS256 signed by client_secret).

Reference:
https://shopify.dev/docs/apps/build/authentication-authorization/session-tokens

Validation rules:
- Algorithm: HS256
- Signing key: SHOPIFY_CLIENT_SECRET
- aud: must equal SHOPIFY_CLIENT_ID
- iss / dest: must be `https://<shop>.myshopify.com/admin`
- exp: must be in the future
- nbf: must not be in the future (with small leeway)
"""

import os
import re

import jwt

_SHOP_FROM_ISS = re.compile(r"^https://([a-z0-9][a-z0-9\-]*\.myshopify\.com)/admin$")


class SessionTokenError(Exception):
    """Raised when a Shopify session token is invalid, expired, or malformed."""


def verify_session_token(token: str) -> dict:
    """Decode and validate a Shopify session token. Returns the payload.

    Raises:
        SessionTokenError: if the token cannot be trusted.
    """
    client_id = os.getenv("SHOPIFY_CLIENT_ID")
    client_secret = os.getenv("SHOPIFY_CLIENT_SECRET")
    if not client_id or not client_secret:
        raise SessionTokenError("Server missing SHOPIFY_CLIENT_ID / SHOPIFY_CLIENT_SECRET")

    try:
        payload: dict = jwt.decode(
            token,
            client_secret,
            algorithms=["HS256"],
            audience=client_id,
            leeway=5,  # 5 s tolerance for clock skew
        )
    except jwt.ExpiredSignatureError as exc:
        raise SessionTokenError("Session token expired") from exc
    except jwt.InvalidAudienceError as exc:
        raise SessionTokenError("Session token audience does not match this app") from exc
    except jwt.InvalidTokenError as exc:
        raise SessionTokenError(f"Session token invalid: {exc}") from exc

    iss = payload.get("iss") or ""
    dest = payload.get("dest") or ""

    if not iss or not dest:
        raise SessionTokenError("Session token missing iss/dest claim")

    # Both iss and dest must point to the same shop and be a valid myshopify domain.
    iss_match = _SHOP_FROM_ISS.match(iss)
    dest_match = _SHOP_FROM_ISS.match(dest)
    if not iss_match or not dest_match:
        raise SessionTokenError("Session token iss/dest is not a valid Shopify admin URL")
    if iss_match.group(1) != dest_match.group(1):
        raise SessionTokenError("Session token iss/dest mismatch")

    payload["_shop"] = iss_match.group(1)
    return payload


def shop_from_payload(payload: dict) -> str:
    """Convenience accessor — returns `xxx.myshopify.com` from a verified payload."""
    return payload["_shop"]
