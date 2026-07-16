"""Audit endpoints — issues, SEO score, and unified readiness from cached crawl data."""

from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import ShopContext, get_shop_context
from app.api.snapshot_store import load_snapshot_from_file_or_db
from app.db_adapter import DB_PATH, get_conn
from app.geo.readiness import score_catalog_readiness
from app.managed_products import filter_snapshot_products
from app.niche.understanding import get_validated_niche_hypothesis
from app.snapshot.scope import normalize_product_scope
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
_SNAPSHOT_STALE_DAYS = 7


def _load_crawl_findings(shop: str, db_path: Path | None = None) -> list[dict[str, Any]]:
    path = db_path if db_path is not None else DB_PATH
    with get_conn(path) as conn:
        rows = conn.execute(
            """
            SELECT url, issue_type, severity, detail, metadata_json
            FROM crawl_findings
            WHERE shop = ?
            ORDER BY created_at DESC
            LIMIT 500
            """,
            (shop,),
        ).fetchall()
    return list(rows)


def _snapshot_age_days(snapshot: dict[str, Any]) -> int | None:
    date_str = snapshot.get("snapshot_date") or snapshot.get("crawled_at")
    if not date_str:
        return None
    try:
        snapshot_dt = datetime.fromisoformat(str(date_str))
        if snapshot_dt.tzinfo is None:
            snapshot_dt = snapshot_dt.replace(tzinfo=UTC)
        delta = datetime.now(UTC) - snapshot_dt
        return max(0, delta.days)
    except (ValueError, TypeError):
        return None


def _validated_scope(scope: str) -> str:
    try:
        return normalize_product_scope(scope)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


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
    # The app only works on the merchant's managed selection — every consumer
    # of this loader (audit, dashboard, GEO, market analysis…) sees it applied.
    return filter_snapshot_products(ctx.shop, snapshot)


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


@router.get("/shops/{shop}/audit/readiness")
async def get_audit_readiness(
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
    scope: str = Query(default="active", pattern="^(active|draft|unlisted|archived|all)$"),
    top: int = Query(default=50, ge=1, le=200),
) -> dict:
    """Return unified AI Search Readiness audit: global score, niche alerts, crawl health, per-product breakdown."""
    snapshot = _load_snapshot(ctx)
    products = snapshot.get("products", [])

    niche_hypothesis = get_validated_niche_hypothesis(ctx.shop)
    crawl_findings = _load_crawl_findings(ctx.shop)

    age = _snapshot_age_days(snapshot)
    analysis = score_catalog_readiness(
        products,
        top=top,
        scope=_validated_scope(scope),
        niche_hypothesis=niche_hypothesis,
        crawl_findings=crawl_findings if crawl_findings else None,
    )

    return {
        "shop": ctx.shop,
        "snapshot_age_days": age,
        "snapshot_freshness_warning": age is not None and age > _SNAPSHOT_STALE_DAYS,
        "generated_at": datetime.now(UTC).isoformat(),
        **analysis,
    }


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
