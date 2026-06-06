"""Orchestrates publishing the AI discovery templates to the published theme.

Shopify serves /agents.md, /llms.txt and /llms-full.txt natively from theme
templates. Publishing writes those three ``templates/*.liquid`` files on the
merchant's published theme; unpublishing deletes them (reverting to Shopify's
default). The flow is idempotent: republishing identical content is a no-op.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Protocol

from app.apply.shopify_theme_files import ShopifyThemeError, ShopifyThemeWriter
from app.geo.llms_txt import build_llms_payload, wrap_liquid_raw
from app.llms_txt import store
from app.safety import theme_write_mode

logger = logging.getLogger(__name__)

AGENTS_TEMPLATE = "templates/agents.md.liquid"
LLMS_TEMPLATE = "templates/llms.txt.liquid"
LLMS_FULL_TEMPLATE = "templates/llms-full.txt.liquid"
TEMPLATE_FILENAMES = [AGENTS_TEMPLATE, LLMS_TEMPLATE, LLMS_FULL_TEMPLATE]

LLMS_TXT_PATH = "/llms.txt"
LLMS_FULL_TXT_PATH = "/llms-full.txt"
AGENTS_PATH = "/agents.md"
WEBHOOK_DEBOUNCE = timedelta(minutes=5)


class _ThemeWriter(Protocol):
    def get_published_theme_id(self) -> str: ...
    def upsert_templates(self, theme_id: str, files: dict[str, str]) -> list[str]: ...
    def delete_templates(self, theme_id: str, filenames: list[str]) -> list[str]: ...


class LlmsPublishError(Exception):
    """Raised when the theme publish flow fails for a non-scope reason."""


class ThemeWriteDisabledError(LlmsPublishError):
    """Raised when a theme write is attempted while the mode is ``disabled``."""


def _public_urls(shop: str) -> dict[str, str]:
    return {
        "public_url": f"https://{shop}{LLMS_TXT_PATH}",
        "public_full_url": f"https://{shop}{LLMS_FULL_TXT_PATH}",
        "public_agents_url": f"https://{shop}{AGENTS_PATH}",
    }


def publish(
    shop: str,
    access_token: str,
    snapshot: dict[str, Any],
    business_profile: dict[str, Any] | None,
    *,
    db_path: Path | None = None,
    theme_writer: _ThemeWriter | None = None,
    user_action: bool = False,
) -> dict[str, Any]:
    """Write the three AI templates onto the published theme.

    Idempotent: when the three content hashes already match the published ones,
    nothing is written and ``skipped`` is True.

    Backstop: refuses to write when ``LEONIE_THEME_WRITE_MODE=disabled`` — the
    API and webhook entry points gate this too, this is defense-in-depth so no
    code path can ever write while disabled.

    Args:
        user_action: True when the merchant explicitly triggered the publish
            (False for webhook-driven regeneration) — recorded in the audit log.

    Raises:
        ThemeWriteDisabledError: If the theme-write mode is ``disabled``.
        ShopifyThemeScopeError: If the write_themes scope is missing.
        ShopifyThemeError / LlmsPublishError: On other Shopify failures.
        LlmsTxtGenerationError: If the snapshot has no listable page.
    """
    if theme_write_mode() == "disabled":
        raise ThemeWriteDisabledError(
            "Theme writes are disabled (LEONIE_THEME_WRITE_MODE=disabled)."
        )

    payload = build_llms_payload(shop, snapshot, business_profile)
    existing = store.get_publication(shop, db_path)

    if (
        existing
        and existing.get("is_published")
        and existing.get("agents_hash") == payload["agents_content_hash"]
        and existing.get("llms_hash") == payload["content_hash"]
        and existing.get("full_hash") == payload["full_content_hash"]
    ):
        return {
            "skipped": True,
            "reason": "content_unchanged",
            "content_hash": payload["content_hash"],
            "warnings": payload["warnings"],
            **_public_urls(shop),
        }

    writer = theme_writer or ShopifyThemeWriter(shop, access_token)
    theme_id = writer.get_published_theme_id()
    files = {
        AGENTS_TEMPLATE: wrap_liquid_raw(payload["agents_md"]),
        LLMS_TEMPLATE: wrap_liquid_raw(payload["llms_txt"]),
        LLMS_FULL_TEMPLATE: wrap_liquid_raw(payload["llms_full_txt"]),
    }
    writer.upsert_templates(theme_id, files)

    published_at = datetime.now(UTC).isoformat()
    store.save_publication(
        shop,
        theme_id=theme_id,
        agents_hash=payload["agents_content_hash"],
        llms_hash=payload["content_hash"],
        full_hash=payload["full_content_hash"],
        published_at=published_at,
        db_path=db_path,
    )
    store.log_theme_write(
        shop,
        action="publish",
        filenames=list(files.keys()),
        theme_id=theme_id,
        hash_before={
            "agents": existing.get("agents_hash") if existing else None,
            "llms": existing.get("llms_hash") if existing else None,
            "full": existing.get("full_hash") if existing else None,
        },
        hash_after={
            "agents": payload["agents_content_hash"],
            "llms": payload["content_hash"],
            "full": payload["full_content_hash"],
        },
        user_action=user_action,
        db_path=db_path,
    )

    return {
        "skipped": False,
        "theme_id": theme_id,
        "content_hash": payload["content_hash"],
        "full_content_hash": payload["full_content_hash"],
        "agents_content_hash": payload["agents_content_hash"],
        "published_at": published_at,
        "summary": payload["summary"],
        "warnings": payload["warnings"],
        **_public_urls(shop),
    }


def unpublish(
    shop: str,
    access_token: str,
    *,
    db_path: Path | None = None,
    theme_writer: _ThemeWriter | None = None,
    user_action: bool = False,
) -> dict[str, Any]:
    """Delete the three AI templates, reverting to Shopify's default content.

    Only ever deletes the 3 allowlisted AI files — never any other theme file
    (the writer enforces the allowlist). Allowed in every mode: it is the
    merchant's off-switch and only ever reduces the app's theme footprint.

    Best-effort: a Shopify error during delete is logged but never blocks
    clearing local state, so the merchant is never stuck half-published.
    """
    existing = store.get_publication(shop, db_path)
    if not existing or not existing.get("is_published"):
        return {"unpublished": False, "reason": "not_published"}

    writer = theme_writer or ShopifyThemeWriter(shop, access_token)
    theme_id = existing.get("theme_id")
    if theme_id:
        try:
            writer.delete_templates(theme_id, TEMPLATE_FILENAMES)
        except ShopifyThemeError as exc:
            logger.warning("Failed to delete AI templates for %s: %s", shop, exc)

    store.mark_unpublished(shop, db_path)
    store.log_theme_write(
        shop,
        action="unpublish",
        filenames=list(TEMPLATE_FILENAMES),
        theme_id=theme_id,
        user_action=user_action,
        db_path=db_path,
    )
    return {"unpublished": True}


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def should_regenerate(
    shop: str,
    *,
    now: datetime | None = None,
    db_path: Path | None = None,
) -> tuple[bool, str]:
    """Record a catalogue webhook tick and decide whether to republish.

    Returns ``(regenerate, reason)``. Regeneration is warranted only when the
    shop is already published and the previous tick is older than the debounce
    window — so catalogue bursts trigger at most one republish per window.
    """
    current = now or datetime.now(UTC)
    existing = store.get_publication(shop, db_path)
    previous_tick = store.record_webhook_tick(shop, current.isoformat(), db_path)

    if not existing or not existing.get("is_published"):
        return False, "not_published"

    last = _parse_iso(previous_tick)
    if last is not None and (current - last) < WEBHOOK_DEBOUNCE:
        return False, "debounced"

    return True, "regenerate"
