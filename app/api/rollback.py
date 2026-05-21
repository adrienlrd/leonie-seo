"""Rollback API — history of Shopify writes and per-change revert."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.api.deps import ShopContext, get_shop_context
from app.apply.shopify_writer import ShopifyWriter
from app.db_adapter import DB_PATH, get_conn
from app.safety import require_shopify_write_allowed

_ROLLBACK_TTL_DAYS = 90

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["rollback"])

# Fields that can be automatically reverted via ShopifyWriter
_REVERTIBLE_FIELDS = {"seo.title", "seo.description"}


def log_seo_change(
    shop: str,
    resource_type: str,
    resource_id: str,
    field: str,
    old_value: str | None,
    new_value: str,
    *,
    db_path: Path | None = None,
) -> None:
    """Persist a successful Shopify write to seo_changes for audit and rollback.

    Args:
        shop: Shopify shop domain.
        resource_type: 'product', 'collection', 'image', 'redirect'.
        resource_id: Shopify GID of the mutated resource.
        field: Logical field name (e.g. 'seo.title', 'image.alt_text').
        old_value: Value before the mutation, or None if unknown.
        new_value: Value after the mutation.
        db_path: Override DB path (tests only).
    """
    path = db_path if db_path is not None else DB_PATH
    now = datetime.now(UTC).isoformat()
    with get_conn(path) as conn:
        conn.execute(
            """INSERT INTO seo_changes
               (shop, applied_at, resource_type, resource_id, field, old_value, new_value, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, 'applied')""",
            (shop, now, resource_type, resource_id, field, old_value, new_value),
        )


@router.get("/shops/{shop}/rollback/history")
async def get_rollback_history(
    shop: str,
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
    limit: int = 50,
    offset: int = 0,
    resource_type: str | None = None,
) -> dict:
    """Return paginated write history for the shop.

    Args:
        shop: Shopify shop domain.
        limit: Max number of rows to return (default 50).
        offset: Pagination offset (default 0).
        resource_type: Optional filter ('product', 'collection', 'image', 'redirect').
    """
    base_sql = """
        SELECT id, applied_at, resource_type, resource_id, field,
               old_value, new_value, status
        FROM seo_changes
        WHERE shop = ?
    """
    params: list = [ctx.shop]

    if resource_type:
        base_sql += " AND resource_type = ?"
        params.append(resource_type)

    count_sql = base_sql.replace(
        "SELECT id, applied_at, resource_type, resource_id, field,\n               old_value, new_value, status",
        "SELECT COUNT(*)",
    )
    base_sql += " ORDER BY applied_at DESC LIMIT ? OFFSET ?"

    with get_conn(DB_PATH) as conn:
        total = (conn.execute(count_sql, params).fetchone() or {}).get("COUNT(*)", 0)
        rows = conn.execute(base_sql, params + [limit, offset]).fetchall()

    changes = []
    for row in rows:
        field = row["field"]
        status = row["status"]
        old_val = row["old_value"]
        revertible = status == "applied" and old_val is not None and field in _REVERTIBLE_FIELDS
        changes.append(
            {
                "id": row["id"],
                "applied_at": row["applied_at"],
                "resource_type": row["resource_type"],
                "resource_id": row["resource_id"],
                "field": field,
                "old_value": old_val,
                "new_value": row["new_value"],
                "status": status,
                "revertible": revertible,
            }
        )

    return {
        "shop": ctx.shop,
        "total": total,
        "limit": limit,
        "offset": offset,
        "changes": changes,
    }


class RevertRequest(BaseModel):
    dry_run: bool = True
    confirm_live_write: bool = False
    confirm_stale_revert: bool = False


@router.post("/shops/{shop}/rollback/{change_id}/revert")
async def revert_change(
    shop: str,
    change_id: int,
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
    body: RevertRequest,
) -> dict:
    """Revert a single seo_changes entry to its previous value.

    Only fields in _REVERTIBLE_FIELDS ('seo.title', 'seo.description') are supported.
    Dry-run by default — set dry_run=false and confirm_live_write=true to write.

    Args:
        shop: Shopify shop domain.
        change_id: seo_changes row ID to revert.
    """
    with get_conn(DB_PATH) as conn:
        row = conn.execute(
            """SELECT id, applied_at, resource_type, resource_id, field, old_value, status
               FROM seo_changes WHERE id = ? AND shop = ?""",
            (change_id, ctx.shop),
        ).fetchone()

    if row is None:
        raise HTTPException(status_code=404, detail=f"Change {change_id} not found.")

    field: str = row["field"]
    old_value: str | None = row["old_value"]
    resource_id: str = row["resource_id"]
    status: str = row["status"]

    applied_at_str: str = row.get("applied_at", "") or ""
    try:
        applied_dt = datetime.fromisoformat(applied_at_str)
        age_days = (datetime.now(UTC) - applied_dt).days
    except (ValueError, TypeError):
        age_days = 0

    if age_days > _ROLLBACK_TTL_DAYS and not body.dry_run and not body.confirm_stale_revert:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Change {change_id} is {age_days} days old "
                f"(TTL: {_ROLLBACK_TTL_DAYS} days). "
                "Add confirm_stale_revert=true to confirm revert of stale change."
            ),
        )

    if status != "applied":
        raise HTTPException(
            status_code=422,
            detail=f"Cannot revert: current status is '{status}'.",
        )
    if old_value is None:
        raise HTTPException(
            status_code=422,
            detail="Cannot revert: no previous value was recorded for this change.",
        )
    if field not in _REVERTIBLE_FIELDS:
        raise HTTPException(
            status_code=422,
            detail=f"Revert not supported for field '{field}'.",
        )

    require_shopify_write_allowed(
        action="rollback",
        dry_run=body.dry_run,
        confirmed=body.confirm_live_write,
    )

    if body.dry_run:
        result_preview: dict = {
            "change_id": change_id,
            "dry_run": True,
            "status": "preview",
            "detail": f"Would restore {field} to {old_value!r} on {resource_id}",
            "age_days": age_days,
        }
        if age_days > _ROLLBACK_TTL_DAYS:
            result_preview["stale_warning"] = (
                f"Change is {age_days} days old (> {_ROLLBACK_TTL_DAYS}-day TTL). "
                "Add confirm_stale_revert=true when applying."
            )
        return result_preview

    writer = ShopifyWriter(ctx.shop, ctx.access_token)

    if field == "seo.title":
        result = await asyncio.to_thread(
            lambda: writer.apply_product_seo(resource_id, title=old_value, description=None)
        )
    else:
        result = await asyncio.to_thread(
            lambda: writer.apply_product_seo(resource_id, title=None, description=old_value)
        )

    if not result.applied:
        return {
            "change_id": change_id,
            "dry_run": False,
            "status": "error",
            "detail": result.error,
        }

    with get_conn(DB_PATH) as conn:
        conn.execute(
            "UPDATE seo_changes SET status = 'reverted' WHERE id = ?",
            (change_id,),
        )

    return {"change_id": change_id, "dry_run": False, "status": "reverted"}
