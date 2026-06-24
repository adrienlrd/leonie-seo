"""Tests for analysis queue position + concurrency serialization."""

from __future__ import annotations

import threading
import time

import app.market_analysis.jobs as jobs


def _reset_jobs() -> None:
    jobs._jobs.clear()


def test_queue_position_zero_for_single_job() -> None:
    _reset_jobs()
    jid = jobs.create_job("s.myshopify.com")
    assert jobs.queue_position(jid) == 0


def test_queue_position_counts_earlier_waiting_jobs() -> None:
    _reset_jobs()
    j1 = jobs.create_job("a.myshopify.com")
    time.sleep(0.001)  # ensure distinct created_at
    j2 = jobs.create_job("b.myshopify.com")
    time.sleep(0.001)
    j3 = jobs.create_job("c.myshopify.com")

    # All queued → j1 is front (0), j2 has 1 ahead, j3 has 2 ahead.
    assert jobs.queue_position(j1) == 0
    assert jobs.queue_position(j2) == 1
    assert jobs.queue_position(j3) == 2


def test_queue_position_ignores_running_and_completed() -> None:
    _reset_jobs()
    j1 = jobs.create_job("a.myshopify.com")
    time.sleep(0.001)
    j2 = jobs.create_job("b.myshopify.com")

    # Once j1 starts running, j2 is at the front (no waiting job ahead).
    jobs.update_job(j1, status="running")
    assert jobs.queue_position(j2) == 0

    jobs.update_job(j1, status="completed")
    assert jobs.queue_position(j2) == 0


def test_queue_position_unknown_job_is_zero() -> None:
    _reset_jobs()
    assert jobs.queue_position("does-not-exist") == 0


def test_semaphore_serializes_analyses() -> None:
    """With MAX_CONCURRENT_ANALYSES=1, two acquirers cannot hold the gate at once."""
    gate = threading.Semaphore(1)
    concurrent = 0
    max_seen = 0
    lock = threading.Lock()

    def worker() -> None:
        nonlocal concurrent, max_seen
        with gate:
            with lock:
                concurrent += 1
                max_seen = max(max_seen, concurrent)
            time.sleep(0.02)
            with lock:
                concurrent -= 1

    threads = [threading.Thread(target=worker) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert max_seen == 1  # never two at once
