"""In-memory job store and file-based result persistence for market analysis."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_jobs: dict[str, dict[str, Any]] = {}

_DATA_DIR = Path(__file__).parents[2] / "data" / "raw"


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


def save_latest_result(shop: str, data: dict[str, Any]) -> None:
    """Persist the latest completed analysis to disk so it survives page navigation."""
    try:
        shop_dir = _DATA_DIR / shop
        shop_dir.mkdir(parents=True, exist_ok=True)
        (shop_dir / "market_analysis_latest.json").write_text(
            json.dumps(data, ensure_ascii=False),
            encoding="utf-8",
        )
    except OSError:
        pass


def load_latest_result(shop: str) -> dict[str, Any] | None:
    """Load the last persisted analysis result for a shop, or None if unavailable."""
    path = _DATA_DIR / shop / "market_analysis_latest.json"
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def save_identifications(shop: str, data: dict[str, str]) -> None:
    """Persist merchant-validated product labels {product_id: label} to disk."""
    try:
        shop_dir = _DATA_DIR / shop
        shop_dir.mkdir(parents=True, exist_ok=True)
        (shop_dir / "market_analysis_identifications.json").write_text(
            json.dumps(data, ensure_ascii=False), encoding="utf-8"
        )
    except OSError:
        pass


def load_identifications(shop: str) -> dict[str, str]:
    """Load persisted product labels, or {} if none exist."""
    path = _DATA_DIR / shop / "market_analysis_identifications.json"
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def save_identification_job(shop: str, data: dict[str, Any]) -> None:
    """Persist the latest AI identification job result to disk."""
    try:
        shop_dir = _DATA_DIR / shop
        shop_dir.mkdir(parents=True, exist_ok=True)
        (shop_dir / "market_analysis_identification_job.json").write_text(
            json.dumps(data, ensure_ascii=False), encoding="utf-8"
        )
    except OSError:
        pass


def load_identification_job(shop: str) -> dict[str, Any] | None:
    """Load the last persisted identification job result, or None."""
    path = _DATA_DIR / shop / "market_analysis_identification_job.json"
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
