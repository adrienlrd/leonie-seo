"""URL redirect endpoints — validate, dry-run preview, and supervised apply."""

from __future__ import annotations

import asyncio
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.api.deps import ShopContext, get_shop_context
from app.api.snapshot_store import load_snapshot_from_file_or_db
from app.apply.shopify_writer import ShopifyWriter
from app.safety import require_shopify_write_allowed
from scripts.apply.create_redirects import validate_redirects

router = APIRouter(tags=["redirects"])


def _get_existing_handles(snapshot: dict | None) -> set[str]:
    if not snapshot:
        return set()
    handles: set[str] = set()
    for p in snapshot.get("products", []):
        if h := p.get("handle"):
            handles.add(h)
    for c in snapshot.get("collections", []):
        if h := c.get("handle"):
            handles.add(h)
    return handles


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class RedirectItem(BaseModel):
    from_path: str
    to_path: str


class ValidateRequest(BaseModel):
    items: list[RedirectItem]


class ApplyRequest(BaseModel):
    items: list[RedirectItem]
    dry_run: bool = True
    confirm_live_write: bool = False


# ---------------------------------------------------------------------------
# POST — validate
# ---------------------------------------------------------------------------


@router.post("/api/shops/{shop}/audit/redirects/validate")
async def validate_redirect_list(
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
    body: ValidateRequest,
) -> dict:
    """Validate a list of redirects without applying them.

    Checks path format, self-redirects, duplicates, and handle conflicts.
    """
    if not body.items:
        raise HTTPException(status_code=422, detail="No items provided")

    snapshot = load_snapshot_from_file_or_db(ctx.shop, ctx.snapshot_path)
    existing_handles = _get_existing_handles(snapshot)

    rows = [{"from_path": r.from_path, "to_path": r.to_path} for r in body.items]
    valid_rows, warnings = validate_redirects(rows, existing_handles)

    return {
        "shop": ctx.shop,
        "total_submitted": len(body.items),
        "total_valid": len(valid_rows),
        "total_skipped": len(body.items) - len(valid_rows),
        "warnings": warnings,
        "valid": valid_rows,
    }


# ---------------------------------------------------------------------------
# POST — apply (dry_run=True by default)
# ---------------------------------------------------------------------------


@router.post("/api/shops/{shop}/audit/redirects/apply")
async def apply_redirects(
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
    body: ApplyRequest,
) -> dict:
    """Validate and apply URL redirects on Shopify.

    Always validates first. Dry-run by default — no Shopify writes.
    Set dry_run=false + confirm_live_write=true to create redirects.
    """
    if not body.items:
        raise HTTPException(status_code=422, detail="No items provided")

    require_shopify_write_allowed(
        action="apply_redirects",
        dry_run=body.dry_run,
        confirmed=body.confirm_live_write,
    )

    snapshot = load_snapshot_from_file_or_db(ctx.shop, ctx.snapshot_path)
    existing_handles = _get_existing_handles(snapshot)

    rows = [{"from_path": r.from_path, "to_path": r.to_path} for r in body.items]
    valid_rows, warnings = validate_redirects(rows, existing_handles)

    if not valid_rows:
        return {
            "dry_run": body.dry_run,
            "total_submitted": len(body.items),
            "total_valid": 0,
            "warnings": warnings,
            "results": [],
            "applied": 0,
            "errors": 0,
        }

    results = []

    if body.dry_run:
        for row in valid_rows:
            results.append(
                {
                    "from_path": row["from_path"],
                    "to_path": row["to_path"],
                    "status": "preview",
                    "detail": f"Would create redirect {row['from_path']} → {row['to_path']}",
                }
            )
        return {
            "dry_run": True,
            "total_submitted": len(body.items),
            "total_valid": len(valid_rows),
            "warnings": warnings,
            "results": results,
            "applied": 0,
            "errors": 0,
        }

    writer = ShopifyWriter(ctx.shop, ctx.access_token)

    for row in valid_rows:
        from_path = row["from_path"]
        to_path = row["to_path"]
        result = await asyncio.to_thread(
            lambda f=from_path, t=to_path: writer.apply_redirect(f, t)
        )
        results.append(
            {
                "from_path": from_path,
                "to_path": to_path,
                "status": "applied" if result.applied else "error",
                "detail": result.error,
            }
        )

    applied = sum(1 for r in results if r["status"] == "applied")
    errors = sum(1 for r in results if r["status"] == "error")

    return {
        "dry_run": False,
        "total_submitted": len(body.items),
        "total_valid": len(valid_rows),
        "warnings": warnings,
        "results": results,
        "applied": applied,
        "errors": errors,
    }
