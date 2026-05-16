"""ICE priority matrix API endpoint for embedded Shopify workflows."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Any

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import ShopContext, get_shop_context
from app.api.snapshot_store import load_snapshot_from_file_or_db
from scripts.models import Issue, Severity
from scripts.report.ice_matrix import build_ice_matrix, score_issue

router = APIRouter(tags=["ice"])

_DATA_DIR = Path(__file__).parents[2] / "data" / "raw"

_SEVERITY_MAP: dict[str, Severity] = {
    "critical": Severity.CRITICAL,
    "high": Severity.HIGH,
    "medium": Severity.MEDIUM,
    "low": Severity.LOW,
    "info": Severity.INFO,
}


def _load_gsc_df(shop: str) -> pd.DataFrame:
    path = _DATA_DIR / shop / "gsc_performance.csv"
    if path.exists():
        try:
            return pd.read_csv(path)
        except Exception:
            pass
    return pd.DataFrame()


def _load_crawl_issues(shop: str) -> list[dict[str, Any]]:
    path = _DATA_DIR / shop / "crawl_report.json"
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text(encoding="utf-8")).get("issues", [])
    except Exception:
        return []


def _crawl_issue_to_model(ci: dict[str, Any]) -> Issue:
    resource_type = "redirect" if "redirect" in ci.get("issue_type", "") else "page"
    severity = _SEVERITY_MAP.get(ci.get("severity", "info"), Severity.INFO)
    return Issue(
        resource_type=resource_type,
        resource_id=ci["url"],
        resource_title=ci["url"],
        issue_type=ci["issue_type"],
        severity=severity,
        current_value=None,
        detail=ci.get("detail", ""),
    )


@router.get("/api/shops/{shop}/audit/ice")
async def get_ice_matrix(
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
    top: int = 20,
) -> list[dict]:
    """Return the ICE priority matrix for a shop, sorted by score descending.

    Combines Shopify snapshot issues and crawl CSV issues.
    Scores each issue by Impact × Confidence / Effort, boosted by GSC data when available.
    """
    snapshot = load_snapshot_from_file_or_db(ctx.shop, ctx.snapshot_path)
    if snapshot is None:
        raise HTTPException(
            status_code=404,
            detail="No crawl data found. Run an SEO audit first.",
        )

    products = snapshot.get("products", [])
    collections = snapshot.get("collections", [])
    gsc_df = _load_gsc_df(ctx.shop)

    matrix = build_ice_matrix(products, collections, gsc_df)

    crawl_issues = _load_crawl_issues(ctx.shop)
    for ci in crawl_issues:
        try:
            issue = _crawl_issue_to_model(ci)
            url = ci.get("url")
            matrix.append(score_issue(issue, url, gsc_df))
        except Exception:
            continue

    matrix.sort(key=lambda r: r["ice_score"], reverse=True)
    return matrix[:top]
