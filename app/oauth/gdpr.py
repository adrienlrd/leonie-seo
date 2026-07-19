"""GDPR mandatory webhooks — required for Shopify App Store compliance.

Shopify sends these three webhooks to every app in the App Store:
- customers/data_request : merchant requested a customer's data export
- customers/redact       : delete a specific customer's data
- shop/redact            : delete all shop data (48h after uninstall)

All three must return 200 within 5 seconds or Shopify marks the app non-compliant.
"""

from __future__ import annotations

import logging
import os
import re
import shutil
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Request

from app.db import DB_PATH
from app.db_adapter import get_conn
from app.oauth.hmac_validator import verify_webhook_hmac
from app.paths import data_dir

logger = logging.getLogger(__name__)

router = APIRouter()

# Same defense-in-depth pattern as app/api/deps.py: never join an unvalidated
# shop value to a filesystem path (stops `..` traversal cold).
_SHOP_DOMAIN_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9\-]*\.myshopify\.com$")
# Resolve the raw-data directory the same way the rest of the app writes it
# (respecting the DATA_DIR env var / Render persistent disk). A hardcoded
# parents[2]/data/raw path silently missed the real files in production, so the
# reset deleted DB rows but left business_profile.json / snapshots on disk —
# leaving the merchant with a fully populated dashboard after a "reset".
_RAW_DIR = data_dir()

# Every table in app/db.py with a `shop` column. gdpr_requests is intentionally
# excluded: it is the compliance audit trail proving redaction requests were
# received and honored. Shared caches keyed by URL/keyword (keyword_data_cache,
# competitor_crawl_cache) hold no shop data and are excluded too.
_SHOP_SCOPED_TABLES = (
    "shop_tokens",
    "google_tokens",
    "seo_changes",
    "snapshots",
    "subscriptions",
    "meta_suggestions",
    "llm_metrics",
    "llm_cache",
    "product_embeddings",
    "query_embeddings",
    "shop_config",
    "jobs",
    "geo_impact_events",
    "geo_optimization_snapshots",
    "crawl_findings",
    "competitor_crawl_runs",
    "content_actions",
    "content_action_decisions",
    "llms_txt_publications",
    "theme_write_log",
    "llms_txt_prefs",
    "product_improvement_tags",
    "tag_performance_history",
    "continuous_improvement_agent_runs",
    "learning_observations",
    "learning_weights",
    "learning_runs",
    "learning_policy_decisions",
    "learning_pending_approvals",
    "merchant_learning_settings",
    "agent_schedule_settings",
    "analysis_artifacts",
    "usage_events",
    "redeemed_quota_codes",
)

# Tables kept during an in-app "reset to first-open" (Danger Zone). The OAuth
# token must survive or the embedded session breaks; the subscription must
# survive because a merchant reset cannot un-bill an active plan. Everything
# else (including google_tokens → GSC/GA4) is wiped to restore the first-open
# state. This differs from shop/redact, which deletes everything on uninstall.
# redeemed_quota_codes survives the in-app reset too: resetting the app must
# not un-burn single-use quota codes.
_RESET_PRESERVED_TABLES = ("shop_tokens", "subscriptions", "redeemed_quota_codes")


def purge_shop_data(shop: str) -> None:
    """Delete every trace of a shop: all shop-scoped DB rows + data/raw/{shop} files.

    Called from shop/redact (48h after uninstall). Raises ValueError on a
    malformed shop domain instead of touching the filesystem.
    """
    if not _SHOP_DOMAIN_RE.match(shop):
        raise ValueError(f"Invalid shop domain: {shop!r}")
    with get_conn(DB_PATH) as conn:
        for table in _SHOP_SCOPED_TABLES:
            # Table names come from the fixed allowlist above, never from input.
            conn.execute(f"DELETE FROM {table} WHERE shop = ?", (shop,))  # noqa: S608
    shop_dir = _RAW_DIR / shop
    if shop_dir.is_dir():
        shutil.rmtree(shop_dir)


def reset_shop_data(shop: str) -> dict[str, Any]:
    """Reset a shop to its first-open state while keeping it installed.

    Deletes every shop-scoped DB row and the data/raw/{shop} directory, except
    the tables in ``_RESET_PRESERVED_TABLES`` (OAuth token + subscription).
    Triggered by the Danger Zone "reset app" action, not by GDPR redaction.
    Raises ValueError on a malformed shop domain instead of touching the disk.

    Each table is wiped in its own transaction so one failing table (e.g. a
    prod schema drift where an allowlisted table is missing) cannot abort the
    whole reset — it is skipped, reported in ``failed`` and logged, while every
    other table is still cleared. Returns ``{"deleted", "failed"}``.
    """
    if not _SHOP_DOMAIN_RE.match(shop):
        raise ValueError(f"Invalid shop domain: {shop!r}")
    tables = [t for t in _SHOP_SCOPED_TABLES if t not in _RESET_PRESERVED_TABLES]
    # Billing state and the app language are preferences, not merchant data —
    # losing them on reset silently downgraded overridden shops to free and
    # flipped the AI output language back to English mid-onboarding.
    _PRESERVED_CONFIG_KEYS = ("plan_override", "app_language")
    preserved_config: dict[str, str] = {}
    try:
        with get_conn(DB_PATH) as conn:
            for key in _PRESERVED_CONFIG_KEYS:
                row = conn.execute(
                    "SELECT value FROM shop_config WHERE shop = ? AND key = ?",
                    (shop, key),
                ).fetchone()
                if row:
                    preserved_config[key] = row["value"] if isinstance(row, dict) else row[0]
    except Exception as exc:  # noqa: BLE001 - best-effort: a missing table must not block the reset
        logger.warning("reset_shop_data(%s): config read failed: %s", shop, exc)
    deleted = 0
    failed: list[str] = []
    for table in tables:
        try:
            # Table names come from the fixed allowlist above, never from input.
            with get_conn(DB_PATH) as conn:
                cur = conn.execute(f"DELETE FROM {table} WHERE shop = ?", (shop,))  # noqa: S608
                deleted += max(cur.rowcount, 0)
        except Exception as exc:  # noqa: BLE001 - best-effort wipe: skip + report a failing table
            failed.append(table)
            logger.warning("reset_shop_data(%s): table %s failed: %s", shop, table, exc)
    shop_dir = _RAW_DIR / shop
    if shop_dir.is_dir():
        try:
            shutil.rmtree(shop_dir)
        except OSError as exc:
            failed.append("data/raw")
            logger.warning("reset_shop_data(%s): raw dir removal failed: %s", shop, exc)
    for key, value in preserved_config.items():
        try:
            with get_conn(DB_PATH) as conn:
                conn.execute(
                    "INSERT INTO shop_config (shop, key, value) VALUES (?, ?, ?)"
                    " ON CONFLICT(shop, key) DO UPDATE SET value = excluded.value",
                    (shop, key, value),
                )
        except Exception as exc:  # noqa: BLE001 - best-effort restore, reported but non-fatal
            failed.append(f"{key}_restore")
            logger.warning("reset_shop_data(%s): %s restore failed: %s", shop, key, exc)
    logger.info(
        "reset_shop_data(%s): deleted %d rows + raw dir; failed=%s",
        shop, deleted, failed,
    )
    return {"deleted": deleted, "failed": failed}


def _require_hmac(body: bytes, header_hmac: str | None) -> None:
    secret = os.getenv("SHOPIFY_CLIENT_SECRET")
    if not secret:
        raise HTTPException(status_code=500, detail="SHOPIFY_CLIENT_SECRET not set")
    if not verify_webhook_hmac(body, header_hmac, secret):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")


def _log(topic: str, shop: str, payload: bytes) -> None:
    # DB_PATH may be monkeypatched by tests to a temp SQLite file.
    # get_conn(DB_PATH) detects equality with the canonical default path to
    # decide between Postgres (production) and SQLite (test isolation).
    with get_conn(DB_PATH) as conn:
        conn.execute(
            "INSERT INTO gdpr_requests (received_at, topic, shop, payload) VALUES (?, ?, ?, ?)",
            (datetime.now(UTC).isoformat(), topic, shop, payload.decode("utf-8", errors="replace")),
        )


@router.post("/customers/data_request")
async def customers_data_request(
    request: Request,
    x_shopify_hmac_sha256: str | None = Header(default=None),
    x_shopify_shop_domain: str | None = Header(default=None),
) -> dict:
    """Acknowledge a customer data export request.

    We do not store individual customer PII — only shop-level OAuth tokens.
    Log the request for the compliance audit trail; Shopify handles the export.
    """
    body = await request.body()
    _require_hmac(body, x_shopify_hmac_sha256)
    _log("customers/data_request", x_shopify_shop_domain or "", body)
    return {"status": "ok"}


@router.post("/customers/redact")
async def customers_redact(
    request: Request,
    x_shopify_hmac_sha256: str | None = Header(default=None),
    x_shopify_shop_domain: str | None = Header(default=None),
) -> dict:
    """Acknowledge a customer data deletion request.

    We store no individual customer data, so there is nothing to delete.
    Log for the compliance audit trail.
    """
    body = await request.body()
    _require_hmac(body, x_shopify_hmac_sha256)
    _log("customers/redact", x_shopify_shop_domain or "", body)
    return {"status": "ok"}


@router.post("/shop/redact")
async def shop_redact(
    request: Request,
    x_shopify_hmac_sha256: str | None = Header(default=None),
    x_shopify_shop_domain: str | None = Header(default=None),
) -> dict:
    """Delete all shop data 48 hours after uninstall.

    Purges every shop-scoped DB row and the data/raw/{shop} directory.
    A malformed shop domain is logged but not purged (nothing to delete,
    and retrying would never succeed) — still return 200 as Shopify requires.
    """
    body = await request.body()
    _require_hmac(body, x_shopify_hmac_sha256)
    shop = x_shopify_shop_domain or ""
    _log("shop/redact", shop, body)
    if shop and _SHOP_DOMAIN_RE.match(shop):
        purge_shop_data(shop)
    return {"status": "ok"}
