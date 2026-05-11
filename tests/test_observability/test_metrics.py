"""Tests for LLM usage metrics and cost computation."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from app.observability.costs import compute_cost
from app.observability.metrics import check_budget, get_shop_metrics, record_llm_call

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _init_db(db_path: Path) -> None:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE IF NOT EXISTS llm_metrics (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            shop       TEXT,
            provider   TEXT NOT NULL,
            model      TEXT NOT NULL,
            tokens_in  INTEGER NOT NULL DEFAULT 0,
            tokens_out INTEGER NOT NULL DEFAULT 0,
            cost_usd   REAL NOT NULL DEFAULT 0.0,
            latency_ms REAL NOT NULL DEFAULT 0.0,
            error      TEXT,
            called_at  TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# compute_cost
# ---------------------------------------------------------------------------


def test_compute_cost_gpt4o_mini():
    # 1000 input + 500 output tokens, rate 0.15/1M + 0.60/1M
    cost = compute_cost("gpt-4o-mini", 1000, 500)
    expected = (1000 * 0.15 + 500 * 0.60) / 1_000_000
    assert abs(cost - expected) < 1e-9


def test_compute_cost_groq_free():
    assert compute_cost("llama3-70b-8192", 5000, 2000) == 0.0


def test_compute_cost_unknown_model():
    assert compute_cost("unknown-model-xyz", 9999, 9999) == 0.0


def test_compute_cost_zero_tokens():
    assert compute_cost("gpt-4o-mini", 0, 0) == 0.0


# ---------------------------------------------------------------------------
# record_llm_call
# ---------------------------------------------------------------------------


def test_record_llm_call_inserts_row(tmp_path):
    db = tmp_path / "test.db"
    _init_db(db)
    record_llm_call("shop.myshopify.com", "openai", "gpt-4o-mini", 100, 50, 320.5, db_path=db)

    conn = sqlite3.connect(db)
    row = conn.execute("SELECT * FROM llm_metrics").fetchone()
    conn.close()

    assert row is not None
    assert row[1] == "shop.myshopify.com"  # shop
    assert row[2] == "openai"  # provider
    assert row[3] == "gpt-4o-mini"  # model
    assert row[4] == 100  # tokens_in
    assert row[5] == 50  # tokens_out
    assert row[6] > 0  # cost_usd
    assert abs(row[7] - 320.5) < 0.01  # latency_ms


def test_record_llm_call_with_error(tmp_path):
    db = tmp_path / "test.db"
    _init_db(db)
    record_llm_call(None, "groq", "llama3-70b-8192", 0, 0, 0.0, error="rate limited", db_path=db)

    conn = sqlite3.connect(db)
    row = conn.execute("SELECT error FROM llm_metrics").fetchone()
    conn.close()
    assert row[0] == "rate limited"


def test_record_llm_call_none_shop(tmp_path):
    db = tmp_path / "test.db"
    _init_db(db)
    record_llm_call(None, "openai", "gpt-4o-mini", 10, 5, 100.0, db_path=db)

    conn = sqlite3.connect(db)
    row = conn.execute("SELECT shop FROM llm_metrics").fetchone()
    conn.close()
    assert row[0] is None


# ---------------------------------------------------------------------------
# get_shop_metrics
# ---------------------------------------------------------------------------


def test_get_shop_metrics_empty(tmp_path):
    db = tmp_path / "test.db"
    _init_db(db)
    m = get_shop_metrics("unknown.myshopify.com", db_path=db)

    assert m["total_calls"] == 0
    assert m["total_cost_usd"] == 0.0
    assert m["by_provider"] == {}


def test_get_shop_metrics_aggregates_correctly(tmp_path):
    db = tmp_path / "test.db"
    _init_db(db)
    record_llm_call("s.myshopify.com", "openai", "gpt-4o-mini", 200, 100, 300.0, db_path=db)
    record_llm_call("s.myshopify.com", "openai", "gpt-4o-mini", 300, 150, 400.0, db_path=db)
    record_llm_call("s.myshopify.com", "groq", "llama3-70b-8192", 100, 50, 150.0, db_path=db)
    record_llm_call("s.myshopify.com", "openai", "gpt-4o-mini", 0, 0, 0.0, error="err", db_path=db)

    m = get_shop_metrics("s.myshopify.com", db_path=db)

    assert m["total_calls"] == 4
    assert m["successful_calls"] == 3
    assert m["failed_calls"] == 1
    assert m["total_tokens_in"] == 600
    assert m["total_tokens_out"] == 300
    assert m["total_cost_usd"] > 0
    assert "openai" in m["by_provider"]
    assert "groq" in m["by_provider"]
    assert m["by_provider"]["openai"]["calls"] == 3
    assert m["by_provider"]["groq"]["calls"] == 1


def test_get_shop_metrics_isolates_by_shop(tmp_path):
    db = tmp_path / "test.db"
    _init_db(db)
    record_llm_call("shop-a.myshopify.com", "openai", "gpt-4o-mini", 100, 50, 200.0, db_path=db)
    record_llm_call("shop-b.myshopify.com", "openai", "gpt-4o-mini", 999, 999, 200.0, db_path=db)

    m = get_shop_metrics("shop-a.myshopify.com", db_path=db)
    assert m["total_calls"] == 1
    assert m["total_tokens_in"] == 100


def test_get_shop_metrics_avg_latency_excludes_errors(tmp_path):
    db = tmp_path / "test.db"
    _init_db(db)
    record_llm_call("s.myshopify.com", "openai", "gpt-4o-mini", 100, 50, 400.0, db_path=db)
    record_llm_call("s.myshopify.com", "openai", "gpt-4o-mini", 0, 0, 0.0, error="err", db_path=db)

    m = get_shop_metrics("s.myshopify.com", db_path=db)
    assert m["avg_latency_ms"] == 400.0  # error call excluded


# ---------------------------------------------------------------------------
# check_budget
# ---------------------------------------------------------------------------


def test_check_budget_under_80pct(tmp_path):
    db = tmp_path / "test.db"
    _init_db(db)
    # No spend → 0%
    result = check_budget("shop.myshopify.com", budget_usd=10.0, db_path=db)
    assert result["over_budget"] is False
    assert result["alert"] is None
    assert result["usage_pct"] == 0.0
    assert result["remaining_usd"] == 10.0


def test_check_budget_over_budget(tmp_path):
    db = tmp_path / "test.db"
    _init_db(db)
    # Insert a call with cost > budget
    # gpt-4o-mini: 0.15/1M input + 0.60/1M output
    # 10M input tokens = 1.50 USD > 1.00 USD budget
    record_llm_call("s.myshopify.com", "openai", "gpt-4o-mini", 10_000_000, 0, 1.0, db_path=db)

    result = check_budget("s.myshopify.com", budget_usd=1.0, db_path=db)
    assert result["over_budget"] is True
    assert result["alert"] is not None
    assert "exceeded" in result["alert"]
    assert result["remaining_usd"] == 0.0


def test_check_budget_warning_at_80pct(tmp_path):
    db = tmp_path / "test.db"
    _init_db(db)
    # Inject a metric row directly with a known cost
    conn = sqlite3.connect(db)
    conn.execute(
        "INSERT INTO llm_metrics (shop, provider, model, tokens_in, tokens_out, cost_usd, latency_ms, called_at)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))",
        ("s.myshopify.com", "openai", "gpt-4o-mini", 0, 0, 8.5, 100.0),
    )
    conn.commit()
    conn.close()

    result = check_budget("s.myshopify.com", budget_usd=10.0, db_path=db)
    assert result["over_budget"] is False
    assert result["alert"] is not None
    assert "warning" in result["alert"].lower()
    assert result["usage_pct"] == 85.0
