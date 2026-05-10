"""FastAPI dependencies shared across API routers."""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

from fastapi import Depends, Header, HTTPException

from app.api.plans import PlanFeatures, get_features
from app.api.session_token import SessionTokenError, shop_from_payload, verify_session_token
from app.billing.subscription_store import get_plan_for_shop
from app.oauth.token_store import get_token

_API_VERSION = "2025-01"
_PROJECT_ROOT = Path(__file__).parents[2]
_SNAPSHOT_DEFAULT = _PROJECT_ROOT / "data" / "raw" / "shopify_snapshot.json"
_RAW_DIR = _PROJECT_ROOT / "data" / "raw"


@dataclass
class ShopContext:
    shop: str
    access_token: str
    graphql_endpoint: str
    graphql_headers: dict[str, str]
    snapshot_path: Path
    plan: str = "pro"


def _auth_required() -> bool:
    return os.getenv("LEONIE_REQUIRE_SESSION_TOKEN", "false").lower() in ("1", "true", "yes")


def _verify_token_matches_shop(authorization: str | None, shop: str) -> None:
    """Validate the Shopify session token in the Authorization header.

    No-op when LEONIE_REQUIRE_SESSION_TOKEN is false (development mode).
    """
    if not _auth_required():
        return

    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=401, detail="Missing Bearer session token in Authorization header"
        )

    token = authorization[7:].strip()
    try:
        payload = verify_session_token(token)
    except SessionTokenError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc

    if shop_from_payload(payload) != shop:
        raise HTTPException(status_code=403, detail="Session token does not match requested shop")


def get_shop_context(
    shop: str,
    authorization: Annotated[str | None, Header()] = None,
) -> ShopContext:
    """Resolve Shopify credentials for a shop, after auth gate.

    Auth priority (when enabled):
    - Shopify session token in Authorization header — required in prod.

    Credential priority:
    1. OAuth token from shop_tokens SQLite table (installed merchants).
    2. Primary tenant credentials from .env (local development fallback).
    """
    _verify_token_matches_shop(authorization, shop)

    record = get_token(shop)
    if record:
        token = record["access_token"]
        snapshot = _RAW_DIR / shop / "shopify_snapshot.json"
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
        plan=get_plan_for_shop(shop),
    )


def require_feature(feature: str):
    """Dependency factory: raises 403 when the active plan lacks a feature.

    Usage::

        @router.post("/shops/{shop}/apply/meta")
        async def apply_meta(ctx: Annotated[ShopContext, Depends(require_feature("apply"))]):
            ...

    FastAPI caches Depends results per request, so get_shop_context runs once.
    """

    def _check(ctx: Annotated[ShopContext, Depends(get_shop_context)]) -> ShopContext:
        features: PlanFeatures = get_features(ctx.plan)
        if not getattr(features, f"can_{feature}", False):
            plan_label = ctx.plan.capitalize()
            raise HTTPException(
                status_code=403,
                detail=(
                    f"La fonctionnalité '{feature}' n'est pas disponible avec le plan {plan_label}. "
                    "Passez au plan Pro ou Agency."
                ),
            )
        return ctx

    return _check
