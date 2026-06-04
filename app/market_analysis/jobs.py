"""In-memory job store and file-based result persistence for market analysis."""

from __future__ import annotations

import json
import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from app.paths import data_dir

logger = logging.getLogger(__name__)

_jobs: dict[str, dict[str, Any]] = {}

_DATA_DIR = data_dir()
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


def save_merchant_facts(shop: str, product_id: str, facts: dict[str, str]) -> dict[str, str]:
    """Persist merchant-confirmed product facts used for grounded content generation."""
    stored = load_merchant_facts(shop)
    cleaned = {
        str(key): str(value).strip()[:500] for key, value in facts.items() if str(value).strip()
    }
    merged = {**stored.get(product_id, {}), **cleaned}
    stored[product_id] = merged
    try:
        shop_dir = _DATA_DIR / shop
        shop_dir.mkdir(parents=True, exist_ok=True)
        (shop_dir / "market_analysis_merchant_facts.json").write_text(
            json.dumps(stored, ensure_ascii=False), encoding="utf-8"
        )
    except OSError as exc:
        logger.error("Failed to save merchant facts for %s: %s", shop, exc)
    return merged


def load_merchant_facts(shop: str) -> dict[str, dict[str, str]]:
    """Load merchant-confirmed facts, excluding malformed persisted entries."""
    path = _DATA_DIR / shop / "market_analysis_merchant_facts.json"
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(raw, dict):
        return {}
    stored: dict[str, dict[str, str]] = {}
    for product_id, product_facts in raw.items():
        if not isinstance(product_facts, dict):
            continue
        stored[str(product_id)] = {
            str(key): str(value).strip()[:500]
            for key, value in product_facts.items()
            if isinstance(value, str) and value.strip()
        }
    return stored


def _write_json_file(shop: str, filename: str, data: dict) -> None:
    try:
        shop_dir = _DATA_DIR / shop
        shop_dir.mkdir(parents=True, exist_ok=True)
        (shop_dir / filename).write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    except OSError as exc:
        logger.error("Failed to write %s for %s: %s", filename, shop, exc)


def load_retired_questions(shop: str) -> dict[str, list[str]]:
    """Load retired question keys per product."""
    path = _DATA_DIR / shop / "market_analysis_retired_questions.json"
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(raw, dict):
        return {}
    return {str(k): [str(v) for v in v_list if isinstance(v, str)] for k, v_list in raw.items() if isinstance(v_list, list)}


def retire_question(shop: str, product_id: str, key: str) -> None:
    """Mark a question key as retired for a given product."""
    stored = load_retired_questions(shop)
    keys = stored.get(product_id, [])
    if key not in keys:
        keys.append(key)
    stored[product_id] = keys
    _write_json_file(shop, "market_analysis_retired_questions.json", stored)


def restore_question(shop: str, product_id: str, key: str) -> None:
    """Remove the retired status from a question key."""
    stored = load_retired_questions(shop)
    stored[product_id] = [k for k in stored.get(product_id, []) if k != key]
    _write_json_file(shop, "market_analysis_retired_questions.json", stored)


def load_question_metadata(shop: str) -> dict[str, dict[str, dict]]:
    """Load persisted question metadata (text, placeholder, why_it_matters) per product."""
    path = _DATA_DIR / shop / "market_analysis_question_metadata.json"
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return raw if isinstance(raw, dict) else {}


def save_question_metadata(shop: str, product_id: str, questions: list[dict]) -> None:
    """Persist question metadata so retired questions can still be displayed."""
    stored = load_question_metadata(shop)
    stored[product_id] = {
        q["key"]: {
            "key": q["key"],
            "question": q.get("question", ""),
            "why_it_matters": q.get("why_it_matters", ""),
            "placeholder": q.get("placeholder", ""),
            "target_keyword": q.get("target_keyword", ""),
        }
        for q in questions
        if isinstance(q, dict) and q.get("key")
    }
    _write_json_file(shop, "market_analysis_question_metadata.json", stored)


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
        p for p in data.get("products", []) if str(p.get("product_id", "")) not in product_ids
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


def replace_product_analysis(
    shop: str,
    product_result: dict[str, Any],
    analyzed_at: str | None = None,
) -> bool:
    """Replace one persisted product analysis after a fact-enriched regeneration."""
    path = _DATA_DIR / shop / "market_analysis_latest.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False

    product_id = str(product_result.get("product_id", ""))
    products = data.get("products", [])
    if not isinstance(products, list):
        return False
    for index, product in enumerate(products):
        if str(product.get("product_id", "")) != product_id:
            continue
        products[index] = product_result
        if analyzed_at:
            data["analyzed_at"] = analyzed_at
        data["analyzed_product_count"] = len(products)
        data["total_opportunity_count"] = sum(
            len(item.get("seo_keywords", [])) + len(item.get("geo_questions", []))
            for item in products
            if isinstance(item, dict)
        )
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        return True
    return False
