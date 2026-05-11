"""Tests for the LLM meta suggestion diff / review engine."""

from __future__ import annotations

import pytest

from app.llm.review import (
    _DESC_MAX,
    _DESC_MIN,
    _TITLE_MAX,
    _TITLE_MIN,
    DiffResult,
    compute_diff,
    diff_suggestions,
)


def _suggestion(
    *,
    id: int = 1,
    product_id: str = "gid://shopify/Product/1",
    product_title: str = "Pardessus chien premium",
    generated_title: str = "",
    generated_description: str = "",
    status: str = "pending",
) -> dict:
    return {
        "id": id,
        "product_id": product_id,
        "product_title": product_title,
        "generated_title": generated_title,
        "generated_description": generated_description,
        "status": status,
    }


def _ok_title() -> str:
    """Return a title exactly 55 chars (within 50-60 target)."""
    return "x" * 55


def _ok_desc() -> str:
    """Return a description exactly 150 chars (within 140-160 target)."""
    return "x" * 150


# ── compute_diff ──────────────────────────────────────────────────────────────


def test_compute_diff_returns_diff_result():
    result = compute_diff(
        _suggestion(generated_title=_ok_title(), generated_description=_ok_desc())
    )
    assert isinstance(result, DiffResult)


def test_compute_diff_title_length_ok_within_target():
    title = "A" * 55
    result = compute_diff(_suggestion(generated_title=title, generated_description=_ok_desc()))
    assert result.title_length == 55
    assert result.title_length_ok is True


def test_compute_diff_title_too_short_fails():
    title = "A" * (_TITLE_MIN - 1)
    result = compute_diff(_suggestion(generated_title=title, generated_description=_ok_desc()))
    assert result.title_length_ok is False
    assert result.passes_quality_check is False


def test_compute_diff_title_too_long_fails():
    title = "A" * (_TITLE_MAX + 1)
    result = compute_diff(_suggestion(generated_title=title, generated_description=_ok_desc()))
    assert result.title_length_ok is False
    assert result.passes_quality_check is False


def test_compute_diff_desc_length_ok_within_target():
    desc = "A" * 150
    result = compute_diff(_suggestion(generated_title=_ok_title(), generated_description=desc))
    assert result.desc_length == 150
    assert result.desc_length_ok is True


def test_compute_diff_desc_too_short_fails():
    desc = "A" * (_DESC_MIN - 1)
    result = compute_diff(_suggestion(generated_title=_ok_title(), generated_description=desc))
    assert result.desc_length_ok is False
    assert result.passes_quality_check is False


def test_compute_diff_desc_too_long_fails():
    desc = "A" * (_DESC_MAX + 1)
    result = compute_diff(_suggestion(generated_title=_ok_title(), generated_description=desc))
    assert result.desc_length_ok is False
    assert result.passes_quality_check is False


def test_compute_diff_passes_quality_check_when_both_lengths_ok():
    result = compute_diff(
        _suggestion(generated_title=_ok_title(), generated_description=_ok_desc())
    )
    assert result.passes_quality_check is True


def test_compute_diff_fails_quality_check_when_title_empty():
    result = compute_diff(_suggestion(generated_title="", generated_description=_ok_desc()))
    assert result.passes_quality_check is False


def test_compute_diff_title_changed_when_different_from_baseline():
    result = compute_diff(
        _suggestion(
            product_title="Pardessus chien",
            generated_title=_ok_title(),
            generated_description=_ok_desc(),
        )
    )
    assert result.title_changed is True


def test_compute_diff_title_not_changed_when_same_case_insensitive():
    title = "pardessus chien premium"
    result = compute_diff(
        _suggestion(
            product_title="Pardessus chien premium",
            generated_title=title,
            generated_description=_ok_desc(),
        )
    )
    assert result.title_changed is False


def test_compute_diff_summary_reports_issues():
    result = compute_diff(_suggestion(generated_title="short", generated_description="short"))
    assert "title" in result.summary
    assert "desc" in result.summary


def test_compute_diff_summary_ok_when_lengths_valid():
    result = compute_diff(
        _suggestion(generated_title=_ok_title(), generated_description=_ok_desc())
    )
    assert result.summary == "ok"


# ── diff_suggestions ──────────────────────────────────────────────────────────


def test_diff_suggestions_returns_one_diff_per_suggestion():
    suggestions = [
        _suggestion(id=1, generated_title=_ok_title(), generated_description=_ok_desc()),
        _suggestion(id=2, generated_title="too short", generated_description="too short"),
    ]
    results = diff_suggestions(suggestions)
    assert len(results) == 2
    assert results[0].passes_quality_check is True
    assert results[1].passes_quality_check is False


def test_diff_suggestions_empty_input_returns_empty():
    assert diff_suggestions([]) == []


# ── batch_update_status ───────────────────────────────────────────────────────


def test_batch_update_status_updates_multiple_rows(tmp_path):
    from app.db import init_db
    from app.llm.batch import MetaResult
    from app.llm.meta_store import batch_update_status, list_suggestions, save_results

    db = tmp_path / "test.db"
    init_db(db)

    results = [
        MetaResult(
            product_id="1",
            product_title="P1",
            generated_title="T1",
            generated_description="D1",
            provider="openai",
        ),
        MetaResult(
            product_id="2",
            product_title="P2",
            generated_title="T2",
            generated_description="D2",
            provider="openai",
        ),
        MetaResult(
            product_id="3",
            product_title="P3",
            generated_title="T3",
            generated_description="D3",
            provider="openai",
        ),
    ]
    save_results(results, shop="s.myshopify.com", job_id="j", db_path=db)
    rows = list_suggestions("s.myshopify.com", db_path=db)
    ids = [r["id"] for r in rows[:2]]

    count = batch_update_status(ids, "approved", db_path=db)
    assert count == 2

    approved = list_suggestions("s.myshopify.com", status="approved", db_path=db)
    assert len(approved) == 2


def test_batch_update_status_empty_list_returns_zero(tmp_path):
    from app.llm.meta_store import batch_update_status

    assert batch_update_status([], "approved") == 0


def test_batch_update_status_rejects_invalid_status():
    from app.llm.meta_store import batch_update_status

    with pytest.raises(ValueError, match="Invalid status"):
        batch_update_status([1, 2], "invalid")
