"""Mint single-use quota reset codes (operator-only).

Usage:
    QUOTA_CODE_SECRET=<secret> python scripts/generate_quota_code.py BASE [BASE ...]

Each BASE (4-32 uppercase letters/digits, e.g. LAUNCH01) yields one code
like GEO-LAUNCH01-3F2A9C1B. A code is valid on any shop/plan and burns
globally on first redemption — mint a new BASE for each recipient.
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
    bases = sys.argv[1:]
    if not bases:
        print(__doc__, file=sys.stderr)
        return 1
    for base in bases:
        print(build_code(base, secret))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
