"""Async job worker — polls the queue, dispatches handlers, manages retries."""

from __future__ import annotations

import asyncio
import logging
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.jobs.handlers import get_handler
from app.jobs.store import claim_next, recover_stale_running_jobs, update_job
from app.llm.provider import LLMError

logger = logging.getLogger(__name__)

_DEFAULT_POLL_INTERVAL = 5.0  # seconds between polls when queue is empty
_DEFAULT_TIMEOUT = 600  # seconds per job before it is marked failed


def _retry_delay(retries: int) -> int:
    """Exponential backoff: 30 s, 60 s, 120 s … capped at 1 h."""
    return min(30 * (2**retries), 3600)


def _next_scheduled_at(retries: int) -> str:
    delay = _retry_delay(retries)
    return (datetime.now(UTC) + timedelta(seconds=delay)).isoformat()


class JobWorker:
    """Async worker that processes jobs from the queue table.

    Designed to run as a single asyncio background task inside the FastAPI
    lifespan. Multi-worker concurrency (Postgres FOR UPDATE SKIP LOCKED) can
    be added later when throughput requires it.
    """

    def __init__(
        self,
        poll_interval: float = _DEFAULT_POLL_INTERVAL,
        timeout: int = _DEFAULT_TIMEOUT,
        stale_after_seconds: int | None = None,
        db_path: Path | None = None,
    ) -> None:
        self.poll_interval = poll_interval
        self.timeout = timeout
        self.stale_after_seconds = stale_after_seconds or timeout + 60
        self._db_path = db_path
        self._running = False

    async def run(self) -> None:
        """Main loop — runs until cancelled."""
        self._running = True
        logger.info("JobWorker started (poll_interval=%.1fs)", self.poll_interval)
        while self._running:
            try:
                recovered = recover_stale_running_jobs(
                    stale_after_seconds=self.stale_after_seconds,
                    db_path=self._db_path,
                )
                if recovered:
                    logger.warning("Recovered %d stale running job(s)", recovered)
                job = claim_next(db_path=self._db_path)
                if job:
                    await self._process(job)
                else:
                    await asyncio.sleep(self.poll_interval)
            except asyncio.CancelledError:
                break
            except (OSError, RuntimeError, TypeError, ValueError, sqlite3.Error, LLMError):
                logger.exception("Unexpected error in JobWorker loop")
                await asyncio.sleep(self.poll_interval)
        logger.info("JobWorker stopped")

    def stop(self) -> None:
        self._running = False

    async def _process(self, job: dict) -> None:
        job_id: str = job["id"]
        queue: str = job["queue"]
        shop: str | None = job.get("shop")
        retries: int = job.get("retries", 0)
        max_retries: int = job.get("max_retries", 3)

        handler = get_handler(queue)
        if handler is None:
            logger.error("No handler registered for queue %r (job %s)", queue, job_id)
            update_job(
                job_id,
                status="failed",
                result=f"no handler for queue '{queue}'",
                db_path=self._db_path,
            )
            return

        logger.info(
            "Processing job %s (queue=%s shop=%s attempt=%d)", job_id, queue, shop, retries + 1
        )
        try:
            result = await asyncio.wait_for(
                handler(job["payload"], shop),
                timeout=self.timeout,
            )
            update_job(job_id, status="completed", result=result, db_path=self._db_path)
            logger.info("Job %s completed", job_id)

        except TimeoutError:
            logger.warning("Job %s timed out after %ds", job_id, self.timeout)
            self._handle_failure(job_id, retries, max_retries, f"timed out after {self.timeout}s")

        except (OSError, RuntimeError, TypeError, ValueError, sqlite3.Error, LLMError) as exc:
            logger.warning("Job %s failed: %s", job_id, exc)
            self._handle_failure(job_id, retries, max_retries, str(exc))

    def _handle_failure(self, job_id: str, retries: int, max_retries: int, error: str) -> None:
        new_retries = retries + 1
        if new_retries <= max_retries:
            next_at = _next_scheduled_at(new_retries)
            update_job(
                job_id,
                status="pending",
                result={"error": error, "attempt": new_retries},
                retries=new_retries,
                scheduled_at=next_at,
                db_path=self._db_path,
            )
            logger.info(
                "Job %s scheduled for retry %d/%d at %s", job_id, new_retries, max_retries, next_at
            )
        else:
            update_job(
                job_id,
                status="failed",
                result={"error": error, "attempts": new_retries},
                retries=new_retries,
                db_path=self._db_path,
            )
            logger.warning("Job %s permanently failed after %d attempts", job_id, new_retries)
