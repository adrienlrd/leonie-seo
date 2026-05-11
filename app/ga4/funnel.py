"""Organic funnel builder — joins GSC metrics with GA4 metrics per URL."""

from __future__ import annotations

from urllib.parse import urlparse


def _url_to_path(url: str) -> str:
    """Extract the path from a full URL, stripping trailing slash."""
    try:
        return urlparse(url).path.rstrip("/") or "/"
    except Exception:
        return url.rstrip("/")


def build_funnel(
    gsc_rows: dict[str, dict],
    ga4_rows: dict[str, dict],
) -> list[dict]:
    """Join GSC and GA4 data into a per-URL organic funnel.

    GSC provides: impressions, clicks, CTR, position (keyed by full URL).
    GA4 provides: sessions, conversions, revenue, conversion_rate (keyed by path).

    Args:
        gsc_rows: Dict[full_url, {clicks, impressions, ctr, position}].
        ga4_rows: Dict[page_path, {sessions, conversions, revenue, conversion_rate}].

    Returns:
        List of funnel dicts, one per URL, sorted by revenue desc then clicks desc.
        Each dict: url, path, impressions, clicks, ctr, position,
                   sessions, conversions, revenue, conversion_rate,
                   session_rate (sessions/clicks), has_ga4_data.
    """
    funnel: list[dict] = []

    for url, gsc in gsc_rows.items():
        path = _url_to_path(url)
        ga4 = ga4_rows.get(path, {})
        has_ga4 = bool(ga4)

        clicks = gsc.get("clicks", 0)
        sessions = ga4.get("sessions", 0)
        session_rate = round(sessions / clicks, 4) if clicks > 0 else 0.0

        funnel.append(
            {
                "url": url,
                "path": path,
                # GSC
                "impressions": gsc.get("impressions", 0),
                "clicks": clicks,
                "ctr": round(gsc.get("ctr", 0.0), 4),
                "position": round(gsc.get("position", 0.0), 2),
                # GA4
                "sessions": sessions,
                "conversions": ga4.get("conversions", 0),
                "revenue": ga4.get("revenue", 0.0),
                "conversion_rate": ga4.get("conversion_rate", 0.0),
                # Derived
                "session_rate": session_rate,
                "has_ga4_data": has_ga4,
            }
        )

    # Sort: revenue desc, then clicks desc for pages with no GA4 data
    funnel.sort(key=lambda r: (-r["revenue"], -r["clicks"]))
    return funnel


def summarize_funnel(funnel: list[dict]) -> dict:
    """Compute aggregate totals across all funnel rows.

    Args:
        funnel: Output of build_funnel().

    Returns:
        Dict with total impressions, clicks, sessions, conversions, revenue,
        and average CTR, position, conversion_rate for rows that have GA4 data.
    """
    total_impressions = sum(r["impressions"] for r in funnel)
    total_clicks = sum(r["clicks"] for r in funnel)
    total_sessions = sum(r["sessions"] for r in funnel)
    total_conversions = sum(r["conversions"] for r in funnel)
    total_revenue = round(sum(r["revenue"] for r in funnel), 2)
    urls_with_ga4 = sum(1 for r in funnel if r["has_ga4_data"])

    avg_position = (
        round(sum(r["position"] for r in funnel) / len(funnel), 2) if funnel else 0.0
    )
    overall_conv_rate = (
        round(total_conversions / total_sessions, 4) if total_sessions > 0 else 0.0
    )
    overall_session_rate = (
        round(total_sessions / total_clicks, 4) if total_clicks > 0 else 0.0
    )

    return {
        "urls_total": len(funnel),
        "urls_with_ga4_data": urls_with_ga4,
        "total_impressions": total_impressions,
        "total_clicks": total_clicks,
        "total_sessions": total_sessions,
        "total_conversions": total_conversions,
        "total_revenue": total_revenue,
        "avg_position": avg_position,
        "overall_conversion_rate": overall_conv_rate,
        "overall_session_rate": overall_session_rate,
    }
