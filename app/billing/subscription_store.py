"""Subscription store — one active subscription per shop, backed by DB adapter."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from app.db import DB_PATH
from app.db_adapter import get_conn

_VALID_PLANS = frozenset({"free", "pro", "agency"})
PLAN_RANK = {"free": 0, "pro": 1, "agency": 2}
_ACTIVE_STATUSES = frozenset({"active"})
# Shopify does not refund a cancelled subscription pro rata, so the merchant
# keeps what they paid for until the period ends. Frozen/expired/declined are
# unpaid states and end access at once.
_GRACE_STATUSES = frozenset({"cancelled"})


def upsert_subscription(
    shop: str,
    plan: str,
    status: str,
    subscription_id: str | None = None,
    db_path: Path | None = None,
) -> None:
    """Insert or update the subscription record for a shop."""
    path = db_path if db_path is not None else DB_PATH
    now = datetime.now(UTC).isoformat()
    with get_conn(path) as conn:
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


def get_subscription(shop: str, db_path: Path | None = None) -> dict | None:
    """Return the subscription row for a shop, or None."""
    path = db_path if db_path is not None else DB_PATH
    with get_conn(path) as conn:
        row = conn.execute("SELECT * FROM subscriptions WHERE shop = ?", (shop,)).fetchone()
    return row


def get_subscription_by_id(subscription_id: str, db_path: Path | None = None) -> dict | None:
    """Return the subscription row matching a Shopify subscription GID."""
    path = db_path if db_path is not None else DB_PATH
    with get_conn(path) as conn:
        row = conn.execute(
            "SELECT * FROM subscriptions WHERE subscription_id = ?", (subscription_id,)
        ).fetchone()
    return row


def update_subscription_status(
    subscription_id: str,
    status: str,
    db_path: Path | None = None,
    current_period_end: str | None = None,
) -> bool:
    """Update status by subscription GID. Returns True if a row was updated.

    `current_period_end` is Shopify's paid-through date; it is only written
    when supplied, so a status event without it never erases a known deadline.
    """
    path = db_path if db_path is not None else DB_PATH
    now = datetime.now(UTC).isoformat()
    with get_conn(path) as conn:
        if current_period_end:
            cur = conn.execute(
                "UPDATE subscriptions SET status = ?, updated_at = ?,"
                " current_period_end = ? WHERE subscription_id = ?",
                (status, now, current_period_end, subscription_id),
            )
        else:
            cur = conn.execute(
                "UPDATE subscriptions SET status = ?, updated_at = ? WHERE subscription_id = ?",
                (status, now, subscription_id),
            )
    return cur.rowcount > 0


def _parse_deadline(timestamp: str | None) -> datetime | None:
    """Parse an ISO timestamp, or None when absent or unreadable."""
    if not timestamp:
        return None
    try:
        deadline = datetime.fromisoformat(timestamp)
    except ValueError:
        return None
    return deadline.replace(tzinfo=UTC) if deadline.tzinfo is None else deadline


def _is_future(timestamp: str | None) -> bool:
    """True only when the timestamp reads as a date still ahead of now.

    Used to *extend* access, so anything unreadable means no extension.
    """
    deadline = _parse_deadline(timestamp)
    return deadline is not None and deadline > datetime.now(UTC)


def _is_expired(timestamp: str | None) -> bool:
    """True only when the timestamp reads as a date already past.

    Used to *revoke* access, so anything unreadable means no deadline at all —
    a corrupted value must not silently cut a merchant off.
    """
    deadline = _parse_deadline(timestamp)
    return deadline is not None and deadline <= datetime.now(UTC)


def get_override_plan(shop: str) -> str | None:
    """Return the partner-code plan for a shop, or None once it has expired."""
    from app.billing.quota_codes import OVERRIDE_EXPIRY_KEY
    from app.shop_config_store import get_shop_config

    try:
        override = get_shop_config(shop, "plan_override")
        expires_at = get_shop_config(shop, OVERRIDE_EXPIRY_KEY)
    except sqlite3.Error:
        # Global config DB not provisioned yet (fresh install, isolated tests).
        return None
    if override not in _VALID_PLANS:
        return None
    # An empty expiry means indefinite — every code minted before durations
    # existed, plus grants that deliberately never end.
    return None if _is_expired(expires_at) else override


def get_subscription_plan(shop: str, db_path: Path | None = None) -> str | None:
    """Return the plan the shop's subscription entitles it to, or None."""
    sub = get_subscription(shop, db_path)
    if not sub:
        return None
    status = sub["status"]
    entitled = status in _ACTIVE_STATUSES or (
        status in _GRACE_STATUSES and _is_future(sub.get("current_period_end"))
    )
    if not entitled:
        return None
    plan = sub["plan"]
    return plan if plan in _VALID_PLANS else None


def get_plan_for_shop(shop: str, db_path: Path | None = None) -> str:
    """Return the active plan for a shop. Defaults to 'free'.

    A partner code and a paid subscription can coexist; the higher of the two
    wins, so a code never caps a merchant who pays for more than it grants.

    Args:
        shop: Shopify shop domain (e.g. mystore.myshopify.com).
        db_path: Override DB path (tests only).

    Returns:
        Plan name: "free", "pro", or "agency".
    """
    candidates = [get_override_plan(shop), get_subscription_plan(shop, db_path)]
    return max(
        (plan for plan in candidates if plan),
        key=lambda plan: PLAN_RANK.get(plan, 0),
        default="free",
    )
