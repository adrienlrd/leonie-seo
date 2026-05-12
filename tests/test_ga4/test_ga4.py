"""Tests for GA4 client, queries, and funnel builder."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.ga4.client import GA4Client, parse_report
from app.ga4.funnel import _url_to_path, build_funnel, summarize_funnel
from app.ga4.queries import get_organic_by_page

# ── parse_report ──────────────────────────────────────────────────────────────


def _make_response(dim_names: list[str], met_names: list[str], rows: list[list]) -> dict:
    return {
        "dimensionHeaders": [{"name": n} for n in dim_names],
        "metricHeaders": [{"name": n} for n in met_names],
        "rows": [
            {
                "dimensionValues": [{"value": str(v)} for v in row[: len(dim_names)]],
                "metricValues": [{"value": str(v)} for v in row[len(dim_names) :]],
            }
            for row in rows
        ],
    }


def test_parse_report_returns_flat_dicts():
    resp = _make_response(
        ["pagePath"],
        ["sessions", "conversions", "totalRevenue"],
        [["/products/harnais", 120, 5, 250.0]],
    )
    rows = parse_report(resp)
    assert len(rows) == 1
    assert rows[0]["pagePath"] == "/products/harnais"
    assert rows[0]["sessions"] == 120.0
    assert rows[0]["totalRevenue"] == 250.0


def test_parse_report_empty_response():
    rows = parse_report({})
    assert rows == []


def test_parse_report_no_rows():
    resp = _make_response(["pagePath"], ["sessions"], [])
    assert parse_report(resp) == []


def test_parse_report_invalid_metric_value_defaults_to_zero():
    resp = {
        "dimensionHeaders": [{"name": "pagePath"}],
        "metricHeaders": [{"name": "sessions"}],
        "rows": [{"dimensionValues": [{"value": "/x"}], "metricValues": [{"value": "N/A"}]}],
    }
    rows = parse_report(resp)
    assert rows[0]["sessions"] == 0.0


def test_parse_report_multiple_rows():
    resp = _make_response(
        ["pagePath"],
        ["sessions"],
        [["/a", 10], ["/b", 20], ["/c", 5]],
    )
    rows = parse_report(resp)
    assert len(rows) == 3
    assert rows[1]["pagePath"] == "/b"


# ── _url_to_path ──────────────────────────────────────────────────────────────


def test_url_to_path_full_url():
    assert _url_to_path("https://example.com/products/harnais") == "/products/harnais"


def test_url_to_path_trailing_slash_stripped():
    assert _url_to_path("https://example.com/collections/chiens/") == "/collections/chiens"


def test_url_to_path_root():
    assert _url_to_path("https://example.com/") == "/"


def test_url_to_path_bare_path():
    assert _url_to_path("/products/harnais") == "/products/harnais"


# ── build_funnel ──────────────────────────────────────────────────────────────


def _gsc(clicks=100, impressions=1000, ctr=0.10, position=5.0):
    return {"clicks": clicks, "impressions": impressions, "ctr": ctr, "position": position}


def _ga4(sessions=80, conversions=4, revenue=200.0):
    cr = round(conversions / sessions, 4) if sessions > 0 else 0.0
    return {
        "sessions": sessions,
        "conversions": conversions,
        "revenue": revenue,
        "conversion_rate": cr,
    }


def test_build_funnel_joins_gsc_and_ga4():
    gsc_rows = {"https://example.com/products/harnais": _gsc()}
    ga4_rows = {"/products/harnais": _ga4()}
    funnel = build_funnel(gsc_rows, ga4_rows)
    assert len(funnel) == 1
    row = funnel[0]
    assert row["clicks"] == 100
    assert row["sessions"] == 80
    assert row["revenue"] == 200.0
    assert row["has_ga4_data"] is True


def test_build_funnel_missing_ga4_data():
    gsc_rows = {"https://example.com/collections/chats": _gsc(clicks=50)}
    ga4_rows = {}
    funnel = build_funnel(gsc_rows, ga4_rows)
    assert funnel[0]["has_ga4_data"] is False
    assert funnel[0]["sessions"] == 0
    assert funnel[0]["revenue"] == 0.0


def test_build_funnel_session_rate_computed():
    gsc_rows = {"https://example.com/products/p": _gsc(clicks=100)}
    ga4_rows = {"/products/p": _ga4(sessions=80)}
    funnel = build_funnel(gsc_rows, ga4_rows)
    assert funnel[0]["session_rate"] == pytest.approx(0.8, rel=1e-3)


def test_build_funnel_session_rate_zero_clicks():
    gsc_rows = {"https://example.com/products/p": _gsc(clicks=0)}
    ga4_rows = {"/products/p": _ga4(sessions=10)}
    funnel = build_funnel(gsc_rows, ga4_rows)
    assert funnel[0]["session_rate"] == 0.0


def test_build_funnel_sorted_by_revenue_desc():
    gsc_rows = {
        "https://example.com/a": _gsc(clicks=10),
        "https://example.com/b": _gsc(clicks=20),
    }
    ga4_rows = {
        "/a": _ga4(revenue=500.0),
        "/b": _ga4(revenue=100.0),
    }
    funnel = build_funnel(gsc_rows, ga4_rows)
    assert funnel[0]["path"] == "/a"


def test_build_funnel_sorted_by_clicks_when_no_revenue():
    gsc_rows = {
        "https://example.com/a": _gsc(clicks=5),
        "https://example.com/b": _gsc(clicks=50),
    }
    ga4_rows = {}
    funnel = build_funnel(gsc_rows, ga4_rows)
    assert funnel[0]["path"] == "/b"


# ── summarize_funnel ──────────────────────────────────────────────────────────


def test_summarize_funnel_totals():
    funnel = [
        {
            "impressions": 1000,
            "clicks": 100,
            "sessions": 80,
            "conversions": 4,
            "revenue": 200.0,
            "position": 3.0,
            "has_ga4_data": True,
            "session_rate": 0.8,
            "ctr": 0.1,
            "conversion_rate": 0.05,
        },
        {
            "impressions": 500,
            "clicks": 30,
            "sessions": 20,
            "conversions": 1,
            "revenue": 50.0,
            "position": 7.0,
            "has_ga4_data": True,
            "session_rate": 0.67,
            "ctr": 0.06,
            "conversion_rate": 0.05,
        },
    ]
    summary = summarize_funnel(funnel)
    assert summary["total_impressions"] == 1500
    assert summary["total_clicks"] == 130
    assert summary["total_sessions"] == 100
    assert summary["total_conversions"] == 5
    assert summary["total_revenue"] == 250.0
    assert summary["urls_with_ga4_data"] == 2


def test_summarize_funnel_empty():
    summary = summarize_funnel([])
    assert summary["total_impressions"] == 0
    assert summary["avg_position"] == 0.0
    assert summary["overall_conversion_rate"] == 0.0


def test_summarize_funnel_overall_rates():
    funnel = [
        {
            "impressions": 100,
            "clicks": 50,
            "sessions": 40,
            "conversions": 2,
            "revenue": 100.0,
            "position": 4.0,
            "has_ga4_data": True,
            "session_rate": 0.8,
            "ctr": 0.5,
            "conversion_rate": 0.05,
        },
    ]
    summary = summarize_funnel(funnel)
    assert summary["overall_session_rate"] == pytest.approx(0.8, rel=1e-3)
    assert summary["overall_conversion_rate"] == pytest.approx(0.05, rel=1e-3)


# ── get_organic_by_page ───────────────────────────────────────────────────────


def test_get_organic_by_page_calls_run_report():
    client = MagicMock()
    client.run_report.return_value = _make_response(
        ["pagePath"],
        ["sessions", "conversions", "totalRevenue"],
        [["/products/harnais", 120, 5, 250.0]],
    )
    result = get_organic_by_page(client, days=30)
    assert "/products/harnais" in result
    row = result["/products/harnais"]
    assert row["sessions"] == 120
    assert row["revenue"] == 250.0
    assert row["conversion_rate"] == pytest.approx(5 / 120, rel=1e-3)


def test_get_organic_by_page_skips_empty_path():
    client = MagicMock()
    client.run_report.return_value = _make_response(
        ["pagePath"],
        ["sessions", "conversions", "totalRevenue"],
        [["", 10, 0, 0.0], ["/valid", 5, 0, 0.0]],
    )
    result = get_organic_by_page(client)
    assert "" not in result
    assert "/valid" in result


def test_get_organic_by_page_zero_sessions_no_division():
    client = MagicMock()
    client.run_report.return_value = _make_response(
        ["pagePath"],
        ["sessions", "conversions", "totalRevenue"],
        [["/page", 0, 0, 0.0]],
    )
    result = get_organic_by_page(client)
    assert result["/page"]["conversion_rate"] == 0.0


# ── Async + token caching (lot 4 wave 2) ─────────────────────────────────────


def test_client_with_injected_token_reuses_it_across_calls():
    """A pre-injected token must be reused without ever touching google-auth."""
    client = GA4Client(property_id="123", token="injected-tok-123")
    assert client._bearer() == "injected-tok-123"
    assert client._bearer() == "injected-tok-123"
    assert client._creds is None  # no service-account exchange happened


def test_run_report_uses_injected_token_in_authorization_header():
    """Verify the Bearer token is set on the Authorization header."""
    client = GA4Client(property_id="123", token="injected-tok-123")
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"rows": []}
    with patch("httpx.post", return_value=mock_resp) as post_mock:
        client.run_report({"dimensions": [{"name": "pagePath"}]})
    headers = post_mock.call_args.kwargs["headers"]
    assert headers["Authorization"] == "Bearer injected-tok-123"


def test_run_report_async_uses_async_httpx_client():
    """The async variant must hit httpx.AsyncClient — not block on httpx.post.

    Uses anyio.from_thread.start_blocking_portal so the test doesn't tear down
    the asyncio default loop (which other tests in the suite still read via
    the deprecated low-level event loop API).
    """
    import httpx
    from anyio.from_thread import start_blocking_portal

    client = GA4Client(property_id="456", token="async-tok")
    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"rows": []}

    captured = {"headers": None}

    class _FakeAsyncClient:
        def __init__(self, *a, **kw):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return None

        async def post(self, url, json=None, headers=None):
            captured["headers"] = headers
            return mock_resp

    with patch("app.ga4.client.httpx.AsyncClient", _FakeAsyncClient):
        with start_blocking_portal() as portal:
            result = portal.call(
                client.run_report_async,
                {"dimensions": [{"name": "pagePath"}]},
            )
    assert result == {"rows": []}
    assert captured["headers"]["Authorization"] == "Bearer async-tok"
