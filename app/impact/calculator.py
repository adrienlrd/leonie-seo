"""Impact calculator — CTR curve, per-URL impact, aggregate ROI.

All results are estimates. Position improvement is derived from the
position_improvement_estimate parameter (default: 2 positions gained).
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Standard organic CTR curve (Sistrix / Advanced Web Ranking composite, desktop FR)
_CTR_BY_POSITION: dict[int, float] = {
    1: 0.316,
    2: 0.158,
    3: 0.095,
    4: 0.065,
    5: 0.049,
    6: 0.038,
    7: 0.029,
    8: 0.023,
    9: 0.018,
    10: 0.015,
}

_CTR_DECAY_BASE = 0.015  # CTR at position 10, used for decay beyond


def estimate_ctr(position: float) -> float:
    """Return estimated organic CTR for a given average SERP position.

    Args:
        position: Average SERP position (1.0 = top). Positions <= 0 return 0.

    Returns:
        CTR as a fraction (e.g. 0.316 for position 1).
    """
    if position <= 0:
        return 0.0
    pos_int = max(1, round(position))
    if pos_int <= 10:
        return _CTR_BY_POSITION[pos_int]
    # Exponential decay beyond position 10
    return max(0.001, _CTR_DECAY_BASE * (0.75 ** (pos_int - 10)))


@dataclass
class URLImpact:
    """Estimated SEO impact for a single modified URL."""

    resource_type: str
    resource_id: str
    url: str
    title: str
    changes: list[dict] = field(default_factory=list)
    impressions: int = 0
    position_before: float = 0.0
    position_after: float = 0.0
    ctr_before: float = 0.0
    ctr_after: float = 0.0
    clicks_before: float = 0.0
    clicks_after: float = 0.0
    clicks_gained: float = 0.0
    revenue_estimate: float = 0.0
    estimated: bool = True  # always True — these are projections


def compute_url_impact(
    resource_type: str,
    resource_id: str,
    url: str,
    title: str,
    changes: list[dict],
    impressions: int,
    position_current: float,
    *,
    position_improvement: float = 2.0,
    conversion_rate: float = 0.02,
    aov: float = 50.0,
) -> URLImpact:
    """Compute estimated impact for a single URL.

    Args:
        resource_type: "product" or "collection".
        resource_id: Shopify resource ID.
        url: Full URL (e.g. https://shop.com/products/handle).
        title: Resource title.
        changes: List of change dicts (field, old_value, new_value, applied_at).
        impressions: GSC impressions for this URL (current period).
        position_current: GSC average position (current, i.e. after changes).
        position_improvement: Assumed position gain from SEO changes (default 2).
        conversion_rate: Fraction of organic clicks that convert (default 2%).
        aov: Average order value in currency units (default €50).

    Returns:
        URLImpact with estimated clicks gained and revenue.
    """
    position_before = position_current + position_improvement
    position_after = position_current

    ctr_before = estimate_ctr(position_before)
    ctr_after = estimate_ctr(position_after)

    clicks_before = impressions * ctr_before
    clicks_after = impressions * ctr_after
    clicks_gained = max(0.0, clicks_after - clicks_before)
    revenue_estimate = clicks_gained * conversion_rate * aov

    return URLImpact(
        resource_type=resource_type,
        resource_id=resource_id,
        url=url,
        title=title,
        changes=changes,
        impressions=impressions,
        position_before=round(position_before, 2),
        position_after=round(position_after, 2),
        ctr_before=round(ctr_before, 4),
        ctr_after=round(ctr_after, 4),
        clicks_before=round(clicks_before, 1),
        clicks_after=round(clicks_after, 1),
        clicks_gained=round(clicks_gained, 1),
        revenue_estimate=round(revenue_estimate, 2),
    )


def aggregate_impact(impacts: list[URLImpact], *, conversion_rate: float, aov: float) -> dict:
    """Aggregate a list of URLImpact into a summary report dict.

    Args:
        impacts: Per-URL impact objects.
        conversion_rate: Conversion rate used (included for context).
        aov: Average order value used (included for context).

    Returns:
        Dict with summary totals and per-URL detail list.
    """
    total_clicks_gained = sum(i.clicks_gained for i in impacts)
    total_revenue = sum(i.revenue_estimate for i in impacts)
    urls_with_gsc = sum(1 for i in impacts if i.impressions > 0)

    return {
        "summary": {
            "urls_changed": len(impacts),
            "urls_with_gsc_data": urls_with_gsc,
            "total_clicks_gained_estimate": round(total_clicks_gained, 1),
            "total_revenue_estimate": round(total_revenue, 2),
            "conversion_rate": conversion_rate,
            "average_order_value": aov,
            "estimated": True,
        },
        "by_url": [
            {
                "url": i.url,
                "title": i.title,
                "resource_type": i.resource_type,
                "resource_id": i.resource_id,
                "changes_count": len(i.changes),
                "changes": i.changes,
                "impressions": i.impressions,
                "position_before": i.position_before,
                "position_after": i.position_after,
                "ctr_before": i.ctr_before,
                "ctr_after": i.ctr_after,
                "clicks_gained": i.clicks_gained,
                "revenue_estimate": i.revenue_estimate,
            }
            for i in sorted(impacts, key=lambda x: x.revenue_estimate, reverse=True)
        ],
    }
