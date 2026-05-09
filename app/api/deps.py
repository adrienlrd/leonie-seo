"""FastAPI dependencies shared across API routers."""

import os
from dataclasses import dataclass
from pathlib import Path

from fastapi import HTTPException

from app.oauth.token_store import get_token

_API_VERSION = "2025-01"
_SNAPSHOT_DEFAULT = Path("data/raw/shopify_snapshot.json")


@dataclass
class ShopContext:
    shop: str
    access_token: str
    graphql_endpoint: str
    graphql_headers: dict[str, str]
    snapshot_path: Path


def get_shop_context(shop: str) -> ShopContext:
    """Resolve Shopify credentials for a shop.

    Priority:
    1. OAuth token from shop_tokens SQLite table (installed merchants).
    2. Primary tenant credentials from .env (local development fallback).
    """
    record = get_token(shop)
    if record:
        token = record["access_token"]
        snapshot = Path(f"data/raw/{shop}/shopify_snapshot.json")
    else:
        primary_shop = os.getenv("SHOPIFY_STORE_DOMAIN", "")
        primary_token = os.getenv("SHOPIFY_ACCESS_TOKEN", "")
        if shop == primary_shop and primary_token:
            token = primary_token
            snapshot = _SNAPSHOT_DEFAULT
        else:
            raise HTTPException(
                status_code=403,
                detail=f"Shop '{shop}' is not installed. Complete OAuth first.",
            )

    return ShopContext(
        shop=shop,
        access_token=token,
        graphql_endpoint=f"https://{shop}/admin/api/{_API_VERSION}/graphql.json",
        graphql_headers={
            "X-Shopify-Access-Token": token,
            "Content-Type": "application/json",
        },
        snapshot_path=snapshot,
    )
