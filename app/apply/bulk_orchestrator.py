"""Bulk apply orchestrator — pushes approved meta suggestions to Shopify."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from app.apply.shopify_writer import ShopifyWriter
from app.db_adapter import DB_PATH, get_conn
from app.llm.meta_store import batch_update_status, list_suggestions
from app.oauth.token_store import get_token

logger = logging.getLogger(__name__)

_MAX_PER_RUN_DEFAULT = 50


@dataclass
class BulkApplyReport:
    """Summary of a bulk apply run.

    Attributes:
        shop: Shopify shop domain.
        dry_run: True if no mutations were actually sent to Shopify.
        applied: Number of suggestions successfully pushed.
        skipped: Number skipped (no token, no content, etc.).
        errors: Number of Shopify API failures.
        details: Per-suggestion outcome dicts (product_id, applied, error).
        run_at: ISO 8601 timestamp of when the run completed.
    """

    shop: str
    dry_run: bool
    applied: int = 0
    skipped: int = 0
    errors: int = 0
    details: list[dict] = field(default_factory=list)
    run_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())


def _log_applied(
    shop: str,
    product_id: str,
    generated_title: str | None,
    generated_description: str | None,
    db_path: Path | None,
    *,
    old_title: str | None = None,
    old_description: str | None = None,
) -> None:
    """Record a successful apply in seo_changes for rollback support.

    Args:
        shop: Shopify shop domain — required for multi-tenant isolation.
        product_id: Shopify product GID.
        generated_title: New SEO title (or None to skip).
        generated_description: New SEO description (or None to skip).
        db_path: Override DB path (tests only).
        old_title: Previous SEO title captured by the writer before the mutation.
                   When provided, persisted so the rollback CLI can restore it.
        old_description: Previous SEO description captured pre-mutation.
    """
    path = db_path if db_path is not None else DB_PATH
    now = datetime.now(UTC).isoformat()
    pairs = [
        ("seo.title", generated_title, old_title),
        ("seo.description", generated_description, old_description),
    ]
    with get_conn(path) as conn:
        for field_name, new_value, old_value in pairs:
            if new_value:
                conn.execute(
                    """INSERT INTO seo_changes
                       (shop, applied_at, resource_type, resource_id, field,
                        old_value, new_value, status)
                       VALUES (?, ?, 'product', ?, ?, ?, ?, 'applied')""",
                    (shop, now, product_id, field_name, old_value, new_value),
                )


def apply_approved_meta(
    shop: str,
    *,
    dry_run: bool = True,
    max_per_run: int = _MAX_PER_RUN_DEFAULT,
    delay: float = 0.5,
    db_path: Path | None = None,
) -> BulkApplyReport:
    """Apply all approved meta suggestions for a shop to Shopify.

    Loads approved suggestions from the DB, applies each one sequentially
    (to stay within Shopify rate limits), then marks them as 'applied'.
    Failures are marked as 'error' and reported in the result.

    Args:
        shop: Shopify shop domain.
        dry_run: If True (default), simulate the run without calling Shopify.
                 The report shows what would be applied.
        max_per_run: Maximum suggestions to process per call (prevents timeouts).
        delay: Seconds between Shopify mutations (rate-limit guard).
        db_path: Override DB path (tests only).

    Returns:
        BulkApplyReport with per-suggestion outcomes.
    """
    report = BulkApplyReport(shop=shop, dry_run=dry_run)

    suggestions = list_suggestions(shop, status="approved", limit=max_per_run, db_path=db_path)
    if not suggestions:
        logger.info("No approved suggestions for %s", shop)
        return report

    if dry_run:
        token_record = get_token(shop, db_path)
        writer = (
            ShopifyWriter(shop, token_record["access_token"], delay=0) if token_record else None
        )
        for row in suggestions:
            product_id = row["product_id"] if isinstance(row, dict) else row[2]
            product_title = row.get("product_title", "") if isinstance(row, dict) else ""
            current_title = product_title
            current_description = ""
            current_seo_read = False
            if writer:
                seo_title, seo_description = writer.read_product_seo(product_id)
                current_title = seo_title or ""
                current_description = seo_description or ""
                current_seo_read = True
            report.details.append(
                {
                    "suggestion_id": row["id"] if isinstance(row, dict) else row[0],
                    "product_id": product_id,
                    "product_title": product_title,
                    "current_title": current_title,
                    "current_description": current_description,
                    "current_seo_read": current_seo_read,
                    "generated_title": (
                        row.get("generated_title", "") if isinstance(row, dict) else ""
                    ),
                    "generated_description": (
                        row.get("generated_description", "") if isinstance(row, dict) else ""
                    ),
                    "applied": False,
                    "dry_run": True,
                    "action": "would_apply",
                    "note": "preview only - no Shopify write was performed",
                }
            )
        report.skipped = len(suggestions)
        return report

    token_record = get_token(shop, db_path)
    if token_record is None:
        logger.error("No OAuth token found for shop %s — cannot apply", shop)
        report.skipped = len(suggestions)
        report.details = [
            {
                "suggestion_id": None,
                "product_id": None,
                "applied": False,
                "error": "no OAuth token for shop",
            }
        ]
        return report

    writer = ShopifyWriter(shop, token_record["access_token"], delay=delay)
    applied_ids: list[int] = []
    error_ids: list[int] = []

    for row in suggestions:
        # Support both dict rows (SQLite dict_factory) and sqlite3.Row
        if isinstance(row, dict):
            suggestion_id = row["id"]
            product_id = row["product_id"]
            title = row.get("generated_title")
            description = row.get("generated_description")
        else:
            cols = [d[0] for d in row.description] if hasattr(row, "description") else []
            row_dict = dict(zip(cols, row)) if cols else {}
            suggestion_id = row_dict.get("id")
            product_id = row_dict.get("product_id", "")
            title = row_dict.get("generated_title")
            description = row_dict.get("generated_description")

        result = writer.apply_product_seo(product_id, title, description)

        detail: dict = {
            "suggestion_id": suggestion_id,
            "product_id": product_id,
            "applied": result.applied,
        }
        if result.error:
            detail["error"] = result.error

        report.details.append(detail)

        if result.applied:
            _log_applied(
                shop,
                product_id,
                title,
                description,
                db_path,
                old_title=result.old_title,
                old_description=result.old_description,
            )
            applied_ids.append(suggestion_id)
            report.applied += 1
        else:
            error_ids.append(suggestion_id)
            report.errors += 1
            logger.warning("Failed to apply suggestion %s: %s", suggestion_id, result.error)

    if applied_ids:
        batch_update_status(applied_ids, "applied", db_path=db_path)
    if error_ids:
        batch_update_status(error_ids, "error", db_path=db_path)

    return report
