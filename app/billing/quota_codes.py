"""Single-use quota reset codes.

A code is `GEO-<BASE>-<SIG>` where BASE is any token the operator picks and
SIG is the first 8 hex chars (uppercased) of HMAC-SHA256(BASE, secret). Only
someone knowing the secret (`QUOTA_CODE_SECRET` env var) can mint valid codes
— generate them with `scripts/generate_quota_code.py`. Each code is redeemable
once, globally (recorded in `redeemed_quota_codes`), by a shop on any plan.

Redeeming wipes the shop's rolling-window analysis usage (`analysis` events +
every `product_analysis:{id}` event), restoring the full plan quota.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import re
from datetime import UTC, datetime
from pathlib import Path

from app.db import DB_PATH
from app.db_adapter import get_conn

_CODE_RE = re.compile(r"^GEO-([A-Z0-9]{4,32})-([0-9A-F]{8})$")
_SIG_LEN = 8


class InvalidQuotaCode(Exception):
    """Raised for a malformed or badly-signed code."""


class QuotaCodeAlreadyUsed(Exception):
    """Raised when a valid code was already redeemed."""


def _signature(base: str, secret: str) -> str:
    return (
        hmac.new(secret.encode("utf-8"), base.encode("utf-8"), hashlib.sha256)
        .hexdigest()[:_SIG_LEN]
        .upper()
    )


def build_code(base: str, secret: str) -> str:
    """Mint a code for BASE — used by the operator-side generator script."""
    base = base.strip().upper()
    if not re.fullmatch(r"[A-Z0-9]{4,32}", base):
        raise ValueError("BASE must be 4-32 uppercase letters/digits")
    return f"GEO-{base}-{_signature(base, secret)}"


def redeem_quota_code(shop: str, code: str, *, db_path: Path | None = None) -> dict:
    """Validate + burn a code, then reset the shop's analysis quotas.

    Raises InvalidQuotaCode / QuotaCodeAlreadyUsed; returns
    ``{"reset_events": N}`` on success.
    """
    secret = os.getenv("QUOTA_CODE_SECRET", "")
    if not secret:
        raise InvalidQuotaCode("quota codes are not enabled on this server")

    match = _CODE_RE.match(code.strip().upper())
    if not match:
        raise InvalidQuotaCode("malformed code")
    base, sig = match.groups()
    if not hmac.compare_digest(sig, _signature(base, secret)):
        raise InvalidQuotaCode("invalid signature")

    path = db_path if db_path is not None else DB_PATH
    normalized = f"GEO-{base}-{sig}"
    with get_conn(path) as conn:
        already = conn.execute(
            "SELECT 1 FROM redeemed_quota_codes WHERE code = ?", (normalized,)
        ).fetchone()
        if already:
            raise QuotaCodeAlreadyUsed(normalized)
        conn.execute(
            "INSERT INTO redeemed_quota_codes (code, shop, redeemed_at) VALUES (?, ?, ?)",
            (normalized, shop, datetime.now(UTC).isoformat()),
        )
    from app.billing.quotas import reset_analysis_usage  # noqa: PLC0415

    return {"reset_events": reset_analysis_usage(shop, db_path)}
