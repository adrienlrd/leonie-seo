"""Tests for scripts.license — HMAC-signed key issuance and validation."""

from __future__ import annotations

import hashlib
import hmac

import pytest
from click.testing import CliRunner

from scripts.license import (
    LicenseError,
    cli,
    decode_key,
    issue_key,
    require_valid_license,
    validate_key,
)

_SECRET = "test-secret-xyz"
_TENANT = "testshop"


def _key(days: int = 365) -> str:
    return issue_key(_TENANT, days, _SECRET)


# ── issue_key ─────────────────────────────────────────────────────────────


def test_issue_key_starts_with_leo():
    assert _key().startswith("LEO-")


def test_issue_key_is_non_empty_string():
    k = _key()
    assert isinstance(k, str) and len(k) > 20


def test_issue_key_different_tenants_produce_different_keys():
    k1 = issue_key("shop-a", 365, _SECRET)
    k2 = issue_key("shop-b", 365, _SECRET)
    assert k1 != k2


def test_issue_key_different_secrets_produce_different_keys():
    k1 = issue_key(_TENANT, 365, "secret-1")
    k2 = issue_key(_TENANT, 365, "secret-2")
    assert k1 != k2


# ── decode_key ────────────────────────────────────────────────────────────


def test_decode_key_roundtrip_has_tenant_id():
    data = decode_key(_key())
    assert data["tenant_id"] == _TENANT


def test_decode_key_roundtrip_has_expiry():
    data = decode_key(_key())
    assert "expiry" in data


def test_decode_key_roundtrip_has_sig():
    data = decode_key(_key())
    assert "sig" in data


def test_decode_key_invalid_prefix_raises():
    with pytest.raises(LicenseError, match="LEO-"):
        decode_key("INVALID-key")


def test_decode_key_corrupted_raises():
    with pytest.raises(LicenseError):
        decode_key("LEO-!!!notvalidbase64!!!!")


# ── validate_key ──────────────────────────────────────────────────────────


def test_validate_key_valid_returns_payload():
    result = validate_key(_key(), _SECRET)
    assert result["tenant_id"] == _TENANT
    assert "expiry" in result


def test_validate_key_result_has_no_sig():
    result = validate_key(_key(), _SECRET)
    assert "sig" not in result


def test_validate_key_wrong_secret_raises():
    with pytest.raises(LicenseError, match="Signature"):
        validate_key(_key(), "wrong-secret")


def test_validate_key_expired_raises():
    with pytest.raises(LicenseError, match="expir"):
        validate_key(_key(days=-1), _SECRET)


def test_validate_key_no_sig_raises():
    import base64
    import json

    payload = {"tenant_id": "x", "expiry": "2099-01-01"}
    raw = json.dumps(payload, sort_keys=True)
    encoded = base64.urlsafe_b64encode(raw.encode()).decode().rstrip("=")
    with pytest.raises(LicenseError, match="sans signature"):
        validate_key(f"LEO-{encoded}", _SECRET)


# ── require_valid_license ─────────────────────────────────────────────────


def test_require_valid_license_no_key_returns_none(monkeypatch):
    monkeypatch.delenv("LEONIE_API_KEY", raising=False)
    assert require_valid_license() is None


def test_require_valid_license_valid_key(monkeypatch):
    k = _key()
    monkeypatch.setenv("LEONIE_API_KEY", k)
    result = require_valid_license(secret=_SECRET)
    assert result["tenant_id"] == _TENANT


def test_require_valid_license_invalid_key_raises(monkeypatch):
    monkeypatch.setenv("LEONIE_API_KEY", "LEO-invalid")
    with pytest.raises(LicenseError):
        require_valid_license(secret=_SECRET)


def test_require_valid_license_expired_key_raises(monkeypatch):
    monkeypatch.setenv("LEONIE_API_KEY", _key(days=-1))
    with pytest.raises(LicenseError, match="expir"):
        require_valid_license(secret=_SECRET)


def test_require_valid_license_explicit_key_overrides_env(monkeypatch):
    monkeypatch.delenv("LEONIE_API_KEY", raising=False)
    k = _key()
    result = require_valid_license(api_key=k, secret=_SECRET)
    assert result is not None


# ── CLI ───────────────────────────────────────────────────────────────────


def test_cmd_issue_output_contains_key():
    runner = CliRunner()
    result = runner.invoke(cli, ["issue", "--tenant", "testshop", "--secret", _SECRET])
    assert result.exit_code == 0, result.output
    assert "LEO-" in result.output


def test_cmd_issue_mentions_env_instruction():
    runner = CliRunner()
    result = runner.invoke(cli, ["issue", "--tenant", "testshop", "--secret", _SECRET])
    assert "LEONIE_API_KEY" in result.output


def test_cmd_check_no_key_warns():
    runner = CliRunner()
    result = runner.invoke(cli, ["check"], env={"LEONIE_API_KEY": "", "LICENSE_SECRET": ""})
    assert result.exit_code == 0
    assert "sans licence" in result.output or "⚠" in result.output


def test_cmd_check_valid_key_succeeds():
    runner = CliRunner()
    k = _key()
    result = runner.invoke(cli, ["check", "--key", k, "--secret", _SECRET])
    assert result.exit_code == 0, result.output
    assert "valide" in result.output


def test_cmd_check_invalid_key_reports_error():
    runner = CliRunner()
    result = runner.invoke(cli, ["check", "--key", "LEO-invalid", "--secret", _SECRET])
    assert result.exit_code == 0
    assert "✗" in result.output or "invalide" in result.output.lower()


# ── plan field ────────────────────────────────────────────────────────────


def test_issue_key_default_plan_is_pro():
    data = decode_key(issue_key(_TENANT, 365, _SECRET))
    assert data["plan"] == "pro"


def test_issue_key_agency_plan_stored():
    data = decode_key(issue_key(_TENANT, 365, _SECRET, plan="agency"))
    assert data["plan"] == "agency"


def test_issue_key_free_plan_stored():
    data = decode_key(issue_key(_TENANT, 365, _SECRET, plan="free"))
    assert data["plan"] == "free"


def test_issue_key_invalid_plan_raises():
    with pytest.raises(LicenseError, match="Plan inconnu"):
        issue_key(_TENANT, 365, _SECRET, plan="enterprise")


def test_validate_key_returns_plan():
    result = validate_key(issue_key(_TENANT, 365, _SECRET, plan="agency"), _SECRET)
    assert result["plan"] == "agency"


def test_validate_key_legacy_key_defaults_to_pro():
    """Keys issued before the plan field was added must validate as plan=pro."""
    import base64
    import json as _json

    secret = _SECRET
    payload = {"tenant_id": _TENANT, "expiry": "2099-01-01"}
    data = payload.copy()
    sig = hmac.new(
        secret.encode(), _json.dumps(data, sort_keys=True).encode(), hashlib.sha256
    ).hexdigest()
    raw = _json.dumps({**data, "sig": sig}, sort_keys=True)
    key = "LEO-" + base64.urlsafe_b64encode(raw.encode()).decode().rstrip("=")
    result = validate_key(key, secret)
    assert result["plan"] == "pro"


def test_cmd_issue_with_plan_shows_plan():
    runner = CliRunner()
    result = runner.invoke(
        cli, ["issue", "--tenant", "testshop", "--plan", "agency", "--secret", _SECRET]
    )
    assert result.exit_code == 0, result.output
    assert "agency" in result.output


def test_cmd_check_shows_plan():
    runner = CliRunner()
    k = issue_key(_TENANT, 365, _SECRET, plan="pro")
    result = runner.invoke(cli, ["check", "--key", k, "--secret", _SECRET])
    assert result.exit_code == 0, result.output
    assert "pro" in result.output
