"""In-memory job store for async market analysis runs."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

_jobs: dict[str, dict[str, Any]] = {}


def create_job(shop: str) -> str:
    job_id = str(uuid.uuid4())
    _jobs[job_id] = {
        "job_id": job_id,
        "shop": shop,
        "status": "pending",
        "created_at": datetime.now(UTC).isoformat(),
        "progress": 0,
        "total": 0,
        "products": [],
        "analyzed_at": None,
        "active_product_count": 0,
        "analyzed_product_count": 0,
        "total_opportunity_count": 0,
        "sources_used": [],
        "error": None,
    }
    return job_id


def get_job(job_id: str) -> dict[str, Any] | None:
    return _jobs.get(job_id)


def update_job(job_id: str, **kwargs: Any) -> None:
    if job_id in _jobs:
        _jobs[job_id].update(kwargs)
