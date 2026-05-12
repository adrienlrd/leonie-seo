"""Self-hosted HMAC license validation.

Shopify App Store billing is handled by ``app/billing``. This module only
keeps the historical HMAC key path available for self-hosted or agency
deployments, without making the application layer import CLI scripts.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import os
from datetime import UTC, datetime

_KEY_PREFIX = "LEO-"
_ENV_API_KEY = "LEONIE_API_KEY"
_ENV_SECRET = "LICENSE_SECRET"
_DEFAULT_SECRET = "leonie-seo-v1"


class LicenseError(Exception):
    """Raised when a self-hosted license key is missing, invalid, or expired."""


def _secret(override: str | None = None) -> str:
    return override or os.getenv(_ENV_SECRET, _DEFAULT_SECRET)


def _sign(payload: dict, secret: str) -> str:
    data = json.dumps(payload, sort_keys=True)
    return hmac.new(secret.encode(), data.encode(), hashlib.sha256).hexdigest()


def decode_key(api_key: str) -> dict:
    """Decode a self-hosted license key without checking its signature.

    Args:
        api_key: LEO-prefixed key string.

    Returns:
        Decoded license payload.

    Raises:
        LicenseError: If the key format or encoding is invalid.
    """
    if not api_key.startswith(_KEY_PREFIX):
        raise LicenseError(f"Invalid format — key must start with {_KEY_PREFIX}")
    try:
        b64 = api_key[len(_KEY_PREFIX) :]
        padded = b64 + "=" * (-len(b64) % 4)
        raw = base64.urlsafe_b64decode(padded)
        return json.loads(raw)
    except (binascii.Error, json.JSONDecodeError, UnicodeDecodeError, ValueError) as exc:
        raise LicenseError(f"Unreadable key: {exc}") from exc


def validate_key(api_key: str, secret: str | None = None) -> dict:
    """Validate signature integrity and expiry for a self-hosted license key.

    Args:
        api_key: LEO-prefixed key string.
        secret: Signing secret. Defaults to LICENSE_SECRET.

    Returns:
        License payload with tenant_id, expiry and plan.

    Raises:
        LicenseError: If signature is wrong, key is expired, or format invalid.
    """
    data = decode_key(api_key)
    sig = data.pop("sig", None)
    if sig is None:
        raise LicenseError("Missing signature")
    expected = _sign(data, _secret(secret))
    if not hmac.compare_digest(sig, expected):
        raise LicenseError("Invalid signature")
    today = datetime.now(UTC).strftime("%Y-%m-%d")
    if today > data["expiry"]:
        raise LicenseError(f"License expired on {data['expiry']}")
    data.setdefault("plan", "pro")
    return data


def require_valid_license(
    api_key: str | None = None,
    secret: str | None = None,
) -> dict | None:
    """Return the active self-hosted license payload, or None when unset.

    Args:
        api_key: Override key. Defaults to LEONIE_API_KEY.
        secret: Override signing secret.

    Raises:
        LicenseError: If a configured key is invalid.
    """
    key = api_key or os.getenv(_ENV_API_KEY)
    if not key:
        return None
    return validate_key(key, secret)
