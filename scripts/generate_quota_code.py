"""Mint single-use signed codes (operator-only).

Usage:
    QUOTA_CODE_SECRET=<secret> python scripts/generate_quota_code.py BASE [BASE ...]
    QUOTA_CODE_SECRET=<secret> python scripts/generate_quota_code.py --plan pro BASE
    QUOTA_CODE_SECRET=<secret> python scripts/generate_quota_code.py --plan agency --days 90 BASE

Without --plan: quota reset codes (GEO-...) wiping the shop's rolling usage
window. With --plan pro/agency: plan grant codes (GEOPRO-.../GEOBIG-...) that
switch the redeeming shop to that plan.

A plan grant lasts --days days (default 30); --days 0 grants it indefinitely.
The duration is signed into the code, so it cannot be edited after minting.

Each BASE (4-32 uppercase letters/digits) yields one code; every code burns
globally on first redemption — mint a new BASE per recipient.
"""

from __future__ import annotations

import argparse
import os
import sys

from app.billing.quota_codes import build_code

DEFAULT_PLAN_DAYS = 30


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bases", nargs="+", metavar="BASE")
    parser.add_argument("--plan", choices=("pro", "agency"))
    parser.add_argument(
        "--days",
        type=int,
        help=f"days a plan grant lasts (default {DEFAULT_PLAN_DAYS}, 0 = indefinite)",
    )
    args = parser.parse_args()

    secret = os.getenv("QUOTA_CODE_SECRET", "")
    if not secret:
        print("QUOTA_CODE_SECRET env var is required", file=sys.stderr)
        return 1
    if args.days is not None and not args.plan:
        print("--days only applies to --plan codes", file=sys.stderr)
        return 1

    days = None if not args.plan else (args.days if args.days is not None else DEFAULT_PLAN_DAYS)
    for base in args.bases:
        print(build_code(base, secret, args.plan, days))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
