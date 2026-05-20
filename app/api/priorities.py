"""Priorities API — 3-action priority dossiers from the opportunity catalog."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query

from app.api.audit import _load_crawl_findings, _load_snapshot, _snapshot_age_days
from app.api.deps import ShopContext, get_shop_context
from app.api.opportunities import _load_gsc_query_rows
from app.impact.report import _find_gsc_file, _parse_gsc_csv
from app.niche.understanding import get_validated_niche_hypothesis
from app.priorities.engine import build_priority_actions

router = APIRouter(prefix="/api", tags=["priorities"])


@router.get("/shops/{shop}/priorities")
async def get_priorities(
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
    scope: str = Query(default="active", pattern="^(active|draft|unlisted|archived|all)$"),
    plan: str = Query(default="free", pattern="^(free|pro|agency)$"),
) -> dict[str, Any]:
    """Return exactly 3 priority action dossiers for the shop.

    Uses a 4-step pipeline: opportunity finder → Risk Guard filter →
    deterministic pre-score → LLM arbitrage (pro/agency) or fallback (free).
    """
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

    result = build_priority_actions(
        products,
        shop_domain,
        ctx.shop,
        gsc_page_rows,
        gsc_query_rows,
        niche_hypothesis=niche_hypothesis,
        crawl_findings=crawl_findings if crawl_findings else None,
        scope=scope,
        llm_router=None,
        plan=plan,
    )

    age = _snapshot_age_days(snapshot)
    return {
        **result,
        "shop": ctx.shop,
        "snapshot_age_days": age,
    }
