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
    product_id: str,
    generated_title: str | None,
    generated_description: str | None,
    db_path: Path | None,
) -> None:
    """Record a successful apply in seo_changes for rollback support."""
    path = db_path if db_path is not None else DB_PATH
    now = datetime.now(UTC).isoformat()
    with get_conn(path) as conn:
        for field_name, new_value in [
            ("seo.title", generated_title),
            ("seo.description", generated_description),
        ]:
            if new_value:
                conn.execute(
                    """INSERT INTO seo_changes
                       (applied_at, resource_type, resource_id, field, old_value, new_value, status)
                       VALUES (?, 'product', ?, ?, NULL, ?, 'applied')""",
                    (now, product_id, field_name, new_value),
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
        for row in suggestions:
            report.details.append({
                "suggestion_id": row["id"] if isinstance(row, dict) else row[0],
                "product_id": row["product_id"] if isinstance(row, dict) else row[2],
                "applied": False,
                "dry_run": True,
            })
        report.skipped = len(suggestions)
        return report

    token_record = get_token(shop, db_path)
    if token_record is None:
        logger.error("No OAuth token found for shop %s — cannot apply", shop)
        report.skipped = len(suggestions)
        report.details = [
            {"suggestion_id": None, "product_id": None, "applied": False,
             "error": "no OAuth token for shop"}
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
            _log_applied(product_id, title, description, db_path)
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
