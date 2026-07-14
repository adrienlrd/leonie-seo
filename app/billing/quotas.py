"""Per-plan usage quotas over a rolling 28-day window."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.billing.subscription_store import get_plan_for_shop
from app.db import DB_PATH
from app.db_adapter import get_conn

WINDOW_DAYS = 28

# kind → max events per rolling window; "products" is a cap, not an event count.
PLAN_QUOTAS: dict[str, dict[str, int | bool]] = {
    "free": {
        "products": 3,
        "analysis": 1,
        "product_analysis": 1,
        "blog": 3,
        "auto_analysis": False,
    },
    "pro": {
        "products": 15,
        "analysis": 5,
        "product_analysis": 3,
        "blog": 20,
        "auto_analysis": True,
    },
    "agency": {
        "products": 35,
        "analysis": 10,
        "product_analysis": 5,
        "blog": 40,
        "auto_analysis": True,
    },
}

_COUNTED_KINDS = frozenset({"analysis", "blog"})

# Per-product analysis is tracked with a product-scoped kind: "product_analysis:{id}".
_PRODUCT_ANALYSIS_PREFIX = "product_analysis:"


class QuotaExceeded(Exception):
    """Raised when a shop hits its plan quota for a usage kind."""

    def __init__(self, plan: str, kind: str, used: int, quota: int) -> None:
        self.plan = plan
        self.kind = kind
        self.used = used
        self.quota = quota
        super().__init__(f"Quota '{kind}' exceeded for plan '{plan}': {used}/{quota}")

    def payload(self) -> dict:
        upgrade = "pro" if self.plan == "free" else "agency"
        return {
            "error": "quota_exceeded",
            "kind": self.kind,
            "plan": self.plan,
            "used": self.used,
            "quota": self.quota,
            "window_days": WINDOW_DAYS,
            "upgrade": upgrade,
        }


def get_quotas(plan: str) -> dict[str, int | bool]:
    """Return the quota set for a plan. Unknown plans fall back to free."""
    return PLAN_QUOTAS.get(plan, PLAN_QUOTAS["free"])


def get_usage(shop: str, kind: str, db_path: Path | None = None) -> int:
    """Count usage events of a kind within the rolling window."""
    path = db_path if db_path is not None else DB_PATH
    cutoff = (datetime.now(UTC) - timedelta(days=WINDOW_DAYS)).isoformat()
    with get_conn(path) as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM usage_events WHERE shop = ? AND kind = ? AND created_at >= ?",
            (shop, kind, cutoff),
        ).fetchone()
    return int(row["n"] if isinstance(row, dict) else row[0])


def record_usage(shop: str, kind: str, db_path: Path | None = None) -> None:
    """Record one usage event for a shop."""
    path = db_path if db_path is not None else DB_PATH
    with get_conn(path) as conn:
        conn.execute(
            "INSERT INTO usage_events (shop, kind, created_at) VALUES (?, ?, ?)",
            (shop, kind, datetime.now(UTC).isoformat()),
        )


def check_quota(shop: str, kind: str, db_path: Path | None = None) -> None:
    """Raise QuotaExceeded when the shop has used up its window quota for kind."""
    if kind not in _COUNTED_KINDS:
        raise ValueError(f"Unknown counted quota kind: '{kind}'")
    plan = get_plan_for_shop(shop, db_path)
    quota = int(get_quotas(plan)[kind])
    used = get_usage(shop, kind, db_path)
    if used >= quota:
        raise QuotaExceeded(plan, kind, used, quota)


def check_product_analysis_quota(
    shop: str, product_id: str, db_path: Path | None = None
) -> None:
    """Raise QuotaExceeded when a single product has been analysed too many times.

    The limit is per product over the rolling window: free 1, pro 3, agency 5.
    """
    plan = get_plan_for_shop(shop, db_path)
    quota = int(get_quotas(plan)["product_analysis"])
    kind = f"{_PRODUCT_ANALYSIS_PREFIX}{product_id}"
    used = get_usage(shop, kind, db_path)
    if used >= quota:
        raise QuotaExceeded(plan, "product_analysis", used, quota)


def record_product_analysis(shop: str, product_id: str, db_path: Path | None = None) -> None:
    """Record one analysis event for a single product."""
    record_usage(shop, f"{_PRODUCT_ANALYSIS_PREFIX}{product_id}", db_path)


def product_analysis_quota(shop: str, db_path: Path | None = None) -> int:
    """Max analyses allowed per product over the window for the shop's plan."""
    plan = get_plan_for_shop(shop, db_path)
    return int(get_quotas(plan)["product_analysis"])


def product_cap(shop: str, db_path: Path | None = None) -> int:
    """Max products the shop's plan allows in analyses."""
    plan = get_plan_for_shop(shop, db_path)
    return int(get_quotas(plan)["products"])


def auto_analysis_allowed(shop: str, db_path: Path | None = None) -> bool:
    """Whether the shop's plan includes automatic analysis."""
    plan = get_plan_for_shop(shop, db_path)
    return bool(get_quotas(plan)["auto_analysis"])
