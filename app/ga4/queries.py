"""Pre-built GA4 queries for organic traffic analysis."""

from __future__ import annotations

from app.ga4.client import GA4Client, parse_report


def get_organic_by_page(
    client: GA4Client,
    *,
    days: int = 30,
) -> dict[str, dict]:
    """Fetch organic search sessions, conversions, and revenue grouped by page path.

    Filters to sessionDefaultChannelGroup = "Organic Search" only.

    Args:
        client: Authenticated GA4Client instance.
        days: Lookback window in days (default 30). GA4 max is 3650.

    Returns:
        Dict keyed by page path (e.g. "/products/harnais-premium"):
        {sessions, conversions, revenue, conversion_rate}
    """
    body = {
        "dimensions": [{"name": "pagePath"}],
        "metrics": [
            {"name": "sessions"},
            {"name": "conversions"},
            {"name": "totalRevenue"},
        ],
        "dateRanges": [{"startDate": f"{days}daysAgo", "endDate": "yesterday"}],
        "dimensionFilter": {
            "filter": {
                "fieldName": "sessionDefaultChannelGroup",
                "stringFilter": {
                    "matchType": "EXACT",
                    "value": "Organic Search",
                    "caseSensitive": False,
                },
            }
        },
        "limit": 1000,
        "orderBys": [{"metric": {"metricName": "sessions"}, "desc": True}],
    }

    response = client.run_report(body)
    rows = parse_report(response)

    result: dict[str, dict] = {}
    for row in rows:
        path = row.get("pagePath", "")
        if not path:
            continue
        sessions = int(row.get("sessions", 0))
        conversions = int(row.get("conversions", 0))
        revenue = round(float(row.get("totalRevenue", 0.0)), 2)
        conv_rate = round(conversions / sessions, 4) if sessions > 0 else 0.0
        result[path] = {
            "sessions": sessions,
            "conversions": conversions,
            "revenue": revenue,
            "conversion_rate": conv_rate,
        }

    return result
