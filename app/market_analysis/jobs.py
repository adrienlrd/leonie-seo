"""In-memory job store and file-based result persistence for market analysis."""

from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_jobs: dict[str, dict[str, Any]] = {}

_DATA_DIR = Path(os.environ.get("DATA_DIR", str(Path(__file__).parents[2] / "data" / "raw")))
logger.info("Market analysis data directory: %s", _DATA_DIR)


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
        dest = shop_dir / "market_analysis_latest.json"
        dest.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        logger.info("Analysis saved to %s (%d bytes)", dest, dest.stat().st_size)
    except OSError as exc:
        logger.error("Failed to save analysis for %s: %s", shop, exc)


def load_latest_result(shop: str) -> dict[str, Any] | None:
    """Load the last persisted analysis result for a shop, or None if unavailable."""
    path = _DATA_DIR / shop / "market_analysis_latest.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        logger.info("Analysis loaded from %s", path)
        return data
    except (OSError, json.JSONDecodeError) as exc:
        logger.info("No saved analysis for %s: %s", shop, exc)
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


def remove_products_from_analysis(shop: str, product_ids: set[str]) -> int:
    """Remove products from the persisted analysis by product_id. Returns count removed."""
    if not product_ids:
        return 0
    path = _DATA_DIR / shop / "market_analysis_latest.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return 0
    before = len(data.get("products", []))
    data["products"] = [
        p for p in data.get("products", [])
        if str(p.get("product_id", "")) not in product_ids
    ]
    removed = before - len(data["products"])
    if removed:
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return removed


def patch_product_proposals(shop: str, product_id: str, proposals: dict[str, Any]) -> bool:
    """Update content_test_pack fields for one product in the persisted analysis result.

    Returns True if the product was found and the file updated, False otherwise.
    """
    path = _DATA_DIR / shop / "market_analysis_latest.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False

    for product in data.get("products", []):
        if str(product.get("product_id", "")) == str(product_id):
            if "content_test_pack" not in product:
                product["content_test_pack"] = {}
            product["content_test_pack"].update(proposals)
            path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            return True
    return False
