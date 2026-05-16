"""Runtime safety gates for Shopify mutations."""

from __future__ import annotations

import os

from fastapi import HTTPException


def _is_truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


def is_pilot_safe_mode() -> bool:
    """Return whether live Shopify writes are blocked for the pilot."""
    return _is_truthy(os.getenv("LEONIE_PILOT_SAFE_MODE"))


def require_shopify_write_allowed(
    *,
    action: str,
    dry_run: bool,
    confirmed: bool,
) -> None:
    """Raise when a live Shopify write is not allowed.

    Args:
        action: Human-readable action name used in error messages.
        dry_run: True when the request is preview-only.
        confirmed: True when the caller explicitly confirmed a live write.

    Raises:
        HTTPException: 403 in pilot-safe mode, 409 when confirmation is missing.
    """
    if dry_run:
        return

    if is_pilot_safe_mode():
        raise HTTPException(
            status_code=403,
            detail=(
                f"Pilot-safe mode blocks live Shopify writes for '{action}'. "
                "Run this action in dry-run mode."
            ),
        )

    if not confirmed:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Live Shopify write '{action}' requires explicit confirmation. "
                "Set confirm_live_write=true after reviewing the dry-run output."
            ),
        )


def require_billing_write_allowed(*, action: str) -> None:
    """Raise when pilot-safe mode blocks Shopify Billing mutations."""
    if is_pilot_safe_mode():
        raise HTTPException(
            status_code=403,
            detail=f"Pilot-safe mode blocks Shopify Billing write '{action}'.",
        )
