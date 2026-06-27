"""Per-shop reusable blog authors.

Authors are created once and selected at publish time, instead of retyping the
name/bio/URL (and an E-E-A-T bio) on every article. Stored on the merchant data
directory plus the artifact DB, mirroring the merchant-facts store.
"""

from __future__ import annotations

import json
import logging
import uuid
from pathlib import Path
from typing import Any

from app.analysis_artifacts import load_artifact, save_artifact
from app.paths import data_dir

logger = logging.getLogger(__name__)

_DATA_DIR = data_dir()
_FILENAME = "blog_authors.json"
_ARTIFACT = "blog_authors"


def _clean_author(raw: dict[str, Any]) -> dict[str, str]:
    return {
        "id": str(raw.get("id") or "").strip(),
        "name": str(raw.get("name") or "").strip()[:120],
        "bio": str(raw.get("bio") or "").strip()[:600],
        "url": str(raw.get("url") or "").strip()[:300],
    }


def load_authors(shop: str, *, db_path: Path | None = None) -> list[dict[str, str]]:
    """Return the shop's saved authors, newest first, skipping malformed entries."""
    path = _DATA_DIR / shop / _FILENAME
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        raw = load_artifact(shop, _ARTIFACT, db_path=db_path)
    if not isinstance(raw, list):
        return []
    return [_clean_author(a) for a in raw if isinstance(a, dict) and str(a.get("name") or "").strip()]


def _persist(shop: str, authors: list[dict[str, str]], *, db_path: Path | None = None) -> None:
    try:
        shop_dir = _DATA_DIR / shop
        shop_dir.mkdir(parents=True, exist_ok=True)
        (shop_dir / _FILENAME).write_text(json.dumps(authors, ensure_ascii=False), encoding="utf-8")
    except OSError as exc:
        logger.error("Failed to save blog authors for %s: %s", shop, exc)
    save_artifact(shop, _ARTIFACT, authors, db_path=db_path)


def save_author(
    shop: str, author: dict[str, Any], *, db_path: Path | None = None
) -> dict[str, str]:
    """Create or update one author (matched by id) and return the stored record."""
    cleaned = _clean_author(author)
    if not cleaned["name"]:
        raise ValueError("author name is required")
    if not cleaned["id"]:
        cleaned["id"] = uuid.uuid4().hex
    authors = load_authors(shop, db_path=db_path)
    existing = next((a for a in authors if a["id"] == cleaned["id"]), None)
    if existing:
        existing.update(cleaned)
    else:
        authors.insert(0, cleaned)
    _persist(shop, authors, db_path=db_path)
    return cleaned


def delete_author(shop: str, author_id: str, *, db_path: Path | None = None) -> bool:
    """Remove an author by id. Returns True if one was removed."""
    authors = load_authors(shop, db_path=db_path)
    remaining = [a for a in authors if a["id"] != author_id]
    if len(remaining) == len(authors):
        return False
    _persist(shop, remaining, db_path=db_path)
    return True
