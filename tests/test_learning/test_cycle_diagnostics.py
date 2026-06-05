"""Tests for the 0-proposal diagnostics of a learning cycle."""

from __future__ import annotations

from app.learning.scheduler import diagnose_cycle_outcome


def test_diagnose_learning_disabled() -> None:
    result = diagnose_cycle_outcome(
        learning_enabled=False, continuous_result=None, cycle_errors=[]
    )
    assert result["reason"] == "learning_disabled"
    assert result["proposals"] == 0


def test_diagnose_no_market_analysis() -> None:
    errors = [{"stage": "continuous_agent", "error": "No market analysis is available."}]
    result = diagnose_cycle_outcome(
        learning_enabled=True, continuous_result=None, cycle_errors=errors
    )
    assert result["reason"] == "no_market_analysis"


def test_diagnose_no_candidates() -> None:
    continuous = {"summary": {"products_seen": 12, "candidate_actions": 0, "proposals_created": 0}}
    result = diagnose_cycle_outcome(
        learning_enabled=True, continuous_result=continuous, cycle_errors=[]
    )
    assert result["reason"] == "no_candidates"


def test_diagnose_all_candidates_failed() -> None:
    continuous = {
        "summary": {"products_seen": 5, "candidate_actions": 3, "proposals_created": 0},
        "errors": [{"error": "llm failed"}],
    }
    result = diagnose_cycle_outcome(
        learning_enabled=True, continuous_result=continuous, cycle_errors=[]
    )
    assert result["reason"] == "all_candidates_failed"


def test_diagnose_ok_reports_proposal_count() -> None:
    continuous = {"summary": {"products_seen": 5, "candidate_actions": 3, "proposals_created": 2}}
    result = diagnose_cycle_outcome(
        learning_enabled=True, continuous_result=continuous, cycle_errors=[]
    )
    assert result["reason"] == "ok"
    assert result["proposals"] == 2
