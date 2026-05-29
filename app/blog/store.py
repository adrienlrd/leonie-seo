"""Persistent store for blog drafts (one JSON file per shop).

Drafts live on the merchant's data directory (persistent disk on Render Starter),
so the editor survives page refreshes and sleeps. A draft tracks the full editable
state plus the Shopify article id once published, so the listing page can show
which posts have already been pushed to Shopify.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from app.paths import data_dir

logger = logging.getLogger(__name__)


def _drafts_path(shop: str):
    path = data_dir() / shop / "blog_drafts.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _load_all(shop: str) -> dict[str, dict[str, Any]]:
    path = _drafts_path(shop)
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("blog_drafts.json corrupted for %s: %s", shop, exc)
        return {}


def _write_all(shop: str, drafts: dict[str, dict[str, Any]]) -> None:
    _drafts_path(shop).write_text(
        json.dumps(drafts, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _now() -> str:
    return datetime.now(UTC).isoformat()


def list_drafts(shop: str) -> list[dict[str, Any]]:
    """Return drafts ordered by most-recently-updated first."""
    drafts = list(_load_all(shop).values())
    drafts.sort(key=lambda d: d.get("updated_at", ""), reverse=True)
    return drafts


def get_draft(shop: str, draft_id: str) -> dict[str, Any] | None:
    return _load_all(shop).get(draft_id)


def save_draft(shop: str, draft: dict[str, Any]) -> dict[str, Any]:
    """Upsert a draft. Generates an id on create; bumps ``updated_at`` on every save."""
    drafts = _load_all(shop)
    draft = dict(draft)
    if not draft.get("id"):
        draft["id"] = uuid.uuid4().hex
        draft.setdefault("created_at", _now())
        draft.setdefault("status", "draft")
    draft["updated_at"] = _now()
    drafts[draft["id"]] = draft
    _write_all(shop, drafts)
    return draft


def delete_draft(shop: str, draft_id: str) -> bool:
    drafts = _load_all(shop)
    if draft_id not in drafts:
        return False
    drafts.pop(draft_id)
    _write_all(shop, drafts)
    return True
