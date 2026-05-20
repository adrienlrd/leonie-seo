"""Tests for crawl API endpoints."""

from __future__ import annotations

from io import BytesIO
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.crawl.mini import MiniCrawlResult
from app.crawl.sitemap import SitemapUrl
from app.main import app

HEADERS = {
    "X-Leonie-Shop": "store.myshopify.com",
    "X-Internal-Secret": "internal",
    "X-Shopify-Access-Token": "shpat_test",
}

ENV = {
    "SHOPIFY_STORE_DOMAIN": "store.myshopify.com",
    "SHOPIFY_ACCESS_TOKEN": "shpat_test",
    "SHOPIFY_CLIENT_ID": "client_id",
    "SHOPIFY_CLIENT_SECRET": "client_secret",
    "SHOPIFY_SCOPES": "read_products",
    "APP_URL": "https://app.example.com",
    "INTERNAL_API_SECRET": "internal",
}

_OVERVIEW_CSV = (
    "Address,Title 1,Meta Description 1,Status Code,Indexability,Canonical Link Element 1\n"
    "https://example.com/a,Title A,Desc A,200,Indexable,https://example.com/a\n"
    "https://example.com/b,Title B,Desc B,200,Indexable,https://example.com/b\n"
    "https://example.com/missing,Title C,Desc C,404,Non-Indexable,\n"
)


def test_crawl_status_returns_not_available_when_no_report(monkeypatch) -> None:
    monkeypatch.setenv("INTERNAL_API_SECRET", "internal")
    with (
        patch.dict("os.environ", ENV),
        patch(
            "app.api.crawl.latest_crawl_status",
            return_value={
                "available": False,
                "url_count": 0,
                "issue_count": 0,
                "by_severity": {},
                "issues": [],
                "imported_at": None,
            },
        ),
    ):
        resp = TestClient(app).get("/api/shops/store.myshopify.com/crawl/status", headers=HEADERS)

    assert resp.status_code == 200
    body = resp.json()
    assert body["shop"] == "store.myshopify.com"
    assert body["available"] is False


def test_crawl_status_returns_report_when_available(monkeypatch) -> None:
    monkeypatch.setenv("INTERNAL_API_SECRET", "internal")
    with (
        patch.dict("os.environ", ENV),
        patch(
            "app.api.crawl.latest_crawl_status",
            return_value={
                "available": True,
                "url_count": 42,
                "issue_count": 3,
                "by_severity": {"critical": 1},
                "issues": [],
                "imported_at": "2026-05-16T10:00:00+00:00",
            },
        ),
    ):
        resp = TestClient(app).get("/api/shops/store.myshopify.com/crawl/status", headers=HEADERS)

    assert resp.status_code == 200
    body = resp.json()
    assert body["available"] is True
    assert body["url_count"] == 42
    assert body["issue_count"] == 3


def test_crawl_upload_processes_csv_and_stores_report(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("INTERNAL_API_SECRET", "internal")
    monkeypatch.setattr("app.crawl.client._DATA_DIR", tmp_path)

    with patch.dict("os.environ", ENV):
        resp = TestClient(app).post(
            "/api/shops/store.myshopify.com/crawl/upload",
            headers=HEADERS,
            files={"overview": ("overview.csv", BytesIO(_OVERVIEW_CSV.encode()), "text/csv")},
        )

    assert resp.status_code == 202
    body = resp.json()
    assert body["shop"] == "store.myshopify.com"
    assert body["url_count"] == 3
    assert body["issue_count"] >= 1
    assert "critical" in body["by_severity"]
    shop_dir = tmp_path / "store.myshopify.com"
    assert (shop_dir / "crawl_report.json").exists()


def test_crawl_upload_with_redirects_csv(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("INTERNAL_API_SECRET", "internal")
    monkeypatch.setattr("app.crawl.client._DATA_DIR", tmp_path)

    redirects_csv = (
        "Address,Redirect URL,Status Code,Redirect Chain Length\n"
        "https://example.com/old,,301,2\n"
    )

    with patch.dict("os.environ", ENV):
        resp = TestClient(app).post(
            "/api/shops/store.myshopify.com/crawl/upload",
            headers=HEADERS,
            files={
                "overview": ("overview.csv", BytesIO(_OVERVIEW_CSV.encode()), "text/csv"),
                "redirects": ("redirects.csv", BytesIO(redirects_csv.encode()), "text/csv"),
            },
        )

    assert resp.status_code == 202
    issue_types = [i["issue_type"] for i in resp.json()["issues"]]
    assert "redirect_chain" in issue_types


def test_crawl_upload_requires_overview_file(monkeypatch) -> None:
    monkeypatch.setenv("INTERNAL_API_SECRET", "internal")
    with patch.dict("os.environ", ENV):
        resp = TestClient(app).post(
            "/api/shops/store.myshopify.com/crawl/upload",
            headers=HEADERS,
        )

    assert resp.status_code == 422


def test_crawl_l3_runs_native_crawl_without_screaming_frog(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("INTERNAL_API_SECRET", "internal")
    snapshot = {
        "shop": {"primaryDomain": {"url": "https://example.com"}},
        "products": [{"id": "p1", "title": "A", "handle": "a"}],
        "collections": [],
        "pages": [],
        "articles": [],
    }

    class _Robots:
        sitemaps = ["https://example.com/sitemap.xml"]

        def can_fetch(self, url: str) -> bool:
            return True

    with (
        patch.dict("os.environ", ENV),
        patch("app.api.crawl.load_snapshot_from_file_or_db", return_value=snapshot),
        patch("app.api.crawl.fetch_robots_txt", return_value=_Robots()),
        patch(
            "app.api.crawl.fetch_sitemap_urls",
            return_value=[
                SitemapUrl("https://example.com/"),
                SitemapUrl("https://example.com/products/a"),
            ],
        ),
        patch(
            "app.api.crawl.crawl_urls",
            return_value=[
                MiniCrawlResult(
                    url="https://example.com/products/a",
                    allowed_by_robots=True,
                    status_code=200,
                    canonical="https://example.com/products/a",
                    jsonld_valid=True,
                )
            ],
        ),
        patch("app.api.crawl.store_crawl_findings", return_value=0),
        patch(
            "app.api.crawl.store_crawl_report",
            return_value=(tmp_path / "crawl_report.json", tmp_path / "crawl_report_1.json"),
        ),
    ):
        resp = TestClient(app).post(
            "/api/shops/store.myshopify.com/crawl/l3?max_urls=5&throttle_seconds=0",
            headers=HEADERS,
        )

    assert resp.status_code == 202
    body = resp.json()
    assert body["source"] == "crawl_l3"
    assert body["url_count"] >= 1
    assert body["sitemap_url_count"] == 2
    assert body["mini_crawl_url_count"] == 1
    assert body["issue_count"] == 0


def test_crawl_l3_returns_404_without_snapshot(monkeypatch) -> None:
    monkeypatch.setenv("INTERNAL_API_SECRET", "internal")
    with (
        patch.dict("os.environ", ENV),
        patch("app.api.crawl.load_snapshot_from_file_or_db", return_value=None),
    ):
        resp = TestClient(app).post("/api/shops/store.myshopify.com/crawl/l3", headers=HEADERS)

    assert resp.status_code == 404
