"""Audit endpoints — issues and SEO score from cached crawl data."""

from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import ShopContext, get_shop_context
from app.api.snapshot_store import load_snapshot_from_file_or_db
from scripts.audit.detect_issues import (
    detect_alt_text_issues,
    detect_duplicate_content,
    detect_meta_description_issues,
    detect_meta_title_issues,
)
from scripts.models import Issue, SEOScore
from scripts.report.generate_report import calculate_score

router = APIRouter(prefix="/api", tags=["audit"])

_PROJECT_ROOT = Path(__file__).parents[2]
_RULES_PATH = str(_PROJECT_ROOT / "config" / "seo_rules.yaml")


def _load_snapshot(ctx: ShopContext) -> dict[str, Any]:
    try:
        snapshot = load_snapshot_from_file_or_db(ctx.shop, ctx.snapshot_path)
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    if snapshot is None:
        raise HTTPException(
            status_code=404,
            detail="No crawl data found. Run 'leonie-seo audit crawl' first.",
        )
    return snapshot


def _detect_all_issues(snapshot: dict[str, Any]) -> list[Issue]:
    products = snapshot.get("products", [])
    collections = snapshot.get("collections", [])

    issues: list[Issue] = []
    issues += detect_meta_title_issues(products, "product", _RULES_PATH)
    issues += detect_meta_title_issues(collections, "collection", _RULES_PATH)
    issues += detect_meta_description_issues(products, "product", _RULES_PATH)
    issues += detect_meta_description_issues(collections, "collection", _RULES_PATH)
    issues += detect_alt_text_issues(products, _RULES_PATH)
    issues += detect_duplicate_content(products)
    return issues


@router.get("/shops/{shop}/audit/issues")
async def get_issues(
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
    severity: str | None = None,
    resource_type: str | None = None,
) -> list[dict]:
    """Return all SEO issues from the last crawl, optionally filtered by severity or resource type."""
    snapshot = _load_snapshot(ctx)
    issues = _detect_all_issues(snapshot)

    if severity:
        issues = [i for i in issues if i.severity == severity]
    if resource_type:
        issues = [i for i in issues if i.resource_type == resource_type]

    return [i.model_dump() for i in issues]


@router.get("/shops/{shop}/audit/score")
async def get_score(ctx: Annotated[ShopContext, Depends(get_shop_context)]) -> dict:
    """Return the SEO score (0–100) from the last crawl."""
    snapshot = _load_snapshot(ctx)

    products = snapshot.get("products", [])
    collections = snapshot.get("collections", [])
    total_resources = len(products) + len(collections)
    total_images = sum(len((p.get("images") or {}).get("edges", [])) for p in products)

    issues = _detect_all_issues(snapshot)
    score: SEOScore = calculate_score(
        issues=issues,
        total_resources=total_resources,
        total_images=total_images,
        rules_path=_RULES_PATH,
    )
    return score.model_dump()
