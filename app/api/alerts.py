"""Merchant alerts — aggregate CWV, 404, CTR drops, LLM budget, and job failures."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query

from app.api.deps import ShopContext, get_shop_context

router = APIRouter(prefix="/api", tags=["alerts"])

_PROJECT_ROOT = Path(__file__).parents[2]


# ---------------------------------------------------------------------------
# Alert builders
# ---------------------------------------------------------------------------


def _pagespeed_alerts(shop: str) -> list[dict[str, Any]]:
    """Return CWV/performance alerts from the latest PageSpeed import."""
    try:
        from app.pagespeed.client import latest_pagespeed_status

        status = latest_pagespeed_status(shop)
    except Exception:  # noqa: BLE001
        return []
    if not status.get("available"):
        return []
    alerts = []
    for row in status.get("alerts", []):
        severity = row.get("severity", "warning")
        alerts.append(
            {
                "type": "cwv",
                "severity": severity,
                "message": f"PageSpeed bas ({row['strategy']}) — {row['url']}",
                "detail": f"Score performance : {round(row['performance_score'] * 100)}%",
                "url": row.get("url"),
            }
        )
    return alerts


def _crawl_404_alerts(shop: str) -> list[dict[str, Any]]:
    """Return page-404 alerts from the latest crawl report."""
    try:
        from app.crawl.client import latest_crawl_status

        status = latest_crawl_status(shop)
    except Exception:  # noqa: BLE001
        return []
    if not status.get("available"):
        return []
    return [
        {
            "type": "crawl_404",
            "severity": "critical",
            "message": f"Page 404 détectée — {issue.get('url', '')}",
            "detail": issue.get("detail", ""),
            "url": issue.get("url"),
        }
        for issue in status.get("issues", [])
        if issue.get("issue_type") == "page_404"
    ]


def _gsc_ctr_alerts(shop: str, *, min_impressions: int = 100, max_ctr: float = 0.01) -> list[dict[str, Any]]:
    """Return low-CTR alerts from the cached GSC performance CSV."""
    try:
        from app.impact.report import _find_gsc_file, _parse_gsc_csv

        gsc_file = _find_gsc_file(shop)
        if gsc_file is None:
            return []
        rows = _parse_gsc_csv(gsc_file.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return []
    alerts = []
    for url, data in rows.items():
        if data.get("impressions", 0) >= min_impressions and data.get("ctr", 1) < max_ctr:
            alerts.append(
                {
                    "type": "low_ctr",
                    "severity": "warning",
                    "message": f"CTR faible ({data['ctr']:.1%}) — {url}",
                    "detail": f"{data['impressions']} impressions, position {data['position']:.1f}",
                    "url": url,
                }
            )
    return alerts[:10]


def _budget_alert(shop: str, budget_usd: float) -> list[dict[str, Any]]:
    """Return LLM budget alert if spend is >= 80% of the configured ceiling."""
    try:
        from app.observability.metrics import check_budget

        result = check_budget(shop, budget_usd)
    except Exception:  # noqa: BLE001
        return []
    if not result.get("alert"):
        return []
    severity = "critical" if result.get("over_budget") else "warning"
    return [
        {
            "type": "llm_budget",
            "severity": severity,
            "message": result["alert"],
            "detail": f"${result['spent_usd']:.4f} dépensé sur ${result['budget_usd']:.2f}",
            "url": None,
        }
    ]


def _failed_jobs_alerts(shop: str, *, limit: int = 5) -> list[dict[str, Any]]:
    """Return recent failed job alerts."""
    try:
        from app.jobs.store import list_jobs

        jobs = list_jobs(shop=shop, status="failed", limit=limit)
    except Exception:  # noqa: BLE001
        return []
    return [
        {
            "type": "job_failed",
            "severity": "error",
            "message": f"Job échoué — {job.get('queue', 'inconnu')}",
            "detail": (job.get("error") or "")[:200],
            "url": None,
            "job_id": job.get("id"),
        }
        for job in jobs
    ]


# ---------------------------------------------------------------------------
# Route
# ---------------------------------------------------------------------------


@router.get("/shops/{shop}/alerts/summary")
async def get_alerts_summary(
    shop: str,
    ctx: Annotated[ShopContext, Depends(get_shop_context)],
    budget_usd: Annotated[float, Query(gt=0)] = 10.0,
) -> dict:
    """Return aggregated merchant alerts across all signal sources.

    Aggregates:
    - CWV / PageSpeed performance regressions
    - 404 pages from the latest technical crawl
    - Low-CTR pages from GSC data (>= 100 impressions, CTR < 1%)
    - LLM budget warnings (>= 80% of monthly ceiling)
    - Recent failed background jobs

    Args:
        shop: Shopify shop domain.
        budget_usd: Monthly LLM budget ceiling in USD (default $10).
    """
    alerts: list[dict[str, Any]] = []
    alerts.extend(_pagespeed_alerts(ctx.shop))
    alerts.extend(_crawl_404_alerts(ctx.shop))
    alerts.extend(_gsc_ctr_alerts(ctx.shop))
    alerts.extend(_budget_alert(ctx.shop, budget_usd))
    alerts.extend(_failed_jobs_alerts(ctx.shop))

    by_severity: dict[str, int] = {}
    for a in alerts:
        sev = a.get("severity", "info")
        by_severity[sev] = by_severity.get(sev, 0) + 1

    return {
        "shop": ctx.shop,
        "total": len(alerts),
        "by_severity": by_severity,
        "alerts": alerts,
    }
