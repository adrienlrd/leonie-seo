"""Snapshot loading helpers shared by app API routes."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.db_adapter import DB_PATH, get_conn


def load_latest_snapshot_from_db(shop: str, db_path: Path | None = None) -> dict[str, Any] | None:
    """Return the latest product/collection snapshot for a shop from the DB."""
    path = db_path if db_path is not None else DB_PATH
    with get_conn(path) as conn:
        latest = conn.execute(
            """
            SELECT snapshot_date
            FROM snapshots
            WHERE shop = ?
            ORDER BY snapshot_date DESC
            LIMIT 1
            """,
            (shop,),
        ).fetchone()
        if latest is None:
            return None

        rows = conn.execute(
            """
            SELECT resource_type, data_json
            FROM snapshots
            WHERE shop = ? AND snapshot_date = ?
            ORDER BY resource_type, resource_id
            """,
            (shop, latest["snapshot_date"]),
        ).fetchall()

    products: list[dict[str, Any]] = []
    collections: list[dict[str, Any]] = []
    for row in rows:
        try:
            resource = json.loads(row["data_json"])
        except (json.JSONDecodeError, TypeError):
            continue
        if row["resource_type"] == "product":
            products.append(resource)
        elif row["resource_type"] == "collection":
            collections.append(resource)

    return {
        "snapshot_date": latest["snapshot_date"],
        "products": products,
        "collections": collections,
    }


def load_snapshot_from_file_or_db(
    shop: str,
    snapshot_path: Path,
    db_path: Path | None = None,
) -> dict[str, Any] | None:
    """Load a tenant snapshot from disk, falling back to the DB."""
    if snapshot_path.exists():
        try:
            return json.loads(snapshot_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            raise RuntimeError("Snapshot file is corrupted") from exc
    return load_latest_snapshot_from_db(shop, db_path=db_path)
