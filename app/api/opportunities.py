"""Opportunities API — ranked product opportunities from 7 deterministic signals."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query

from app.api.audit import _load_crawl_findings, _load_snapshot, _snapshot_age_days
from app.api.deps import ShopContext, get_shop_context
from app.impact.report import _find_gsc_file, _parse_gsc_csv
from app.niche.understanding import get_validated_niche_hypothesis
from app.opportunities.finder import find_opportunities_for_catalog

router = APIRouter(prefix="/api", tags=["opportunities"])

_DATA_DIR = Path(__file__).parents[2] / "data" / "raw"


def _load_gsc_query_rows(shop: str) -> list[dict[str, Any]]:
    """Load query-level GSC JSON export for a shop (gsc_*.json)."""
    shop_dir = _DATA_DIR / shop
    if not shop_dir.exists():
        return []
    candidates = sorted(shop_dir.glob("gsc_*.json"), reverse=True)
    for path in candidates:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            raw_rows = data if isinstance(data, list) else data.get("rows", [])
            normalised: list[dict[str, Any]] = []
            for row in raw_rows:
                if not isinstance(row, dict):
                    continue
                keys = row.get("keys")
                query = row.get("query") or (keys[0] if isinstance(keys, list) and keys else "")
                normalised.append({
                    "query": query,
                    "impressions": row.get("impressions", 0),
                    "clicks": row.get("clicks", 0),
                    "position": row.get("position", row.get("avg_position", 0)),
                })
            return normalised
        except (json.JSONDecodeError, OSError, KeyError, IndexError):
            continue
    return []


@router.get("/shops/{shop}/opportunities")
async def get_opportunities(
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
    scope: str = Query(default="active", pattern="^(active|draft|unlisted|archived|all)$"),
    top: int = Query(default=20, ge=1, le=100),
    intent: str | None = None,
) -> dict:
    """Return ranked product opportunities from 7 deterministic signals."""
    snapshot = _load_snapshot(ctx)
    products = snapshot.get("products", [])
    shop_info = snapshot.get("shop")
    shop_domain = shop_info.get("domain", ctx.shop) if isinstance(shop_info, dict) else ctx.shop

    niche_hypothesis = get_validated_niche_hypothesis(ctx.shop)
    crawl_findings = _load_crawl_findings(ctx.shop)

    gsc_page_rows: dict[str, dict[str, Any]] = {}
    gsc_path = _find_gsc_file(ctx.shop)
    if gsc_path:
        try:
            gsc_page_rows = _parse_gsc_csv(gsc_path.read_text(encoding="utf-8"))
        except OSError:
            pass

    gsc_query_rows = _load_gsc_query_rows(ctx.shop)

    result = find_opportunities_for_catalog(
        products,
        shop_domain,
        gsc_page_rows,
        gsc_query_rows,
        niche_hypothesis=niche_hypothesis,
        crawl_findings=crawl_findings if crawl_findings else None,
        scope=scope,
        top=top,
    )

    if intent:
        result["opportunities"] = [
            opp for opp in result["opportunities"]
            if intent in opp.get("matched_intents", [])
        ]

    age = _snapshot_age_days(snapshot)
    return {
        **result,
        "shop": ctx.shop,
        "snapshot_age_days": age,
        "generated_at": datetime.now(UTC).isoformat(),
    }
