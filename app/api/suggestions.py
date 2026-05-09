"""Suggestion endpoints — serve generated SEO suggestions to the frontend."""

import json
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import ShopContext, get_shop_context

router = APIRouter(prefix="/api", tags=["suggestions"])

_PROJECT_ROOT = Path(__file__).parents[2]
_DEFAULT_RAW_DIR = _PROJECT_ROOT / "data" / "raw"


def _suggestions_path(ctx: ShopContext, filename: str) -> Path:
    """Resolve the per-shop raw suggestion file."""
    # OAuth shops use a per-shop subdirectory; primary tenant uses the legacy flat layout
    candidate_per_shop = _DEFAULT_RAW_DIR / ctx.shop / filename
    if candidate_per_shop.exists():
        return candidate_per_shop
    return _DEFAULT_RAW_DIR / filename


@router.get("/shops/{shop}/suggestions/meta")
async def get_meta_suggestions(
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
) -> list[dict]:
    """Return cached meta suggestions produced by generate_suggestions.

    Returns an empty list if no suggestions have been generated yet — this
    is not an error, just a hint to the frontend to display the empty state.
    """
    path = _suggestions_path(ctx, "meta_suggestions.json")
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text())
    except (json.JSONDecodeError, OSError) as exc:
        raise HTTPException(status_code=500, detail=f"Suggestions unreadable: {exc}") from exc
    return data if isinstance(data, list) else []
