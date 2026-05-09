"""Symmetric encryption helpers for at-rest secrets (Shopify access tokens).

Uses Fernet (AES-128-CBC + HMAC-SHA256) from `cryptography`. The master key
must be supplied via the LEONIE_MASTER_KEY environment variable.

Generate one with:
    python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
"""

import os

from cryptography.fernet import Fernet, InvalidToken

_ENC_PREFIX = "enc:"  # marks ciphertext so we can migrate plaintext rows lazily


class CryptoError(RuntimeError):
    """Raised on misconfiguration (missing key) or decryption failure."""


def _get_fernet() -> Fernet:
    key = os.getenv("LEONIE_MASTER_KEY")
    if not key:
        raise CryptoError(
            "LEONIE_MASTER_KEY is not set — generate one with "
            "`python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'` "
            "and add it to your .env"
        )
    try:
        return Fernet(key.encode() if isinstance(key, str) else key)
    except (ValueError, TypeError) as exc:
        raise CryptoError(f"LEONIE_MASTER_KEY is not a valid Fernet key: {exc}") from exc


def encrypt(plaintext: str) -> str:
    """Encrypt plaintext, returning a `enc:<base64>` string."""
    if not plaintext:
        return plaintext
    f = _get_fernet()
    return _ENC_PREFIX + f.encrypt(plaintext.encode()).decode()


def decrypt(value: str) -> str:
    """Decrypt a value previously produced by `encrypt()`.

    For backward compatibility, plaintext values (no prefix) are returned as-is
    so existing rows from before encryption was rolled out keep working until
    they are re-saved.
    """
    if not value or not value.startswith(_ENC_PREFIX):
        return value
    f = _get_fernet()
    try:
        return f.decrypt(value[len(_ENC_PREFIX) :].encode()).decode()
    except InvalidToken as exc:
        raise CryptoError("Failed to decrypt — wrong key or tampered value") from exc


def is_encrypted(value: str) -> bool:
    return bool(value) and value.startswith(_ENC_PREFIX)
