"""GDPR mandatory webhooks — required for Shopify App Store compliance.

Shopify sends these three webhooks to every app in the App Store:
- customers/data_request : merchant requested a customer's data export
- customers/redact       : delete a specific customer's data
- shop/redact            : delete all shop data (48h after uninstall)

All three must return 200 within 5 seconds or Shopify marks the app non-compliant.
"""

from __future__ import annotations

import os
import re
import shutil
from datetime import UTC, datetime
from pathlib import Path

from fastapi import APIRouter, Header, HTTPException, Request

from app.db import DB_PATH
from app.db_adapter import get_conn
from app.oauth.hmac_validator import verify_webhook_hmac

router = APIRouter()

# Same defense-in-depth pattern as app/api/deps.py: never join an unvalidated
# shop value to a filesystem path (stops `..` traversal cold).
_SHOP_DOMAIN_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9\-]*\.myshopify\.com$")
_RAW_DIR = Path(__file__).parents[2] / "data" / "raw"

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
)


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
