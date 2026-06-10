"""In-memory job store and file-based result persistence for business profile."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from app.analysis_artifacts import load_artifact, save_artifact
from app.paths import data_dir

logger = logging.getLogger(__name__)

_DATA_DIR = data_dir()


def save_business_profile(shop: str, data: dict[str, Any], *, db_path: Path | None = None) -> None:
    """Persist validated business profile to disk."""
    shop_dir = _DATA_DIR / shop
    shop_dir.mkdir(parents=True, exist_ok=True)
    (shop_dir / "business_profile.json").write_text(
        json.dumps(data, ensure_ascii=False), encoding="utf-8"
    )
    save_artifact(shop, "business_profile", data, db_path=db_path)


def load_business_profile(shop: str, *, db_path: Path | None = None) -> dict[str, Any] | None:
    """Load the last persisted business profile for a shop, or None if unavailable."""
    path = _DATA_DIR / shop / "business_profile.json"
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return load_artifact(shop, "business_profile", db_path=db_path)


def save_business_profile_job(shop: str, data: dict[str, Any]) -> None:
    """Persist the latest business profile job result to disk."""
    shop_dir = _DATA_DIR / shop
    shop_dir.mkdir(parents=True, exist_ok=True)
    (shop_dir / "business_profile_job.json").write_text(
        json.dumps(data, ensure_ascii=False), encoding="utf-8"
    )


def load_business_profile_job(shop: str) -> dict[str, Any] | None:
    """Load the last persisted business profile job result, or None."""
    path = _DATA_DIR / shop / "business_profile_job.json"
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
