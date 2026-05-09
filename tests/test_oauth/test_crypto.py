"""Tests for the Fernet encryption helpers."""

from unittest.mock import patch

import pytest
from cryptography.fernet import Fernet

from app.oauth.crypto import CryptoError, decrypt, encrypt, is_encrypted

VALID_KEY = Fernet.generate_key().decode()
ANOTHER_KEY = Fernet.generate_key().decode()


def test_encrypt_decrypt_round_trip():
    with patch.dict("os.environ", {"LEONIE_MASTER_KEY": VALID_KEY}):
        token = "shpat_super_secret"
        ciphertext = encrypt(token)
        assert ciphertext != token
        assert ciphertext.startswith("enc:")
        assert decrypt(ciphertext) == token


def test_decrypt_passes_through_plaintext():
    """Legacy unencrypted rows must keep working until next save."""
    with patch.dict("os.environ", {"LEONIE_MASTER_KEY": VALID_KEY}):
        assert decrypt("shpat_legacy_plaintext") == "shpat_legacy_plaintext"


def test_decrypt_with_wrong_key_raises():
    with patch.dict("os.environ", {"LEONIE_MASTER_KEY": VALID_KEY}):
        ciphertext = encrypt("secret")
    with patch.dict("os.environ", {"LEONIE_MASTER_KEY": ANOTHER_KEY}), pytest.raises(CryptoError):
        decrypt(ciphertext)


def test_missing_key_raises_meaningful_error():
    with patch.dict("os.environ", {}, clear=True), pytest.raises(CryptoError) as exc:
        encrypt("secret")
    assert "LEONIE_MASTER_KEY" in str(exc.value)


def test_invalid_key_format_raises():
    with (
        patch.dict("os.environ", {"LEONIE_MASTER_KEY": "not-a-valid-fernet-key"}),
        pytest.raises(CryptoError),
    ):
        encrypt("secret")


def test_is_encrypted_detection():
    with patch.dict("os.environ", {"LEONIE_MASTER_KEY": VALID_KEY}):
        assert is_encrypted(encrypt("hello")) is True
    assert is_encrypted("plain_text") is False
    assert is_encrypted("") is False


def test_empty_string_passes_through():
    with patch.dict("os.environ", {"LEONIE_MASTER_KEY": VALID_KEY}):
        assert encrypt("") == ""
        assert decrypt("") == ""
