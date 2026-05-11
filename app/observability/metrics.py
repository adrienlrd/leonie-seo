"""LLM usage metrics — record calls, query per-shop totals, check budgets."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.db_adapter import DB_PATH, get_conn
from app.observability.costs import compute_cost


def record_llm_call(
    shop: str | None,
    provider: str,
    model: str,
    tokens_in: int,
    tokens_out: int,
    latency_ms: float,
    *,
    error: str | None = None,
    db_path: Path | None = None,
) -> None:
    """Persist one LLM call's usage data.

    Args:
        shop: Shop domain (may be None for background jobs without shop context).
        provider: Provider name (openai, groq, cloudflare).
        model: Model identifier.
        tokens_in: Prompt tokens consumed.
        tokens_out: Completion tokens generated.
        latency_ms: End-to-end latency in milliseconds.
        error: Error message if the call failed, None on success.
        db_path: Override DB path (tests only).
    """
    cost_usd = compute_cost(model, tokens_in, tokens_out)
    path = db_path if db_path is not None else DB_PATH
    now = datetime.now(UTC).isoformat()
    with get_conn(path) as conn:
        conn.execute(
            """INSERT INTO llm_metrics
               (shop, provider, model, tokens_in, tokens_out, cost_usd, latency_ms, error, called_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (shop, provider, model, tokens_in, tokens_out, cost_usd, latency_ms, error, now),
        )


def get_shop_metrics(
    shop: str,
    *,
    days: int = 30,
    db_path: Path | None = None,
) -> dict:
    """Return aggregated LLM usage metrics for a shop over the last N days.

    Args:
        shop: Shop domain.
        days: Lookback window in days (default 30).
        db_path: Override DB path (tests only).

    Returns:
        Dict with keys: total_calls, successful_calls, failed_calls,
        total_tokens_in, total_tokens_out, total_cost_usd, avg_latency_ms,
        by_provider (dict of provider → {calls, tokens_in, tokens_out, cost_usd}).
    """
    path = db_path if db_path is not None else DB_PATH
    since = (datetime.now(UTC) - timedelta(days=days)).isoformat()

    with get_conn(path) as conn:
        rows = conn.execute(
            """SELECT provider, model, tokens_in, tokens_out, cost_usd, latency_ms, error
               FROM llm_metrics
               WHERE shop = ? AND called_at >= ?""",
            (shop, since),
        ).fetchall()

    total_calls = len(rows)
    successful = sum(1 for r in rows if not (r["error"] if isinstance(r, dict) else r[6]))
    failed = total_calls - successful

    def _val(row, idx: int, key: str):
        return row[key] if isinstance(row, dict) else row[idx]

    total_tin = sum(_val(r, 2, "tokens_in") or 0 for r in rows)
    total_tout = sum(_val(r, 3, "tokens_out") or 0 for r in rows)
    total_cost = sum(_val(r, 4, "cost_usd") or 0.0 for r in rows)
    latencies = [_val(r, 5, "latency_ms") or 0.0 for r in rows if not _val(r, 6, "error")]
    avg_latency = round(sum(latencies) / len(latencies), 1) if latencies else 0.0

    by_provider: dict[str, dict] = {}
    for row in rows:
        prov = _val(row, 0, "provider")
        if prov not in by_provider:
            by_provider[prov] = {"calls": 0, "tokens_in": 0, "tokens_out": 0, "cost_usd": 0.0}
        by_provider[prov]["calls"] += 1
        by_provider[prov]["tokens_in"] += _val(row, 2, "tokens_in") or 0
        by_provider[prov]["tokens_out"] += _val(row, 3, "tokens_out") or 0
        by_provider[prov]["cost_usd"] += _val(row, 4, "cost_usd") or 0.0

    return {
        "shop": shop,
        "days": days,
        "total_calls": total_calls,
        "successful_calls": successful,
        "failed_calls": failed,
        "total_tokens_in": total_tin,
        "total_tokens_out": total_tout,
        "total_cost_usd": round(total_cost, 6),
        "avg_latency_ms": avg_latency,
        "by_provider": by_provider,
    }


def check_budget(
    shop: str,
    budget_usd: float,
    *,
    days: int = 30,
    db_path: Path | None = None,
) -> dict:
    """Compare shop's LLM spend against a budget threshold.

    Args:
        shop: Shop domain.
        budget_usd: Monthly budget ceiling in USD.
        days: Lookback window (default 30).
        db_path: Override DB path (tests only).

    Returns:
        Dict with: budget_usd, spent_usd, remaining_usd, usage_pct,
        over_budget (bool), alert (str | None).
    """
    metrics = get_shop_metrics(shop, days=days, db_path=db_path)
    spent = metrics["total_cost_usd"]
    remaining = round(budget_usd - spent, 6)
    pct = round((spent / budget_usd * 100) if budget_usd > 0 else 0.0, 1)

    alert: str | None = None
    if spent >= budget_usd:
        alert = f"Budget exceeded: ${spent:.4f} spent of ${budget_usd:.2f} limit"
    elif pct >= 80:
        alert = f"Budget warning: {pct}% used (${spent:.4f} of ${budget_usd:.2f})"

    return {
        "shop": shop,
        "budget_usd": budget_usd,
        "spent_usd": spent,
        "remaining_usd": max(remaining, 0.0),
        "usage_pct": pct,
        "over_budget": spent >= budget_usd,
        "alert": alert,
    }
