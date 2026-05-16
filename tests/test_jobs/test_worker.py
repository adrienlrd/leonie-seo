"""Tests for JobWorker — dispatch, retry logic, backoff, error handling."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import pytest

from app.db import init_db
from app.jobs.handlers import _HANDLERS, register
from app.jobs.store import enqueue, get_job
from app.jobs.worker import JobWorker, _next_scheduled_at, _retry_delay

# ── Retry/backoff helpers ─────────────────────────────────────────────────────


def test_retry_delay_exponential():
    assert _retry_delay(0) == 30
    assert _retry_delay(1) == 60
    assert _retry_delay(2) == 120
    assert _retry_delay(3) == 240


def test_retry_delay_capped_at_one_hour():
    assert _retry_delay(100) == 3600


def test_next_scheduled_at_is_in_future():
    ts = _next_scheduled_at(0)
    scheduled = datetime.fromisoformat(ts)
    assert scheduled > datetime.now(UTC)


# ── Worker dispatch ───────────────────────────────────────────────────────────


@pytest.fixture()
def db(tmp_path):
    path = tmp_path / "test.db"
    init_db(path)
    return path


@pytest.fixture(autouse=True)
def _cleanup_handlers():
    """Restore handler registry after each test."""
    original = dict(_HANDLERS)
    yield
    _HANDLERS.clear()
    _HANDLERS.update(original)


def test_worker_processes_job_to_completed(db):
    @register("test_ok")
    async def _ok(payload, shop):
        return {"done": True}

    job_id = enqueue("test_ok", {"x": 1}, db_path=db)
    worker = JobWorker(db_path=db)

    asyncio.run(_run_one(worker))

    job = get_job(job_id, db_path=db)
    assert job["status"] == "completed"
    assert job["result"]["done"] is True


def test_worker_retries_on_handler_exception(db):
    @register("test_fail")
    async def _fail(payload, shop):
        raise ValueError("oops")

    job_id = enqueue("test_fail", {}, max_retries=2, db_path=db)
    worker = JobWorker(db_path=db)

    asyncio.run(_run_one(worker))

    job = get_job(job_id, db_path=db)
    assert job["status"] == "pending"  # scheduled for retry
    assert job["retries"] == 1


def test_worker_fails_permanently_after_max_retries(db):
    @register("test_exhaust")
    async def _exhaust(payload, shop):
        raise RuntimeError("always fails")

    job_id = enqueue("test_exhaust", {}, max_retries=1, db_path=db)
    worker = JobWorker(db_path=db)

    # First attempt → retries=1, still pending (scheduled in future)
    asyncio.run(_run_one(worker))
    job = get_job(job_id, db_path=db)
    assert job["retries"] == 1

    # Force the scheduled_at back to now so the worker can pick it up again
    from app.jobs.store import update_job

    update_job(job_id, status="pending", scheduled_at=datetime.now(UTC).isoformat(), db_path=db)

    # Second attempt → max_retries exceeded → failed
    asyncio.run(_run_one(worker))
    job = get_job(job_id, db_path=db)
    assert job["status"] == "failed"
    assert job["retries"] == 2


def test_worker_marks_failed_for_unknown_queue(db):
    job_id = enqueue("no_such_queue", {}, db_path=db)
    worker = JobWorker(db_path=db)

    asyncio.run(_run_one(worker))

    job = get_job(job_id, db_path=db)
    assert job["status"] == "failed"


def test_worker_timeout_triggers_retry(db):
    @register("test_slow")
    async def _slow(payload, shop):
        await asyncio.sleep(9999)

    job_id = enqueue("test_slow", {}, db_path=db)
    worker = JobWorker(timeout=1, db_path=db)

    asyncio.run(_run_one(worker))

    job = get_job(job_id, db_path=db)
    assert job["retries"] == 1  # timed out → retry


def test_worker_retries_on_llm_error(db):
    from app.llm.provider import LLMError

    @register("test_llm_error")
    async def _llm_error(payload, shop):
        raise LLMError("No LLM provider configured")

    job_id = enqueue("test_llm_error", {}, db_path=db)
    worker = JobWorker(db_path=db)

    asyncio.run(_run_one(worker))

    job = get_job(job_id, db_path=db)
    assert job["status"] == "pending"
    assert job["retries"] == 1
    assert "No LLM provider configured" in job["result"]["error"]


def test_seo_audit_handler_uses_stored_access_token(monkeypatch):
    from app.jobs.handlers import handle_seo_audit

    calls: list[tuple[str, str]] = []
    monkeypatch.setattr(
        "app.oauth.token_store.get_token", lambda shop: {"access_token": "shpat_stored"}
    )
    monkeypatch.setattr(
        "app.jobs.audit_snapshot.crawl_shopify_catalog_for_job",
        lambda shop, access_token: calls.append((shop, access_token)) or {"products": 1},
    )

    result = asyncio.run(handle_seo_audit({}, "store.myshopify.com"))

    assert result["products"] == 1
    assert calls == [("store.myshopify.com", "shpat_stored")]


def test_gsc_import_handler_imports_for_shop(monkeypatch):
    from app.jobs.handlers import handle_gsc_import

    calls: list[tuple[str, int, str | None]] = []
    monkeypatch.setattr(
        "app.gsc.client.fetch_and_store_gsc_performance",
        lambda shop, days, site_url: calls.append((shop, days, site_url)) or {"query_page_rows": 3},
    )

    result = asyncio.run(
        handle_gsc_import({"days": 30, "site_url": "sc-domain:example.com"}, "store.myshopify.com")
    )

    assert result["query_page_rows"] == 3
    assert calls == [("store.myshopify.com", 30, "sc-domain:example.com")]


def test_pagespeed_import_handler_imports_for_shop(monkeypatch):
    from app.jobs.handlers import handle_pagespeed_import

    calls: list[tuple[str, list[str] | None, int, str | None]] = []
    monkeypatch.setattr(
        "app.pagespeed.client.fetch_and_store_pagespeed",
        lambda shop, urls, max_urls, site_url: calls.append((shop, urls, max_urls, site_url))
        or {"rows": 2},
    )

    result = asyncio.run(
        handle_pagespeed_import(
            {"urls": ["https://example.com"], "max_urls": 1, "site_url": "https://example.com"},
            "store.myshopify.com",
        )
    )

    assert result["rows"] == 2
    assert calls == [
        ("store.myshopify.com", ["https://example.com"], 1, "https://example.com")
    ]


# ── Helper ────────────────────────────────────────────────────────────────────


async def _run_one(worker: JobWorker) -> None:
    """Run a single worker iteration (claim + process one job)."""
    from app.jobs.store import claim_next

    job = claim_next(db_path=worker._db_path)
    if job:
        await worker._process(job)
