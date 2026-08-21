"""Single-use signed codes: quota resets and plan grants.

Formats (SIG = first 8 hex chars, uppercased, of HMAC-SHA256(payload, secret),
secret = `QUOTA_CODE_SECRET` env var; minted offline with
`scripts/generate_quota_code.py`; each code burns once globally in
`redeemed_quota_codes`):

- `GEO-<BASE>-<SIG>`     — quota reset (payload = BASE): wipes the shop's
  rolling usage window, any plan.
- `GEOPRO-<BASE>-<SIG>`  — grants the Pro plan (payload = "pro:BASE") via
  plan_override, plus a quota reset when it's an upgrade.
- `GEOBIG-<BASE>-<SIG>`  — same for the Grande boutique (agency) plan
  (payload = "agency:BASE").

A plan prefix may carry a duration in days — `GEOPRO30-<BASE>-<SIG>`, payload
"pro:30:BASE" — which expires the override that many days after redemption.
The duration is part of the signed payload, so editing 30 into 365 breaks the
signature. A prefix without digits grants the plan indefinitely, which is what
every code minted before this existed does.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.db import DB_PATH
from app.db_adapter import get_conn

_CODE_RE = re.compile(r"^(GEO|GEOPRO|GEOBIG)(\d{1,3})?-([A-Z0-9]{4,32})-([0-9A-F]{8})$")
_PREFIX_PLANS = {"GEOPRO": "pro", "GEOBIG": "agency"}
_SIG_LEN = 8

# shop_config key holding the expiry of a time-limited plan_override.
OVERRIDE_EXPIRY_KEY = "plan_override_expires_at"


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


def build_code(base: str, secret: str, plan: str | None = None, days: int | None = None) -> str:
    """Mint a code — quota reset by default, plan grant when `plan` is given.

    `days` limits a plan grant in time; omit it (or pass 0) for an indefinite
    one. It is signed with the rest, so it cannot be edited after minting.
    """
    base = base.strip().upper()
    if not re.fullmatch(r"[A-Z0-9]{4,32}", base):
        raise ValueError("BASE must be 4-32 uppercase letters/digits")
    if plan is None:
        if days:
            raise ValueError("a quota reset code cannot carry a duration")
        return f"GEO-{base}-{_signature(base, secret)}"
    if plan not in ("pro", "agency"):
        raise ValueError("plan must be 'pro' or 'agency'")
    if days is not None and not 0 <= days <= 999:
        raise ValueError("days must be between 0 and 999")
    prefix = "GEOPRO" if plan == "pro" else "GEOBIG"
    if not days:
        return f"{prefix}-{base}-{_signature(f'{plan}:{base}', secret)}"
    return f"{prefix}{days}-{base}-{_signature(f'{plan}:{days}:{base}', secret)}"


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
    prefix, raw_days, base, sig = match.groups()
    plan = _PREFIX_PLANS.get(prefix)
    days = int(raw_days) if raw_days else 0
    if days and not plan:
        raise InvalidQuotaCode("a quota reset code cannot carry a duration")
    if plan:
        payload = f"{plan}:{days}:{base}" if days else f"{plan}:{base}"
    else:
        payload = base
    if not hmac.compare_digest(sig, _signature(payload, secret)):
        raise InvalidQuotaCode("invalid signature")

    path = db_path if db_path is not None else DB_PATH
    normalized = f"{prefix}{raw_days or ''}-{base}-{sig}"
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
    from app.billing.quotas import is_plan_upgrade, reset_usage_window  # noqa: PLC0415

    try:
        if plan:
            from app.apply.theme_entitlement import set_theme_entitlement  # noqa: PLC0415
            from app.billing.subscription_store import get_plan_for_shop  # noqa: PLC0415
            from app.shop_config_store import set_shop_config  # noqa: PLC0415

            old_plan = get_plan_for_shop(shop, db_path)
            set_shop_config(shop, "plan_override", plan)
            # Always written, even for an indefinite grant: an empty value must
            # clear the expiry left by a previous time-limited code, otherwise
            # the new grant would inherit a deadline nobody set.
            expires_at = (datetime.now(UTC) + timedelta(days=days)).isoformat() if days else ""
            set_shop_config(shop, OVERRIDE_EXPIRY_KEY, expires_at)
            set_theme_entitlement(shop, True)
            cleared = reset_usage_window(shop, db_path) if is_plan_upgrade(old_plan, plan) else 0
            return {
                "granted_plan": plan,
                "reset_events": cleared,
                "expires_at": expires_at or None,
            }
        return {"reset_events": reset_usage_window(shop, db_path)}
    except Exception:
        # The burn above is already committed, in its own transaction. Without
        # this release, any failure here spends the code while granting
        # nothing — which is exactly what happened when a psycopg2
        # InterfaceError burned three codes and reset no quota at all. Broad on
        # purpose: whatever the failure, the merchant must keep their code.
        with get_conn(path) as conn:
            conn.execute("DELETE FROM redeemed_quota_codes WHERE code = ?", (normalized,))
        raise
