"""GDPR mandatory webhooks — required for Shopify App Store compliance.

Shopify sends these three webhooks to every app in the App Store:
- customers/data_request : merchant requested a customer's data export
- customers/redact       : delete a specific customer's data
- shop/redact            : delete all shop data (48h after uninstall)

All three must return 200 within 5 seconds or Shopify marks the app non-compliant.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime

from fastapi import APIRouter, Header, HTTPException, Request

from app.db import DB_PATH
from app.db_adapter import get_conn
from app.oauth.hmac_validator import verify_webhook_hmac
from app.oauth.token_store import delete_token

router = APIRouter()


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

    Belt-and-suspenders after app/uninstalled: remove the OAuth token if it
    somehow survived the uninstall webhook.
    """
    body = await request.body()
    _require_hmac(body, x_shopify_hmac_sha256)
    shop = x_shopify_shop_domain or ""
    _log("shop/redact", shop, body)
    if shop:
        delete_token(shop)
    return {"status": "ok"}
