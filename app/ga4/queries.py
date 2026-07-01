"""Pre-built GA4 queries for organic traffic analysis."""

from __future__ import annotations

from app.ga4.client import GA4Client, parse_report

# Referral hostnames GA4 reports as `sessionSource` for AI assistants. Used to
# split "AI clicks" out of the Referral channel. Curated, extend as new
# assistants send traffic. Matched case-insensitively as an exact host list.
AI_SOURCE_DOMAINS: tuple[str, ...] = (
    "chatgpt.com",
    "chat.openai.com",
    "openai.com",
    "perplexity.ai",
    "gemini.google.com",
    "bard.google.com",
    "copilot.microsoft.com",
    "claude.ai",
    "you.com",
    "poe.com",
)


def _parse_daily_by_path(rows: list[dict], metric: str = "sessions") -> dict[str, dict[str, int]]:
    """Fold GA4 rows carrying `date` + `pagePath` into {path: {iso_date: value}}."""
    result: dict[str, dict[str, int]] = {}
    for row in rows:
        path = row.get("pagePath", "")
        raw_date = row.get("date", "")
        if not path or len(raw_date) != 8 or not raw_date.isdigit():
            continue
        iso_date = f"{raw_date[0:4]}-{raw_date[4:6]}-{raw_date[6:8]}"
        bucket = result.setdefault(path, {})
        bucket[iso_date] = bucket.get(iso_date, 0) + int(row.get(metric, 0))
    return result


def get_organic_by_page_daily(
    client: GA4Client,
    *,
    start_date: str,
    end_date: str = "today",
) -> dict[str, dict[str, int]]:
    """Organic-search sessions grouped by page path AND day, over [start,end].

    Filters to sessionDefaultChannelGroup = "Organic Search" (Google/Bing).

    Args:
        client: Authenticated GA4Client.
        start_date: ISO ``YYYY-MM-DD`` (or GA4 relative like ``28daysAgo``).
        end_date: ISO date or GA4 keyword (default ``today``).

    Returns:
        ``{page_path: {iso_date: sessions}}``.
    """
    body = {
        "dimensions": [{"name": "date"}, {"name": "pagePath"}],
        "metrics": [{"name": "sessions"}],
        "dateRanges": [{"startDate": start_date, "endDate": end_date}],
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
        "limit": 100000,
    }
    return _parse_daily_by_path(parse_report(client.run_report(body)))


def get_ai_referrals_by_page_daily(
    client: GA4Client,
    *,
    start_date: str,
    end_date: str = "today",
) -> dict[str, dict[str, int]]:
    """AI-assistant referral sessions grouped by page path AND day.

    Filters `sessionSource` to :data:`AI_SOURCE_DOMAINS`. Undercounts because
    many AI assistants send no referrer (those land in Direct), but captures
    the click-throughs that do carry an AI host.

    Returns:
        ``{page_path: {iso_date: sessions}}``.
    """
    body = {
        "dimensions": [{"name": "date"}, {"name": "pagePath"}],
        "metrics": [{"name": "sessions"}],
        "dateRanges": [{"startDate": start_date, "endDate": end_date}],
        "dimensionFilter": {
            "filter": {
                "fieldName": "sessionSource",
                "inListFilter": {
                    "values": list(AI_SOURCE_DOMAINS),
                    "caseSensitive": False,
                },
            }
        },
        "limit": 100000,
    }
    return _parse_daily_by_path(parse_report(client.run_report(body)))


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


def get_organic_daily(
    client: GA4Client,
    *,
    days: int = 90,
) -> dict[str, dict]:
    """Fetch organic sessions, conversions and revenue grouped by day.

    Used by the progress curve dashboard (task 120) to render time-series
    over the validation window.

    Filters to sessionDefaultChannelGroup = "Organic Search" only.

    Args:
        client: Authenticated GA4Client instance.
        days: Lookback window in days (default 90). GA4 max is 3650.

    Returns:
        Dict keyed by ISO date (``YYYY-MM-DD``):
        {sessions, conversions, revenue}
    """
    body = {
        "dimensions": [{"name": "date"}],
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
        "limit": 3650,
        "orderBys": [{"dimension": {"dimensionName": "date"}}],
    }

    response = client.run_report(body)
    rows = parse_report(response)

    result: dict[str, dict] = {}
    for row in rows:
        raw_date = row.get("date", "")
        if not raw_date or len(raw_date) != 8 or not raw_date.isdigit():
            continue
        iso_date = f"{raw_date[0:4]}-{raw_date[4:6]}-{raw_date[6:8]}"
        result[iso_date] = {
            "sessions": int(row.get("sessions", 0)),
            "conversions": int(row.get("conversions", 0)),
            "revenue": round(float(row.get("totalRevenue", 0.0)), 2),
        }

    return result
