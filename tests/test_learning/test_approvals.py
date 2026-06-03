"""Tests for learning approval safety filters."""

from __future__ import annotations

from app.learning.approvals import is_safe_approval


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
