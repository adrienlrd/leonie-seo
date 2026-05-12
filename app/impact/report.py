"""Impact report builder — reads seo_changes + GSC data, computes ROI estimates."""

from __future__ import annotations

import csv
import io
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.db_adapter import DB_PATH, get_conn
from app.impact.calculator import aggregate_impact, compute_url_impact


def _load_seo_changes(
    shop: str,
    days: int,
    *,
    db_path: Path | None = None,
) -> list[dict]:
    """Read applied seo_changes from the last `days` days, filtered by shop.

    Rows with NULL shop (pre-migration legacy data) are excluded — they can't
    be confidently attributed to a tenant in a multi-tenant deployment.
    """
    path = db_path or DB_PATH
    cutoff = (datetime.now(UTC) - timedelta(days=days)).isoformat()

    with get_conn(path) as conn:
        rows = conn.execute(
            """SELECT resource_type, resource_id, field, old_value, new_value, applied_at
               FROM seo_changes
               WHERE status = 'applied' AND shop = ? AND applied_at >= ?
               ORDER BY applied_at DESC""",
            (shop, cutoff),
        ).fetchall()

    return [dict(r) for r in rows]


def _parse_gsc_csv(csv_text: str) -> dict[str, dict]:
    """Parse GSC CSV into a dict keyed by URL.

    Expected columns: url, clicks, impressions, ctr, position
    """
    result: dict[str, dict] = {}
    reader = csv.DictReader(io.StringIO(csv_text))
    for row in reader:
        url = row.get("url", "").rstrip("/")
        if not url:
            continue
        try:
            result[url] = {
                "clicks": int(float(row.get("clicks", 0))),
                "impressions": int(float(row.get("impressions", 0))),
                "ctr": float(row.get("ctr", 0)),
                "position": float(row.get("position", 0)),
            }
        except (ValueError, TypeError):
            continue
    return result


def _find_gsc_file(shop: str) -> Path | None:
    """Locate the per-shop GSC performance CSV.

    Multi-tenant: only the shop-specific path is checked. The legacy global
    fallback (`data/raw/gsc_performance.csv`) was removed in the lot 4 wave 1
    audit fix — it leaked one tenant's GSC data to all other tenants.
    """
    project_root = Path(__file__).parents[2]
    path = project_root / "data" / "raw" / shop / "gsc_performance.csv"
    return path if path.exists() else None


def _product_url(shop_domain: str, handle: str) -> str:
    return f"https://{shop_domain}/products/{handle}"


def _collection_url(shop_domain: str, handle: str) -> str:
    return f"https://{shop_domain}/collections/{handle}"


def build_impact_report(
    shop: str,
    snapshot: dict,
    *,
    days: int = 30,
    position_improvement: float = 2.0,
    conversion_rate: float = 0.02,
    aov: float = 50.0,
    db_path: Path | None = None,
    gsc_csv_text: str | None = None,
) -> dict:
    """Build the full SEO impact report for a shop.

    Args:
        shop: Shopify shop domain.
        snapshot: Crawl snapshot dict (products, collections, shop).
        days: Lookback window for seo_changes (default 30).
        position_improvement: Assumed SERP position gain from changes (default 2).
        conversion_rate: Organic conversion rate for revenue estimate.
        aov: Average order value for revenue estimate.
        db_path: SQLite override (tests only).
        gsc_csv_text: Pre-loaded GSC CSV string (tests only; otherwise read from disk).

    Returns:
        Aggregated impact report dict.
    """
    # Load GSC data
    if gsc_csv_text is not None:
        gsc = _parse_gsc_csv(gsc_csv_text)
    else:
        gsc_file = _find_gsc_file(shop)
        gsc = _parse_gsc_csv(gsc_file.read_text()) if gsc_file else {}

    # Load applied changes (filtered by shop — multi-tenant safe)
    changes_rows = _load_seo_changes(shop, days, db_path=db_path)

    # Group changes by resource
    by_resource: dict[str, list[dict]] = defaultdict(list)
    for row in changes_rows:
        key = f"{row['resource_type']}:{row['resource_id']}"
        by_resource[key].append(
            {
                "field": row["field"],
                "old_value": row["old_value"],
                "new_value": row["new_value"],
                "applied_at": row["applied_at"],
            }
        )

    # Build resource lookup from snapshot
    shop_domain = snapshot.get("shop", {}).get("domain", shop)
    products = {str(p["id"]): p for p in snapshot.get("products", [])}
    collections = {str(c["id"]): c for c in snapshot.get("collections", [])}

    impacts = []
    for key, changes in by_resource.items():
        rtype, rid = key.split(":", 1)
        if rtype == "product" and rid in products:
            p = products[rid]
            url = _product_url(shop_domain, p.get("handle", ""))
            title = p.get("title", "")
        elif rtype == "collection" and rid in collections:
            c = collections[rid]
            url = _collection_url(shop_domain, c.get("handle", ""))
            title = c.get("title", "")
        else:
            # Resource not in snapshot — use stub
            url = ""
            title = f"{rtype} #{rid}"

        url_key = url.rstrip("/")
        gsc_row = gsc.get(url_key, {})
        impressions = gsc_row.get("impressions", 0)
        position_current = gsc_row.get("position", 0.0)

        if position_current <= 0 and impressions == 0:
            # No GSC data — still include in report with zero metrics
            position_current = 20.0  # outside top 10, conservative

        impact = compute_url_impact(
            rtype,
            rid,
            url,
            title,
            changes,
            impressions,
            position_current,
            position_improvement=position_improvement,
            conversion_rate=conversion_rate,
            aov=aov,
        )
        impacts.append(impact)

    report = aggregate_impact(impacts, conversion_rate=conversion_rate, aov=aov)
    report["meta"] = {
        "shop": shop,
        "days": days,
        "position_improvement_assumption": position_improvement,
        "gsc_data_available": bool(gsc),
    }
    return report
