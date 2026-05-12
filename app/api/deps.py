"""FastAPI dependencies shared across API routers."""

import os
import secrets
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


def _validate_internal_secret(received: str) -> None:
    """Verify the X-Internal-Secret header matches INTERNAL_API_SECRET.

    Constant-time comparison prevents timing attacks.
    """
    expected = os.getenv("INTERNAL_API_SECRET", "")
    if not expected:
        raise HTTPException(status_code=500, detail="INTERNAL_API_SECRET not configured on server")
    if not secrets.compare_digest(expected, received):
        raise HTTPException(status_code=403, detail="Invalid internal secret")


def get_shop_context(
    shop: str,
    authorization: Annotated[str | None, Header()] = None,
    x_leonie_shop: Annotated[str | None, Header()] = None,
    x_internal_secret: Annotated[str | None, Header()] = None,
) -> ShopContext:
    """Resolve Shopify credentials for a shop, after auth gate.

    Auth priority:
    1. Internal call from Remix — X-Leonie-Shop + X-Internal-Secret headers.
       Bypasses session token check (trusted internal network call).
    2. External call — Shopify session token in Authorization header (prod only).
       Falls back to env credentials for the primary tenant in dev mode.
    """
    is_internal = bool(x_leonie_shop and x_internal_secret)

    if is_internal:
        _validate_internal_secret(x_internal_secret)  # type: ignore[arg-type]
        if x_leonie_shop != shop:
            raise HTTPException(
                status_code=403,
                detail="X-Leonie-Shop header does not match the requested shop path",
            )
    else:
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


def require_internal_secret(
    x_internal_secret: Annotated[str | None, Header()] = None,
) -> None:
    """Dependency: require a valid X-Internal-Secret header (admin endpoints).

    Used for endpoints that don't carry a `{shop}` path segment but must still
    be protected — e.g. GET /api/shops (lists every installed tenant).

    Raises:
        HTTPException 403 if the header is missing or doesn't match
        INTERNAL_API_SECRET, or 500 if the server is misconfigured.
    """
    if x_internal_secret is None:
        raise HTTPException(status_code=403, detail="Missing X-Internal-Secret header")
    _validate_internal_secret(x_internal_secret)


def get_authenticated_shop(
    x_leonie_shop: Annotated[str | None, Header()] = None,
    x_internal_secret: Annotated[str | None, Header()] = None,
    authorization: Annotated[str | None, Header()] = None,
) -> str:
    """Dependency: resolve the authenticated shop without requiring it in the path.

    Used by endpoints like POST /api/jobs and GET /api/jobs/{job_id} that
    carry the shop in the body or in the job's owner field.

    Auth modes (same as get_shop_context):
    1. Internal call from Remix — X-Leonie-Shop + X-Internal-Secret.
    2. External call — Shopify session token in Authorization header.

    Returns:
        The authenticated shop domain.

    Raises:
        HTTPException 401/403 on missing or invalid credentials.
    """
    if x_leonie_shop and x_internal_secret:
        _validate_internal_secret(x_internal_secret)
        return x_leonie_shop

    # Fall back to session token (external clients)
    if not _auth_required():
        # Dev mode: allow X-Leonie-Shop without internal secret
        if x_leonie_shop:
            return x_leonie_shop
        primary = os.getenv("SHOPIFY_STORE_DOMAIN", "")
        if primary:
            return primary
        raise HTTPException(status_code=403, detail="No shop context available")

    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=401,
            detail="Missing Bearer session token in Authorization header",
        )
    token = authorization[7:].strip()
    try:
        payload = verify_session_token(token)
    except SessionTokenError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    return shop_from_payload(payload)


def require_feature(feature: str):
    """Dependency factory: raises 403 when the active plan lacks a feature."""

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
