"""Single-use signed codes: quota resets and plan grants.

Formats (SIG = first 8 hex chars, uppercased, of HMAC-SHA256(payload, secret),
secret = `QUOTA_CODE_SECRET` env var; minted offline with
`scripts/generate_quota_code.py`; each code burns once globally in
`redeemed_quota_codes`):

- `GEO-<BASE>-<SIG>`     — quota reset (payload = BASE): wipes the shop's
  rolling-window analysis usage, any plan.
- `GEOPRO-<BASE>-<SIG>`  — grants the Pro plan (payload = "pro:BASE") via
  plan_override, plus a quota reset when it's an upgrade.
- `GEOBIG-<BASE>-<SIG>`  — same for the Grande boutique (agency) plan
  (payload = "agency:BASE").
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

_CODE_RE = re.compile(r"^(GEO|GEOPRO|GEOBIG)-([A-Z0-9]{4,32})-([0-9A-F]{8})$")
_PREFIX_PLANS = {"GEOPRO": "pro", "GEOBIG": "agency"}
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


def build_code(base: str, secret: str, plan: str | None = None) -> str:
    """Mint a code — quota reset by default, plan grant when `plan` is given."""
    base = base.strip().upper()
    if not re.fullmatch(r"[A-Z0-9]{4,32}", base):
        raise ValueError("BASE must be 4-32 uppercase letters/digits")
    if plan is None:
        return f"GEO-{base}-{_signature(base, secret)}"
    if plan not in ("pro", "agency"):
        raise ValueError("plan must be 'pro' or 'agency'")
    prefix = "GEOPRO" if plan == "pro" else "GEOBIG"
    return f"{prefix}-{base}-{_signature(f'{plan}:{base}', secret)}"


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
    prefix, base, sig = match.groups()
    plan = _PREFIX_PLANS.get(prefix)
    payload = f"{plan}:{base}" if plan else base
    if not hmac.compare_digest(sig, _signature(payload, secret)):
        raise InvalidQuotaCode("invalid signature")

    path = db_path if db_path is not None else DB_PATH
    normalized = f"{prefix}-{base}-{sig}"
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
    from app.billing.quotas import is_plan_upgrade, reset_analysis_usage  # noqa: PLC0415

    if plan:
        from app.apply.theme_entitlement import set_theme_entitlement  # noqa: PLC0415
        from app.billing.subscription_store import get_plan_for_shop  # noqa: PLC0415
        from app.shop_config_store import set_shop_config  # noqa: PLC0415

        old_plan = get_plan_for_shop(shop, db_path)
        set_shop_config(shop, "plan_override", plan)
        set_theme_entitlement(shop, True)
        cleared = reset_analysis_usage(shop, db_path) if is_plan_upgrade(old_plan, plan) else 0
        return {"granted_plan": plan, "reset_events": cleared}
    return {"reset_events": reset_analysis_usage(shop, db_path)}
