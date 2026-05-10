"""SQLite-backed subscription store — one active subscription per shop."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime

from app.db import DB_PATH

_VALID_PLANS = frozenset({"free", "pro", "agency"})
_ACTIVE_STATUSES = frozenset({"active"})


def upsert_subscription(
    shop: str,
    plan: str,
    status: str,
    subscription_id: str | None = None,
    db_path=None,
) -> None:
    """Insert or update the subscription record for a shop."""
    path = db_path or DB_PATH
    now = datetime.now(UTC).isoformat()
    with sqlite3.connect(path) as conn:
        conn.execute(
            """
            INSERT INTO subscriptions (shop, subscription_id, plan, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(shop) DO UPDATE SET
                subscription_id = excluded.subscription_id,
                plan            = excluded.plan,
                status          = excluded.status,
                updated_at      = excluded.updated_at
            """,
            (shop, subscription_id, plan, status, now, now),
        )


def get_subscription(shop: str, db_path=None) -> dict | None:
    """Return the subscription row for a shop, or None."""
    path = db_path or DB_PATH
    with sqlite3.connect(path) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM subscriptions WHERE shop = ?", (shop,)).fetchone()
    return dict(row) if row else None


def get_subscription_by_id(subscription_id: str, db_path=None) -> dict | None:
    """Return the subscription row matching a Shopify subscription GID."""
    path = db_path or DB_PATH
    with sqlite3.connect(path) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM subscriptions WHERE subscription_id = ?", (subscription_id,)
        ).fetchone()
    return dict(row) if row else None


def update_subscription_status(subscription_id: str, status: str, db_path=None) -> bool:
    """Update status by subscription GID. Returns True if a row was updated."""
    path = db_path or DB_PATH
    now = datetime.now(UTC).isoformat()
    with sqlite3.connect(path) as conn:
        cur = conn.execute(
            "UPDATE subscriptions SET status = ?, updated_at = ? WHERE subscription_id = ?",
            (status, now, subscription_id),
        )
    return cur.rowcount > 0


def get_plan_for_shop(shop: str, db_path=None) -> str:
    """Return the active plan for a shop. Defaults to 'free'.

    Args:
        shop: Shopify shop domain (e.g. mystore.myshopify.com).
        db_path: Override DB path (tests only).

    Returns:
        Plan name: "free", "pro", or "agency".
    """
    sub = get_subscription(shop, db_path)
    if not sub or sub["status"] not in _ACTIVE_STATUSES:
        return "free"
    plan = sub["plan"]
    return plan if plan in _VALID_PLANS else "free"
