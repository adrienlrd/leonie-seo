"""Job queue store — enqueue, claim, and update job rows."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.db import DB_PATH
from app.db_adapter import get_conn

_DEFAULT_MAX_RETRIES = 3
_DEFAULT_PRIORITY = 0


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _scheduled_at(delay_seconds: int) -> str:
    return (datetime.now(UTC) + timedelta(seconds=delay_seconds)).isoformat()


def enqueue(
    queue: str,
    payload: dict,
    *,
    job_id: str | None = None,
    shop: str | None = None,
    delay_seconds: int = 0,
    max_retries: int = _DEFAULT_MAX_RETRIES,
    priority: int = _DEFAULT_PRIORITY,
    db_path: Path | None = None,
) -> str:
    """Insert a job into the queue. Returns the job ID (UUID string).

    Args:
        job_id: Optional pre-generated ID (useful when the ID must be embedded in
                the payload before insertion). Defaults to a new UUID4.
    """
    job_id = job_id or str(uuid.uuid4())
    now = _now()
    path = db_path if db_path is not None else DB_PATH
    with get_conn(path) as conn:
        conn.execute(
            """
            INSERT INTO jobs
                (id, queue, payload, shop, status, priority, retries, max_retries,
                 scheduled_at, created_at)
            VALUES (?, ?, ?, ?, 'pending', ?, 0, ?, ?, ?)
            """,
            (
                job_id,
                queue,
                json.dumps(payload),
                shop,
                priority,
                max_retries,
                _scheduled_at(delay_seconds),
                now,
            ),
        )
    return job_id


def get_job(job_id: str, db_path: Path | None = None) -> dict | None:
    """Return the full job row by ID, or None."""
    path = db_path if db_path is not None else DB_PATH
    with get_conn(path) as conn:
        row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    if row is None:
        return None
    return _decode(row)


def list_jobs(
    shop: str | None = None,
    queue: str | None = None,
    status: str | None = None,
    limit: int = 50,
    db_path: Path | None = None,
) -> list[dict]:
    """Return jobs filtered by shop / queue / status, most recent first."""
    path = db_path if db_path is not None else DB_PATH
    clauses: list[str] = []
    params: list = []
    if shop is not None:
        clauses.append("shop = ?")
        params.append(shop)
    if queue is not None:
        clauses.append("queue = ?")
        params.append(queue)
    if status is not None:
        clauses.append("status = ?")
        params.append(status)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    params.append(limit)
    with get_conn(path) as conn:
        rows = conn.execute(
            f"SELECT * FROM jobs {where} ORDER BY created_at DESC LIMIT ?",  # noqa: S608
            tuple(params),
        ).fetchall()
    return [_decode(r) for r in rows]


def claim_next(queue: str | None = None, db_path: Path | None = None) -> dict | None:
    """Atomically claim the next pending job that is due.

    Uses UPDATE + rowcount check (works in both SQLite and Postgres without
    requiring FOR UPDATE SKIP LOCKED, which SQLite does not support).
    Postgres-backed deployments with a single worker process are safe; for
    multi-worker Postgres, upgrade to SELECT ... FOR UPDATE SKIP LOCKED later.

    Returns the claimed job dict, or None if the queue is empty.
    """
    path = db_path if db_path is not None else DB_PATH
    now = _now()
    queue_filter = "AND queue = ?" if queue else ""
    queue_params = (queue,) if queue else ()

    with get_conn(path) as conn:
        # Find the best candidate: pending, due, highest priority, oldest first.
        row = conn.execute(
            f"""
            SELECT id FROM jobs
            WHERE status = 'pending' AND scheduled_at <= ?
            {queue_filter}
            ORDER BY priority DESC, scheduled_at ASC
            LIMIT 1
            """,  # noqa: S608
            (now, *queue_params),
        ).fetchone()

        if row is None:
            return None

        job_id = row["id"]

        # Atomic claim: only succeeds if another worker hasn't taken it.
        cur = conn.execute(
            "UPDATE jobs SET status = 'running', started_at = ? WHERE id = ? AND status = 'pending'",
            (now, job_id),
        )
        if cur.rowcount == 0:
            return None  # Race lost — caller should retry

    return get_job(job_id, db_path)


def recover_stale_running_jobs(
    *,
    stale_after_seconds: int,
    db_path: Path | None = None,
) -> int:
    """Requeue or fail jobs left in running state by a crashed worker.

    Render deploys, process restarts, or unhandled handler failures can leave a
    job marked as running even though no worker is still processing it. This
    repair step is intentionally conservative: it only touches jobs whose
    started_at timestamp is older than the worker timeout window.
    """
    path = db_path if db_path is not None else DB_PATH
    now = _now()
    cutoff = (datetime.now(UTC) - timedelta(seconds=stale_after_seconds)).isoformat()
    repaired = 0

    with get_conn(path) as conn:
        rows = conn.execute(
            """
            SELECT id, retries, max_retries
            FROM jobs
            WHERE status = 'running'
              AND started_at IS NOT NULL
              AND started_at <= ?
            """,
            (cutoff,),
        ).fetchall()

        for row in rows:
            new_retries = int(row["retries"]) + 1
            max_retries = int(row["max_retries"])
            result = json.dumps(
                {
                    "error": f"stale running job recovered after {stale_after_seconds}s",
                    "attempt": new_retries,
                }
            )

            if new_retries <= max_retries:
                conn.execute(
                    """
                    UPDATE jobs
                    SET status = 'pending',
                        retries = ?,
                        result = ?,
                        scheduled_at = ?,
                        started_at = NULL,
                        completed_at = NULL
                    WHERE id = ? AND status = 'running'
                    """,
                    (new_retries, result, now, row["id"]),
                )
            else:
                conn.execute(
                    """
                    UPDATE jobs
                    SET status = 'failed',
                        retries = ?,
                        result = ?,
                        completed_at = ?
                    WHERE id = ? AND status = 'running'
                    """,
                    (new_retries, result, now, row["id"]),
                )
            repaired += 1

    return repaired


def enqueue_unique(
    queue: str,
    payload: dict,
    *,
    shop: str | None = None,
    db_path: Path | None = None,
    delay_seconds: int = 0,
    max_retries: int = _DEFAULT_MAX_RETRIES,
    priority: int = _DEFAULT_PRIORITY,
) -> str:
    """Enqueue a job only if no pending/running job already exists for queue+shop.

    Returns the existing job ID if one is already queued, otherwise the new one.
    Prevents duplicate background jobs that pile up on repeated triggers.
    """
    path = db_path if db_path is not None else DB_PATH
    # IS is SQLite-only for value equality. PostgreSQL requires = for non-null values.
    if shop is not None:
        shop_clause = "AND shop = ?"
        params: tuple = (queue, shop)
    else:
        shop_clause = "AND shop IS NULL"
        params = (queue,)
    with get_conn(path) as conn:
        row = conn.execute(
            f"""SELECT id FROM jobs
               WHERE queue = ? {shop_clause} AND status IN ('pending', 'running')
               ORDER BY created_at DESC LIMIT 1""",  # noqa: S608
            params,
        ).fetchone()
    if row:
        return row["id"]
    return enqueue(
        queue,
        payload,
        shop=shop,
        db_path=db_path,
        delay_seconds=delay_seconds,
        max_retries=max_retries,
        priority=priority,
    )


def cancel_shop_jobs(
    shop: str,
    *,
    queue: str | None = None,
    db_path: Path | None = None,
) -> int:
    """Mark all pending and running jobs for a shop (and optional queue) as failed.

    Used to clear a stuck job queue without restarting the worker process.
    Returns the number of jobs cancelled.
    """
    path = db_path if db_path is not None else DB_PATH
    now = _now()
    queue_filter = "AND queue = ?" if queue else ""
    params: tuple = (now, shop, *([queue] if queue else []))

    with get_conn(path) as conn:
        cur = conn.execute(
            f"""UPDATE jobs
                SET status = 'failed', result = '"cancelled by admin"', completed_at = ?
                WHERE shop = ? AND status IN ('pending', 'running')
                {queue_filter}""",  # noqa: S608
            params,
        )
        return cur.rowcount


def update_job(
    job_id: str,
    *,
    status: str,
    result: dict | str | None = None,
    retries: int | None = None,
    scheduled_at: str | None = None,
    db_path: Path | None = None,
) -> None:
    """Update job status and optional fields after processing."""
    path = db_path if db_path is not None else DB_PATH
    now = _now()
    result_str = json.dumps(result) if isinstance(result, dict) else result

    fields = ["status = ?", "completed_at = ?"]
    params: list = [status, now if status in ("completed", "failed") else None]

    if result_str is not None:
        fields.append("result = ?")
        params.append(result_str)
    if retries is not None:
        fields.append("retries = ?")
        params.append(retries)
    if scheduled_at is not None:
        fields.append("scheduled_at = ?")
        params.append(scheduled_at)

    params.append(job_id)
    with get_conn(path) as conn:
        conn.execute(
            f"UPDATE jobs SET {', '.join(fields)} WHERE id = ?",  # noqa: S608
            tuple(params),
        )


def _decode(row: dict) -> dict:
    """Parse the JSON payload and result fields."""
    out = dict(row)
    if out.get("payload"):
        try:
            out["payload"] = json.loads(out["payload"])
        except (json.JSONDecodeError, TypeError):
            pass
    if out.get("result"):
        try:
            out["result"] = json.loads(out["result"])
        except (json.JSONDecodeError, TypeError):
            pass
    return out
