"""Tests for learning approval safety filters."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from app.db import init_db
from app.db_adapter import get_conn
from app.learning.approvals import (
    apply_approval,
    bulk_approve_safe,
    edit_approval,
    is_safe_approval,
    reject_approval,
)
from app.learning.store import create_pending_approval, update_settings

SHOP = "store.myshopify.com"


def _approval(
    db: Path,
    *,
    field: str = "meta_title",
    risk_level: str = "low",
    confidence: int = 90,
    resource_id: str = "gid://shopify/Product/1",
) -> int:
    return create_pending_approval(
        shop=SHOP,
        resource_type="product",
        resource_id=resource_id,
        action_type=field,
        field=field,
        old_value="Old",
        proposed_value="New",
        confidence_score=confidence,
        risk_level=risk_level,
        expected_impact={"summary": "expected"},
        explanation={"content_action_id": "action-1"},
        db_path=db,
    )


def test_bulk_approval_filter_accepts_only_safe_actions() -> None:
    safe = {
        "status": "pending",
        "field": "meta_title",
        "risk_level": "low",
        "confidence_score": 82,
    }
    risky = {
        "status": "pending",
        "field": "blog",
        "risk_level": "high",
        "confidence_score": 95,
    }

    assert is_safe_approval(safe, min_confidence=80) is True
    assert is_safe_approval(risky, min_confidence=80) is False


def test_apply_approval_uses_mocked_writer_and_records_trace(tmp_path: Path) -> None:
    db = tmp_path / "history.db"
    init_db(db)
    approval_id = _approval(db)

    with (
        patch("app.learning.approvals.ShopifyWriter") as writer_cls,
        patch(
            "app.learning.approvals.live_write", return_value={"applied": True, "old_value": "Old"}
        ),
        patch("app.learning.approvals.record_content_decision"),
    ):
        result = apply_approval(
            shop=SHOP,
            approval_id=approval_id,
            access_token="token",
            confirm_live_write=True,
            db_path=db,
        )

    assert result["applied"] is True
    writer_cls.assert_called_once_with(SHOP, "token")
    with get_conn(db) as conn:
        approval = conn.execute(
            "SELECT status FROM learning_pending_approvals WHERE id = ?",
            (approval_id,),
        ).fetchone()
        trace = conn.execute("SELECT * FROM seo_changes WHERE shop = ?", (SHOP,)).fetchone()
    assert approval["status"] == "applied"
    assert trace["new_value"] == "New"


def test_apply_approval_requires_confirmation(tmp_path: Path) -> None:
    db = tmp_path / "history.db"
    init_db(db)
    approval_id = _approval(db)

    with pytest.raises(Exception):
        apply_approval(
            shop=SHOP,
            approval_id=approval_id,
            access_token="token",
            confirm_live_write=False,
            db_path=db,
        )


def test_reject_approval_sets_rejected_status(tmp_path: Path) -> None:
    db = tmp_path / "history.db"
    init_db(db)
    approval_id = _approval(db)

    result = reject_approval(shop=SHOP, approval_id=approval_id, db_path=db)

    assert result["status"] == "rejected"


def test_edit_approval_changes_value_and_keeps_edited_status(tmp_path: Path) -> None:
    db = tmp_path / "history.db"
    init_db(db)
    approval_id = _approval(db)

    result = edit_approval(
        shop=SHOP,
        approval_id=approval_id,
        proposed_value="Edited title",
        db_path=db,
    )

    assert result["status"] == "edited"
    assert result["proposed_value"] == "Edited title"


def test_bulk_approve_safe_applies_only_safe_actions(tmp_path: Path) -> None:
    db = tmp_path / "history.db"
    init_db(db)
    _approval(db, resource_id="safe")
    _approval(db, resource_id="risky", risk_level="medium")
    _approval(db, resource_id="blog", field="blog", risk_level="high")

    with (
        patch("app.learning.approvals.ShopifyWriter"),
        patch(
            "app.learning.approvals.live_write", return_value={"applied": True, "old_value": "Old"}
        ) as write,
        patch("app.learning.approvals.record_content_decision"),
    ):
        result = bulk_approve_safe(
            shop=SHOP,
            access_token="token",
            confirm_live_write=True,
            db_path=db,
        )

    assert result["applied"] == 1
    assert result["skipped"] == 2
    assert write.call_count == 1


def test_bulk_approve_safe_respects_disabled_setting(tmp_path: Path) -> None:
    db = tmp_path / "history.db"
    init_db(db)
    update_settings(SHOP, {"allow_bulk_approval": False}, db_path=db)
    _approval(db)

    result = bulk_approve_safe(
        shop=SHOP,
        access_token="token",
        confirm_live_write=True,
        db_path=db,
    )

    assert result["applied"] == 0
    assert result["errors"][0]["reason"] == "bulk_approval_disabled"


def test_approval_not_found_returns_clean_error(tmp_path: Path) -> None:
    db = tmp_path / "history.db"
    init_db(db)

    with pytest.raises(ValueError, match="Approval not found"):
        reject_approval(shop=SHOP, approval_id=999, db_path=db)


def test_applied_approval_is_not_reapplied(tmp_path: Path) -> None:
    db = tmp_path / "history.db"
    init_db(db)
    approval_id = _approval(db)
    with (
        patch("app.learning.approvals.ShopifyWriter"),
        patch(
            "app.learning.approvals.live_write", return_value={"applied": True, "old_value": "Old"}
        ),
        patch("app.learning.approvals.record_content_decision"),
    ):
        apply_approval(
            shop=SHOP,
            approval_id=approval_id,
            access_token="token",
            confirm_live_write=True,
            db_path=db,
        )

    with pytest.raises(ValueError, match="not eligible"):
        apply_approval(
            shop=SHOP,
            approval_id=approval_id,
            access_token="token",
            confirm_live_write=True,
            db_path=db,
        )
