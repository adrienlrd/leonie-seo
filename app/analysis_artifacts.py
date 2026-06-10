"""Best-effort DB durability layer for analysis JSON artifacts.

Market analysis results, product identifications, merchant facts, and the
business profile are primarily persisted as JSON files under
``data/raw/{shop}/``. On Render Free the disk is ephemeral, so these files can
disappear on sleep/restart. This module mirrors each artifact into the
``analysis_artifacts`` table as a secondary copy, read only when the JSON file
is missing or unreadable.

The JSON file remains the source of truth for normal operation (it is read
and written directly by several other functions in `app/market_analysis/jobs.py`).
DB read/write failures (including a missing table on shops/tests that never
ran `init_db()`) must therefore never break the file-based flow — every
operation here swallows exceptions and degrades to a no-op.

Caveat: a few callers (`remove_products_from_analysis`, `patch_product_proposals`,
`replace_product_analysis`) edit `market_analysis_latest.json` directly without
going through `save_artifact`, so the DB copy of that artifact can lag behind
the file until the next full `save_latest_result`. This is acceptable because
`load_latest_result` always prefers the file when present; the DB copy is only
read as a fallback after a disk wipe, where it is still strictly better than
having nothing.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.db_adapter import get_conn

logger = logging.getLogger(__name__)


def save_artifact(shop: str, artifact_type: str, data: Any, *, db_path: Path | None = None) -> None:
    """Best-effort upsert of a JSON artifact for `shop`. Never raises."""
    try:
        with get_conn(db_path) as conn:
            conn.execute(
                """
                INSERT INTO analysis_artifacts (shop, artifact_type, data_json, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT (shop, artifact_type)
                DO UPDATE SET data_json = excluded.data_json, updated_at = excluded.updated_at
                """,
                (shop, artifact_type, json.dumps(data, ensure_ascii=False), datetime.now(UTC).isoformat()),
            )
    except Exception:
        logger.warning(
            "Failed to persist analysis artifact %s for %s to DB", artifact_type, shop, exc_info=True
        )


def load_artifact(shop: str, artifact_type: str, *, db_path: Path | None = None) -> Any | None:
    """Best-effort read of a JSON artifact for `shop`. Returns None on any failure."""
    try:
        with get_conn(db_path) as conn:
            row = conn.execute(
                "SELECT data_json FROM analysis_artifacts WHERE shop = ? AND artifact_type = ?",
                (shop, artifact_type),
            ).fetchone()
    except Exception:
        logger.warning(
            "Failed to read analysis artifact %s for %s from DB", artifact_type, shop, exc_info=True
        )
        return None
    if row is None:
        return None
    try:
        return json.loads(row["data_json"])
    except (TypeError, json.JSONDecodeError):
        return None
