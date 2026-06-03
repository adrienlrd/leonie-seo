"""Merchant approval operations for learning-generated actions."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.apply.shopify_writer import ShopifyWriter
from app.content_actions.schema import ContentType
from app.learning.models import ApprovalStatus
from app.learning.risk import is_auto_apply_field_allowed
from app.learning.store import (
    get_settings,
    list_pending_approvals,
    update_approval_status,
)
from app.safe_apply.decisions import record_decision as record_content_decision
from app.safe_apply.writer_adapters import is_live_supported, live_write
from app.safety import require_shopify_write_allowed

_FIELD_TO_CONTENT_TYPE: dict[str, ContentType] = {
    "meta_title": ContentType.META_TITLE,
    "meta_description": ContentType.META_DESCRIPTION,
    "product_description": ContentType.PRODUCT_DESCRIPTION,
}


def _content_type_for_field(field: str) -> ContentType | None:
    return _FIELD_TO_CONTENT_TYPE.get(field)


def is_safe_approval(row: dict[str, Any], *, min_confidence: int = 0) -> bool:
    """Return True when the approval is safe for one-click application."""
    field = str(row.get("field") or "")
    risk_level = str(row.get("risk_level") or "")
    confidence = int(row.get("confidence_score") or 0)
    content_type = _content_type_for_field(field)
    return (
        str(row.get("status") or "") == "pending"
        and risk_level == "low"
        and confidence >= min_confidence
        and is_auto_apply_field_allowed(field)
        and content_type is not None
        and is_live_supported(content_type)
    )


def apply_approval(
    *,
    shop: str,
    approval_id: int,
    access_token: str,
    confirm_live_write: bool,
    db_path: Path | None = None,
) -> dict[str, Any]:
    """Apply one approved action through the existing Shopify writer."""
    rows = list_pending_approvals(shop, include_closed=True, limit=500, db_path=db_path)
    row = next((item for item in rows if int(item.get("id") or 0) == approval_id), None)
    if row is None:
        raise ValueError("Approval not found.")
    if not is_safe_approval(row):
        raise ValueError("Approval is not eligible for direct apply.")
    require_shopify_write_allowed(
        action="learning_approval_apply",
        dry_run=False,
        confirmed=confirm_live_write,
    )
    content_type = _content_type_for_field(str(row["field"]))
    if content_type is None:
        raise ValueError("Unsupported approval field.")
    writer = ShopifyWriter(shop, access_token)
    result = live_write(
        content_type,
        str(row["resource_id"]),
        str(row["proposed_value"] or ""),
        writer=writer,
    )
    if not result.get("applied"):
        update_approval_status(
            shop=shop,
            approval_id=approval_id,
            status=ApprovalStatus.FAILED,
            db_path=db_path,
        )
        return {"applied": False, "errors": result.get("errors") or ["write_failed"]}

    action_id = (row.get("explanation") or {}).get("content_action_id")
    if action_id:
        try:
            record_content_decision(shop, str(action_id), "accept", db_path=db_path)
        except ValueError:
            pass
    updated = update_approval_status(
        shop=shop,
        approval_id=approval_id,
        status=ApprovalStatus.APPLIED,
        db_path=db_path,
    )
    return {"applied": True, "approval": updated, "write": result}


def reject_approval(
    *,
    shop: str,
    approval_id: int,
    db_path: Path | None = None,
) -> dict[str, Any]:
    """Reject one pending approval."""
    updated = update_approval_status(
        shop=shop,
        approval_id=approval_id,
        status=ApprovalStatus.REJECTED,
        db_path=db_path,
    )
    if not updated:
        raise ValueError("Approval not found.")
    return updated


def edit_approval(
    *,
    shop: str,
    approval_id: int,
    proposed_value: str,
    db_path: Path | None = None,
) -> dict[str, Any]:
    """Edit the proposed value and keep it ready for merchant approval."""
    updated = update_approval_status(
        shop=shop,
        approval_id=approval_id,
        status=ApprovalStatus.EDITED,
        proposed_value=proposed_value,
        db_path=db_path,
    )
    if not updated:
        raise ValueError("Approval not found.")
    update_approval_status(
        shop=shop,
        approval_id=approval_id,
        status=ApprovalStatus.PENDING,
        db_path=db_path,
    )
    refreshed = list_pending_approvals(shop, include_closed=False, limit=500, db_path=db_path)
    return next(item for item in refreshed if int(item.get("id") or 0) == approval_id)


def bulk_approve_safe(
    *,
    shop: str,
    access_token: str,
    confirm_live_write: bool,
    db_path: Path | None = None,
) -> dict[str, Any]:
    """Apply all currently safe pending approvals."""
    settings = get_settings(shop, db_path=db_path)
    if not settings.allow_bulk_approval:
        return {"applied": 0, "skipped": 0, "errors": [{"reason": "bulk_approval_disabled"}]}
    rows = list_pending_approvals(shop, include_closed=False, limit=200, db_path=db_path)
    applied = 0
    skipped = 0
    errors: list[dict[str, Any]] = []
    for row in rows:
        if not is_safe_approval(row, min_confidence=settings.min_confidence_to_suggest):
            skipped += 1
            continue
        try:
            result = apply_approval(
                shop=shop,
                approval_id=int(row["id"]),
                access_token=access_token,
                confirm_live_write=confirm_live_write,
                db_path=db_path,
            )
            applied += 1 if result.get("applied") else 0
        except ValueError as exc:
            skipped += 1
            errors.append({"approval_id": row.get("id"), "error": str(exc)})
    return {"applied": applied, "skipped": skipped, "errors": errors}
