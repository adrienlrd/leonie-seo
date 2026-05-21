"""Tests for the safe apply decision recording module."""

from __future__ import annotations

import pytest

from app.content_actions.schema import (
    ConstraintsCheck,
    ContentActionResult,
    ContentOutput,
    ContentStatus,
    ContentType,
    QualityResult,
)
from app.safe_apply.decisions import record_decision


def _persist_result(result: ContentActionResult, shop: str, db_path) -> None:
    from app.content_actions.runner import _persist_action  # noqa: PLC0415
    from app.db import init_db  # noqa: PLC0415

    init_db(db_path)
    _persist_action(shop, result, db_path=db_path)


def _make_result(
    action_id: str = "act-1",
    violations: list[str] | None = None,
    length_ok: bool = True,
) -> ContentActionResult:
    return ContentActionResult(
        action_id=action_id,
        content_type=ContentType.META_TITLE,
        resource_id="gid://shopify/Product/1",
        generated_at="2026-05-21T10:00:00+00:00",
        output=ContentOutput(primary_text="Harnais chien nylon réglable"),
        constraints_check=ConstraintsCheck(
            length_ok=length_ok,
            forbidden_promise_violations=violations or [],
        ),
        quality=QualityResult(score=75, label="bon"),
        status=ContentStatus.DRAFT,
    )


def test_accept_approved_when_no_violations(tmp_path):
    result = _make_result()
    _persist_result(result, "shop.myshopify.com", tmp_path / "db.sqlite")
    decision = record_decision(
        "shop.myshopify.com", "act-1", "accept", db_path=tmp_path / "db.sqlite"
    )
    assert decision["new_status"] == ContentStatus.APPROVED.value


def test_accept_blocked_when_forbidden_promise(tmp_path):
    result = _make_result(violations=["guérit"])
    _persist_result(result, "shop.myshopify.com", tmp_path / "db.sqlite")
    with pytest.raises(ValueError, match="Accept blocked"):
        record_decision(
            "shop.myshopify.com", "act-1", "accept", db_path=tmp_path / "db.sqlite"
        )


def test_accept_blocked_when_length_out_of_bounds(tmp_path):
    result = _make_result(length_ok=False)
    _persist_result(result, "shop.myshopify.com", tmp_path / "db.sqlite")
    with pytest.raises(ValueError, match="Accept blocked"):
        record_decision(
            "shop.myshopify.com", "act-1", "accept", db_path=tmp_path / "db.sqlite"
        )


def test_reject_sets_rejected_status(tmp_path):
    result = _make_result()
    _persist_result(result, "shop.myshopify.com", tmp_path / "db.sqlite")
    decision = record_decision(
        "shop.myshopify.com", "act-1", "reject",
        rejected_reason="Texte trop générique.",
        db_path=tmp_path / "db.sqlite",
    )
    assert decision["new_status"] == ContentStatus.REJECTED.value


def test_edit_with_new_text_sets_approved(tmp_path):
    result = _make_result()
    _persist_result(result, "shop.myshopify.com", tmp_path / "db.sqlite")
    decision = record_decision(
        "shop.myshopify.com", "act-1", "edit",
        edited_text="Harnais nylon chien — sécurité et confort quotidien",
        db_path=tmp_path / "db.sqlite",
    )
    assert decision["new_status"] == ContentStatus.APPROVED.value


def test_retry_increments_index(tmp_path):
    result = _make_result()
    _persist_result(result, "shop.myshopify.com", tmp_path / "db.sqlite")
    d = record_decision(
        "shop.myshopify.com", "act-1", "retry", db_path=tmp_path / "db.sqlite"
    )
    assert d["retry_index"] == 1
    assert d["new_status"] == ContentStatus.DRAFT.value


def test_retry_blocked_after_3(tmp_path):
    db = tmp_path / "db.sqlite"
    result = _make_result()
    _persist_result(result, "shop.myshopify.com", db)
    for _ in range(3):
        record_decision("shop.myshopify.com", "act-1", "retry", db_path=db)
    with pytest.raises(ValueError, match="Maximum 3 retries"):
        record_decision("shop.myshopify.com", "act-1", "retry", db_path=db)


def test_invalid_decision_raises(tmp_path):
    result = _make_result()
    _persist_result(result, "shop.myshopify.com", tmp_path / "db.sqlite")
    with pytest.raises(ValueError, match="Invalid decision"):
        record_decision(
            "shop.myshopify.com", "act-1", "approve", db_path=tmp_path / "db.sqlite"
        )


def test_action_not_found_raises(tmp_path):
    with pytest.raises(ValueError, match="not found"):
        record_decision(
            "shop.myshopify.com", "ghost-id", "accept", db_path=tmp_path / "db.sqlite"
        )
