"""Safe Apply API — unified human review, dry-run, live apply and rollback."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.api.deps import ShopContext, get_shop_context
from app.api.plans import get_features
from app.apply.shopify_writer import ShopifyWriter
from app.content_actions.runner import _load_action, _update_action_status
from app.content_actions.schema import ContentStatus
from app.db_adapter import DB_PATH, get_conn
from app.safe_apply.decisions import get_decision_history, record_decision
from app.safe_apply.diff import build_diff
from app.safe_apply.rollback_adapters import EXTENDED_REVERTIBLE_FIELDS, revert_field
from app.safe_apply.writer_adapters import dry_run_preview, live_write
from app.safety import require_shopify_write_allowed

router = APIRouter(prefix="/api", tags=["safe_apply"])


# ── Request / response models ─────────────────────────────────────────────────


class DecisionRequest(BaseModel):
    action_id: str
    decision: str
    edited_text: str | None = None
    rejected_reason: str | None = None


class DryRunRequest(BaseModel):
    action_id: str


class LiveApplyRequest(BaseModel):
    action_id: str
    confirm_live_write: bool = False


class RevertRequest(BaseModel):
    dry_run: bool = True
    confirm_live_write: bool = False


# ── Helpers ───────────────────────────────────────────────────────────────────


def _log_seo_change(
    shop: str,
    action_id: str,
    resource_id: str,
    content_type_value: str,
    field: str,
    old_value: str | None,
    new_value: str,
) -> None:
    now = datetime.now(UTC).isoformat()
    try:
        with get_conn(DB_PATH) as conn:
            conn.execute(
                """INSERT INTO seo_changes
                   (shop, applied_at, resource_type, resource_id, field, old_value, new_value, status)
                   VALUES (?, ?, 'product', ?, ?, ?, ?, 'applied')""",
                (shop, now, resource_id, field, old_value, new_value),
            )
    except Exception:
        pass


def _create_apply_event(
    shop: str,
    action_id: str,
    resource_id: str,
    content_type_value: str,
) -> None:
    from app.geo.ledger import create_geo_event  # noqa: PLC0415

    try:
        create_geo_event(
            shop=shop,
            event_type="content_applied",
            resource_type="product",
            resource_id=resource_id,
            resource_title=resource_id,
            action_type=content_type_value,
            before_snapshot={},
            metrics_before={},
            estimated_impact={},
            status="applied",
            source="safe_apply",
            notes=f"action_id={action_id}",
        )
    except Exception:
        pass


# ── Routes ────────────────────────────────────────────────────────────────────


@router.get("/shops/{shop}/safe-apply/diff")
async def get_diff(
    shop: str,
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
    action_id: str = Query(...),
) -> dict[str, Any]:
    """Return the Diff preview object for a content action.

    Args:
        action_id: ID of the content action to preview.
    """
    diff = build_diff(action_id, ctx.shop)
    if diff is None:
        raise HTTPException(status_code=404, detail=f"Action {action_id!r} not found.")
    diff["decision_history"] = get_decision_history(ctx.shop, action_id)
    return diff


@router.post("/shops/{shop}/safe-apply/decision")
async def make_decision(
    shop: str,
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
    body: DecisionRequest,
) -> dict[str, Any]:
    """Record a human review decision: accept, edit, reject, or retry.

    Accept is blocked if the action has constraint violations (forbidden_promise,
    do_not_say, length_out_of_bounds, language_mismatch). Retry is capped at 3.
    """
    try:
        return record_decision(
            ctx.shop,
            body.action_id,
            body.decision,
            edited_text=body.edited_text,
            rejected_reason=body.rejected_reason,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/shops/{shop}/safe-apply/dry-run")
async def dry_run_action(
    shop: str,
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
    body: DryRunRequest,
) -> dict[str, Any]:
    """Simulate applying a content action to Shopify without writing.

    The action must be in status=approved before dry-run is permitted.
    Returns a preview of which fields would change.
    """
    result = _load_action(ctx.shop, body.action_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Action {body.action_id!r} not found.")

    if result.status not in {ContentStatus.APPROVED, ContentStatus.EXPORTED}:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Dry-run requires status=approved (current: {result.status.value}). "
                "Accept the action first."
            ),
        )

    preview = dry_run_preview(result.content_type, result.resource_id, result.output.primary_text)
    preview["action_id"] = body.action_id
    preview["content_type"] = result.content_type.value
    return preview


@router.post("/shops/{shop}/safe-apply/live")
async def live_apply(
    shop: str,
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
    body: LiveApplyRequest,
    plan: str = Query(default="free", pattern="^(free|pro|agency)$"),
) -> dict[str, Any]:
    """Apply an approved content action to Shopify.

    Guards:
    - Plan must be Pro or Agency (Free can only export).
    - Pilot-safe mode blocks all live writes.
    - confirm_live_write=true required.
    - Action must be status=approved.
    """
    features = get_features(plan)
    if not features.can_apply:
        raise HTTPException(
            status_code=403,
            detail="Live apply requires Pro or Agency plan. Use export for Free plan.",
        )

    require_shopify_write_allowed(
        action="safe_apply",
        dry_run=False,
        confirmed=body.confirm_live_write,
    )

    result = _load_action(ctx.shop, body.action_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Action {body.action_id!r} not found.")

    if result.status != ContentStatus.APPROVED:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Live apply requires status=approved (current: {result.status.value}). "
                "Accept the action first, then run dry-run."
            ),
        )

    writer = ShopifyWriter(ctx.shop, ctx.access_token)
    write_result = await asyncio.to_thread(
        live_write,
        result.content_type,
        result.resource_id,
        result.output.primary_text,
        writer=writer,
    )

    if not write_result["applied"]:
        error_msg = write_result["errors"][0] if write_result["errors"] else "Write failed."
        raise HTTPException(status_code=502, detail=f"Shopify write failed: {error_msg}")

    _log_seo_change(
        ctx.shop,
        body.action_id,
        result.resource_id,
        result.content_type.value,
        write_result["field"],
        write_result.get("old_value"),
        result.output.primary_text,
    )

    _create_apply_event(
        ctx.shop,
        body.action_id,
        result.resource_id,
        result.content_type.value,
    )

    _update_action_status(ctx.shop, body.action_id, ContentStatus.APPLIED)

    return {
        "action_id": body.action_id,
        "applied": True,
        "field": write_result["field"],
        "content_type": result.content_type.value,
        "resource_id": result.resource_id,
        "applied_at": datetime.now(UTC).isoformat(),
        "message": (
            "Modification appliquée. Premier signal de mesure attendu sous 7 jours."
        ),
    }


@router.post("/shops/{shop}/safe-apply/revert")
async def revert_action(
    shop: str,
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
    change_id: int = Query(...),
    body: RevertRequest = ...,
) -> dict[str, Any]:
    """Revert a seo_changes entry to its previous value.

    Supports fields: seo.title, seo.description, descriptionHtml.
    Dry-run by default — set dry_run=false and confirm_live_write=true to revert.
    """
    with get_conn(DB_PATH) as conn:
        row = conn.execute(
            """SELECT id, resource_type, resource_id, field, old_value, status
               FROM seo_changes WHERE id = ? AND shop = ?""",
            (change_id, ctx.shop),
        ).fetchone()

    if row is None:
        raise HTTPException(status_code=404, detail=f"Change {change_id} not found.")

    field: str = row["field"]
    old_value: str | None = row["old_value"]
    resource_id: str = row["resource_id"]
    status: str = row["status"]

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
    if field not in EXTENDED_REVERTIBLE_FIELDS:
        raise HTTPException(
            status_code=422,
            detail=f"Revert not supported for field '{field}' in V1.",
        )

    require_shopify_write_allowed(
        action="revert",
        dry_run=body.dry_run,
        confirmed=body.confirm_live_write,
    )

    if body.dry_run:
        return {
            "change_id": change_id,
            "dry_run": True,
            "status": "preview",
            "detail": f"Would restore {field!r} to {(old_value or '')[:60]} on {resource_id}",
        }

    writer = ShopifyWriter(ctx.shop, ctx.access_token)
    revert_result = await asyncio.to_thread(
        revert_field,
        resource_id,
        field,
        old_value,
        writer=writer,
    )

    if not revert_result["applied"]:
        error_msg = revert_result["errors"][0] if revert_result["errors"] else "Revert failed."
        raise HTTPException(status_code=502, detail=f"Shopify revert failed: {error_msg}")

    with get_conn(DB_PATH) as conn:
        conn.execute(
            "UPDATE seo_changes SET status = 'reverted' WHERE id = ?",
            (change_id,),
        )

    return {
        "change_id": change_id,
        "dry_run": False,
        "status": "reverted",
        "field": field,
        "resource_id": resource_id,
    }
