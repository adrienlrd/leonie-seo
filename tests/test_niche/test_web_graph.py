"""Tests for CC-Index web graph client and brand signals."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from app.niche.brand_signals import compare_competitor_coverage, search_brand_in_urls
from app.niche.web_graph import CCIndexClient, WebGraphError

# ── helpers ───────────────────────────────────────────────────────────────────


def _ndjson(*records: dict) -> str:
    return "\n".join(json.dumps(r) for r in records)


def _page(url: str, status: str = "200") -> dict:
    return {"url": url, "timestamp": "20240315120000", "status": status, "mime": "text/html"}


def _mock_response(text: str, status_code: int = 200) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    resp.text = text
    resp.json.return_value = json.loads(text) if text.startswith("[") else {}
    return resp


# ── get_latest_crawl ──────────────────────────────────────────────────────────


def test_get_latest_crawl_returns_first_id():
    client = CCIndexClient()
    collinfo = [{"id": "CC-MAIN-2024-18"}, {"id": "CC-MAIN-2024-10"}]
    with patch("httpx.get", return_value=_mock_response(json.dumps(collinfo))):
        assert client.get_latest_crawl() == "CC-MAIN-2024-18"


def test_get_latest_crawl_cached():
    client = CCIndexClient(cached_crawl="CC-MAIN-2024-18")
    with patch("httpx.get") as mock_get:
        result = client.get_latest_crawl()
        mock_get.assert_not_called()
    assert result == "CC-MAIN-2024-18"


def test_get_latest_crawl_raises_on_http_error():
    client = CCIndexClient()
    with patch("httpx.get", return_value=_mock_response("", 503)):
        with pytest.raises(WebGraphError, match="HTTP 503"):
            client.get_latest_crawl()


def test_get_latest_crawl_raises_on_request_error():
    import httpx as _httpx

    client = CCIndexClient()
    with patch("httpx.get", side_effect=_httpx.ConnectError("timeout")):
        with pytest.raises(WebGraphError, match="unreachable"):
            client.get_latest_crawl()


# ── query_domain ──────────────────────────────────────────────────────────────


def test_query_domain_parses_ndjson():
    client = CCIndexClient(cached_crawl="CC-MAIN-2024-18")
    body = _ndjson(
        _page("https://miacara.com/"),
        _page("https://miacara.com/products/harnais"),
    )
    with patch("httpx.get", return_value=_mock_response(body)):
        pages = client.query_domain("miacara.com")
    assert len(pages) == 2
    assert pages[0].url == "https://miacara.com/"
    assert pages[1].status == "200"


def test_query_domain_returns_empty_on_404():
    client = CCIndexClient(cached_crawl="CC-MAIN-2024-18")
    with patch("httpx.get", return_value=_mock_response("", 404)):
        assert client.query_domain("unknown-domain.com") == []


def test_query_domain_skips_error_records():
    client = CCIndexClient(cached_crawl="CC-MAIN-2024-18")
    body = _ndjson(
        {"error": "No records found"},
        _page("https://miacara.com/blog"),
    )
    with patch("httpx.get", return_value=_mock_response(body)):
        pages = client.query_domain("miacara.com")
    assert len(pages) == 1
    assert pages[0].url == "https://miacara.com/blog"


def test_query_domain_skips_malformed_lines():
    client = CCIndexClient(cached_crawl="CC-MAIN-2024-18")
    body = "not-json\n" + json.dumps(_page("https://miacara.com/"))
    with patch("httpx.get", return_value=_mock_response(body)):
        pages = client.query_domain("miacara.com")
    assert len(pages) == 1


# ── count_domain_pages ────────────────────────────────────────────────────────


def test_count_domain_pages_returns_length():
    client = CCIndexClient(cached_crawl="CC-MAIN-2024-18")
    body = _ndjson(*[_page(f"https://miacara.com/p/{i}") for i in range(5)])
    with patch("httpx.get", return_value=_mock_response(body)):
        assert client.count_domain_pages("miacara.com") == 5


# ── get_url_patterns ──────────────────────────────────────────────────────────


def test_get_url_patterns_groups_by_prefix():
    client = CCIndexClient(cached_crawl="CC-MAIN-2024-18")
    body = _ndjson(
        _page("https://miacara.com/products/a"),
        _page("https://miacara.com/products/b"),
        _page("https://miacara.com/collections/c"),
        _page("https://miacara.com/"),
    )
    with patch("httpx.get", return_value=_mock_response(body)):
        patterns = client.get_url_patterns("miacara.com")
    assert patterns["/products"] == 2
    assert patterns["/collections"] == 1
    assert patterns["/"] == 1


def test_get_url_patterns_sorted_desc():
    client = CCIndexClient(cached_crawl="CC-MAIN-2024-18")
    body = _ndjson(
        _page("https://x.com/blog/a"),
        _page("https://x.com/blog/b"),
        _page("https://x.com/blog/c"),
        _page("https://x.com/products/d"),
    )
    with patch("httpx.get", return_value=_mock_response(body)):
        patterns = client.get_url_patterns("x.com")
    keys = list(patterns.keys())
    assert keys[0] == "/blog"


# ── search_brand_in_urls ──────────────────────────────────────────────────────


def test_search_brand_in_urls_deduplicates():
    client = CCIndexClient(cached_crawl="CC-MAIN-2024-18")
    body = _ndjson(
        _page("https://blog.com/leoniedelacroix-review"),
        _page("https://blog.com/leoniedelacroix-review"),  # duplicate
        _page("https://other.com/leoniedelacroix"),
    )
    with patch("httpx.get", return_value=_mock_response(body)):
        urls = search_brand_in_urls(client, "leoniedelacroix")
    assert len(urls) == 2


def test_search_brand_in_urls_returns_empty_on_error():
    client = CCIndexClient(cached_crawl="CC-MAIN-2024-18")
    with patch("httpx.get", return_value=_mock_response("", 404)):
        urls = search_brand_in_urls(client, "leoniedelacroix")
    assert urls == []


# ── compare_competitor_coverage ───────────────────────────────────────────────


def test_compare_competitor_coverage_sorted_desc():
    client = CCIndexClient(cached_crawl="CC-MAIN-2024-18")
    call_count = [0]

    def fake_get(url, **kwargs):
        call_count[0] += 1
        params = kwargs.get("params", {})
        domain_pattern = params.get("url", "")
        if "miacara" in domain_pattern:
            return _mock_response(_ndjson(*[_page(f"https://miacara.com/{i}") for i in range(10)]))
        return _mock_response(_ndjson(*[_page(f"https://zara.com/{i}") for i in range(3)]))

    with patch("httpx.get", side_effect=fake_get):
        result = compare_competitor_coverage(client, ["miacara.com", "zara.com"])

    assert list(result.keys())[0] == "miacara.com"
    assert result["miacara.com"] == 10
    assert result["zara.com"] == 3


def test_compare_competitor_coverage_skips_empty_domains():
    client = CCIndexClient(cached_crawl="CC-MAIN-2024-18")
    with patch("httpx.get", return_value=_mock_response(_ndjson(_page("https://a.com/")))):
        result = compare_competitor_coverage(client, ["a.com", "  ", ""])
    assert "" not in result
    assert "a.com" in result
