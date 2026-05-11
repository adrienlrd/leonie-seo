"""Persistence layer for LLM-generated meta suggestions."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from app.db_adapter import DB_PATH, get_conn
from app.llm.batch import MetaResult

_VALID_STATUSES = {"pending", "approved", "rejected"}


def save_results(
    results: list[MetaResult], *, shop: str, job_id: str, db_path: Path | None = None
) -> None:
    """Persist a batch of MetaResult rows into meta_suggestions.

    Args:
        results: Output from generate_meta_for_products().
        shop: Shopify shop domain.
        job_id: ID of the parent job (for tracing).
        db_path: Override DB path (tests only).
    """
    path = db_path if db_path is not None else DB_PATH
    now = datetime.now(UTC).isoformat()
    with get_conn(path) as conn:
        for r in results:
            conn.execute(
                """INSERT INTO meta_suggestions
                   (shop, product_id, product_title, generated_title, generated_description,
                    provider, status, error, job_id, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    shop,
                    r.product_id,
                    r.product_title,
                    r.generated_title or None,
                    r.generated_description or None,
                    r.provider or None,
                    "pending" if r.success else "error",
                    r.error,
                    job_id,
                    now,
                ),
            )


def list_suggestions(
    shop: str,
    *,
    status: str | None = None,
    limit: int = 100,
    db_path: Path | None = None,
) -> list[dict]:
    """Return meta suggestions for a shop, newest first.

    Args:
        shop: Shopify shop domain.
        status: Filter by status (pending / approved / rejected / error). None = all.
        limit: Maximum rows returned.
        db_path: Override DB path (tests only).
    """
    path = db_path if db_path is not None else DB_PATH
    with get_conn(path) as conn:
        if status:
            rows = conn.execute(
                "SELECT * FROM meta_suggestions WHERE shop = ? AND status = ? "
                "ORDER BY created_at DESC LIMIT ?",
                (shop, status, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM meta_suggestions WHERE shop = ? ORDER BY created_at DESC LIMIT ?",
                (shop, limit),
            ).fetchall()
    return rows


def update_status(
    suggestion_id: int,
    status: str,
    *,
    db_path: Path | None = None,
) -> None:
    """Set the review status of a suggestion (pending / approved / rejected).

    Args:
        suggestion_id: Row primary key.
        status: Target status.
        db_path: Override DB path (tests only).

    Raises:
        ValueError: If status is not a recognised value.
    """
    if status not in _VALID_STATUSES:
        raise ValueError(f"Invalid status '{status}'. Must be one of {_VALID_STATUSES}")
    path = db_path if db_path is not None else DB_PATH
    with get_conn(path) as conn:
        conn.execute(
            "UPDATE meta_suggestions SET status = ? WHERE id = ?",
            (status, suggestion_id),
        )
