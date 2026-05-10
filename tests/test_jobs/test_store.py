"""Tests for job queue store — enqueue, claim, update, list."""

from __future__ import annotations

import pytest

from app.db import init_db
from app.jobs.store import claim_next, enqueue, get_job, list_jobs, update_job


@pytest.fixture()
def db(tmp_path):
    path = tmp_path / "test.db"
    init_db(path)
    return path


# ── enqueue ───────────────────────────────────────────────────────────────────


def test_enqueue_returns_uuid_string(db):
    job_id = enqueue("seo_audit", {"shop": "test.myshopify.com"}, db_path=db)
    assert isinstance(job_id, str)
    assert len(job_id) == 36  # UUID format


def test_enqueue_persists_job(db):
    job_id = enqueue("seo_audit", {"x": 1}, db_path=db)
    job = get_job(job_id, db_path=db)
    assert job is not None
    assert job["queue"] == "seo_audit"
    assert job["status"] == "pending"
    assert job["payload"] == {"x": 1}


def test_enqueue_default_values(db):
    job_id = enqueue("seo_audit", {}, db_path=db)
    job = get_job(job_id, db_path=db)
    assert job["retries"] == 0
    assert job["max_retries"] == 3
    assert job["priority"] == 0
    assert job["shop"] is None


def test_enqueue_with_shop_and_priority(db):
    job_id = enqueue("seo_audit", {}, shop="myshop.myshopify.com", priority=10, db_path=db)
    job = get_job(job_id, db_path=db)
    assert job["shop"] == "myshop.myshopify.com"
    assert job["priority"] == 10


def test_enqueue_delay_sets_future_scheduled_at(db):
    job_id = enqueue("seo_audit", {}, delay_seconds=3600, db_path=db)
    job = get_job(job_id, db_path=db)
    # scheduled_at must be in the future (not before now)
    from datetime import UTC, datetime

    scheduled = datetime.fromisoformat(job["scheduled_at"])
    assert scheduled > datetime.now(UTC)


# ── claim_next ────────────────────────────────────────────────────────────────


def test_claim_next_returns_pending_job(db):
    job_id = enqueue("seo_audit", {}, db_path=db)
    claimed = claim_next(db_path=db)
    assert claimed is not None
    assert claimed["id"] == job_id
    assert claimed["status"] == "running"


def test_claim_next_returns_none_when_empty(db):
    assert claim_next(db_path=db) is None


def test_claim_next_respects_priority_order(db):
    enqueue("seo_audit", {"p": 0}, priority=0, db_path=db)
    high_id = enqueue("seo_audit", {"p": 10}, priority=10, db_path=db)
    claimed = claim_next(db_path=db)
    assert claimed["id"] == high_id


def test_claim_next_skips_future_jobs(db):
    enqueue("seo_audit", {}, delay_seconds=9999, db_path=db)
    assert claim_next(db_path=db) is None


def test_claim_next_filters_by_queue(db):
    enqueue("other_queue", {}, db_path=db)
    enqueue("seo_audit", {}, db_path=db)
    claimed = claim_next(queue="seo_audit", db_path=db)
    assert claimed is not None
    assert claimed["queue"] == "seo_audit"


# ── update_job ────────────────────────────────────────────────────────────────


def test_update_job_status_completed(db):
    job_id = enqueue("seo_audit", {}, db_path=db)
    update_job(job_id, status="completed", result={"ok": True}, db_path=db)
    job = get_job(job_id, db_path=db)
    assert job["status"] == "completed"
    assert job["result"] == {"ok": True}
    assert job["completed_at"] is not None


def test_update_job_retry_increments_retries(db):
    job_id = enqueue("seo_audit", {}, db_path=db)
    update_job(job_id, status="pending", retries=1, result={"error": "boom"}, db_path=db)
    job = get_job(job_id, db_path=db)
    assert job["retries"] == 1
    assert job["status"] == "pending"


# ── list_jobs ─────────────────────────────────────────────────────────────────


def test_list_jobs_filters_by_shop(db):
    enqueue("seo_audit", {}, shop="a.myshopify.com", db_path=db)
    enqueue("seo_audit", {}, shop="b.myshopify.com", db_path=db)
    jobs = list_jobs(shop="a.myshopify.com", db_path=db)
    assert len(jobs) == 1
    assert jobs[0]["shop"] == "a.myshopify.com"


def test_list_jobs_filters_by_status(db):
    j1 = enqueue("seo_audit", {}, db_path=db)
    update_job(j1, status="completed", db_path=db)
    enqueue("seo_audit", {}, db_path=db)  # pending
    jobs = list_jobs(status="completed", db_path=db)
    assert len(jobs) == 1
    assert jobs[0]["status"] == "completed"


def test_list_jobs_respects_limit(db):
    for _ in range(5):
        enqueue("seo_audit", {}, db_path=db)
    jobs = list_jobs(limit=3, db_path=db)
    assert len(jobs) == 3
