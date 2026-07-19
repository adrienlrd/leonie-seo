"""Mint single-use signed codes (operator-only).

Usage:
    QUOTA_CODE_SECRET=<secret> python scripts/generate_quota_code.py BASE [BASE ...]
    QUOTA_CODE_SECRET=<secret> python scripts/generate_quota_code.py --plan pro BASE
    QUOTA_CODE_SECRET=<secret> python scripts/generate_quota_code.py --plan agency BASE

Without --plan: quota reset codes (GEO-...). With --plan pro/agency: plan
grant codes (GEOPRO-.../GEOBIG-...) that switch the redeeming shop to that
plan. Each BASE (4-32 uppercase letters/digits) yields one code; every code
burns globally on first redemption — mint a new BASE per recipient.
"""

from __future__ import annotations

import os
import sys

from app.billing.quota_codes import build_code


def main() -> int:
    secret = os.getenv("QUOTA_CODE_SECRET", "")
    if not secret:
        print("QUOTA_CODE_SECRET env var is required", file=sys.stderr)
        return 1
    args = sys.argv[1:]
    plan: str | None = None
    if args and args[0] == "--plan":
        if len(args) < 2 or args[1] not in ("pro", "agency"):
            print("--plan requires 'pro' or 'agency'", file=sys.stderr)
            return 1
        plan = args[1]
        args = args[2:]
    if not args:
        print(__doc__, file=sys.stderr)
        return 1
    for base in args:
        print(build_code(base, secret, plan))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
