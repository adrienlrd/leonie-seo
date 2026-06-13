"""Runtime safety gates for Shopify mutations."""

from __future__ import annotations

import os

from fastapi import HTTPException


def is_pilot_safe_mode() -> bool:
    """Pilot-safe mode is permanently disabled — live Shopify writes are always
    allowed (gated only by per-write ``confirm_live_write`` confirmation).

    Kept as a single chokepoint returning False so the env var
    ``LEONIE_PILOT_SAFE_MODE`` can never re-block writes from configuration.
    """
    return False


_THEME_WRITE_MODES = {"disabled", "review_safe", "live"}


def theme_write_mode() -> str:
    """Return the active theme-write mode for the AI discovery files.

    Controlled by ``LEONIE_THEME_WRITE_MODE`` — one of:
    - ``disabled``     : no theme write at all (preview/export only).
    - ``review_safe``  : writes allowed, restricted to the 3 allowlisted AI
      template files, with explicit merchant confirmation + detailed logging.
    - ``live``         : same allowlist, intended for production after review.

    Default: ``review_safe`` in production (``DATABASE_URL`` present),
    ``disabled`` in local/test so nothing is ever written by accident.
    """
    raw = (os.getenv("LEONIE_THEME_WRITE_MODE") or "").strip().lower()
    if raw in _THEME_WRITE_MODES:
        return raw
    if os.getenv("PYTEST_CURRENT_TEST") or not os.getenv("DATABASE_URL"):
        return "disabled"
    return "review_safe"


def require_theme_write_allowed(*, confirmed: bool) -> None:
    """Raise when publishing the AI files to the theme is not allowed.

    Args:
        confirmed: True when the merchant explicitly confirmed the publish in
            the UI (never defaulted on — see app.geo-llms-txt route).

    Raises:
        HTTPException: 403 when the mode is ``disabled``; 409 when the merchant
            confirmation is missing in ``review_safe`` / ``live`` mode.
    """
    mode = theme_write_mode()
    if mode == "disabled":
        raise HTTPException(
            status_code=403,
            detail=(
                "Theme writes are disabled (LEONIE_THEME_WRITE_MODE=disabled). "
                "Use preview/export only."
            ),
        )
    if not confirmed:
        raise HTTPException(
            status_code=409,
            detail=(
                "Publishing the AI files to your theme requires explicit "
                "merchant confirmation. Set confirm=true after reviewing which "
                "files will be created."
            ),
        )



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
