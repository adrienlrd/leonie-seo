"""Tests for the safe apply diff builder."""

from __future__ import annotations

from unittest.mock import patch

from app.content_actions.schema import (
    ConfirmedFact,
    ConstraintsCheck,
    ContentActionResult,
    ContentOutput,
    ContentStatus,
    ContentType,
    QualityResult,
)
from app.safe_apply.diff import build_diff


def _make_result(
    status: ContentStatus = ContentStatus.DRAFT,
    violations: list[str] | None = None,
    length_ok: bool = True,
    language_ok: bool = True,
    quality_score: int = 70,
) -> ContentActionResult:
    return ContentActionResult(
        action_id="test-id",
        content_type=ContentType.META_TITLE,
        resource_id="gid://shopify/Product/1",
        generated_at="2026-05-21T10:00:00+00:00",
        output=ContentOutput(primary_text="Harnais chien nylon réglable — confort et sécurité"),
        facts_used=[ConfirmedFact(key="material", value="nylon")],
        constraints_check=ConstraintsCheck(
            length_ok=length_ok,
            language_ok=language_ok,
            forbidden_promise_violations=violations or [],
        ),
        quality=QualityResult(score=quality_score, label="bon"),
        status=status,
    )


def test_build_diff_returns_none_when_action_not_found(tmp_path):
    with patch("app.safe_apply.diff._load_action", return_value=None):
        assert build_diff("missing", "shop.myshopify.com") is None


def test_build_diff_returns_action_id_and_content_type():
    result = _make_result()
    with patch("app.safe_apply.diff._load_action", return_value=result):
        diff = build_diff("test-id", "shop.myshopify.com")
    assert diff is not None
    assert diff["action_id"] == "test-id"
    assert diff["content_type"] == ContentType.META_TITLE.value


def test_build_diff_after_contains_generated_text():
    result = _make_result()
    with patch("app.safe_apply.diff._load_action", return_value=result):
        diff = build_diff("test-id", "shop.myshopify.com")
    assert diff["after"]["primary_text"] == "Harnais chien nylon réglable — confort et sécurité"


def test_build_diff_clean_allows_accept():
    result = _make_result()
    with patch("app.safe_apply.diff._load_action", return_value=result):
        diff = build_diff("test-id", "shop.myshopify.com")
    assert "accept" in diff["decision_state"]["next_actions"]
    assert diff["decision_state"]["blocked_reasons"] == []


def test_build_diff_forbidden_promise_blocks_accept():
    result = _make_result(violations=["guérit"])
    with patch("app.safe_apply.diff._load_action", return_value=result):
        diff = build_diff("test-id", "shop.myshopify.com")
    assert "accept" not in diff["decision_state"]["next_actions"]
    assert any("forbidden_promise" in r for r in diff["decision_state"]["blocked_reasons"])


def test_build_diff_length_failure_blocks_accept():
    result = _make_result(length_ok=False)
    with patch("app.safe_apply.diff._load_action", return_value=result):
        diff = build_diff("test-id", "shop.myshopify.com")
    assert "accept" not in diff["decision_state"]["next_actions"]
    assert "length_out_of_bounds" in diff["decision_state"]["blocked_reasons"]


def test_build_diff_merchant_view_summary_fr_non_empty():
    result = _make_result()
    with patch("app.safe_apply.diff._load_action", return_value=result):
        diff = build_diff("test-id", "shop.myshopify.com")
    summary = diff["merchant_view"]["summary_fr"]
    assert len(summary) > 20
    assert "titre méta" in summary


def test_build_diff_facts_used_serialized():
    result = _make_result()
    with patch("app.safe_apply.diff._load_action", return_value=result):
        diff = build_diff("test-id", "shop.myshopify.com")
    assert len(diff["facts_used"]) == 1
    assert diff["facts_used"][0]["key"] == "material"


def test_build_diff_before_is_none_v1():
    result = _make_result()
    with patch("app.safe_apply.diff._load_action", return_value=result):
        diff = build_diff("test-id", "shop.myshopify.com")
    assert diff["before"] is None
