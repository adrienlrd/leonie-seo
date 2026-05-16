"""Tests for PageSpeed API endpoints."""

from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app

ENV = {
    "SHOPIFY_STORE_DOMAIN": "store.myshopify.com",
    "SHOPIFY_ACCESS_TOKEN": "shpat_test",
    "SHOPIFY_CLIENT_ID": "client_id",
    "SHOPIFY_CLIENT_SECRET": "client_secret",
    "SHOPIFY_SCOPES": "read_products",
    "APP_URL": "https://app.example.com",
    "INTERNAL_API_SECRET": "internal",
    "PAGESPEED_API_KEY": "pagespeed-key",
}

HEADERS = {
    "X-Leonie-Shop": "store.myshopify.com",
    "X-Internal-Secret": "internal",
    "X-Shopify-Access-Token": "shpat_test",
}


def test_pagespeed_status_returns_latest_summary(monkeypatch) -> None:
    monkeypatch.setenv("INTERNAL_API_SECRET", "internal")
    with (
        patch.dict("os.environ", ENV),
        patch("app.api.pagespeed.priority_urls_for_shop", return_value=["https://example.com"]),
        patch(
            "app.api.pagespeed.latest_pagespeed_status",
            return_value={
                "available": True,
                "row_count": 2,
                "url_count": 1,
                "imported_at": "2026-05-16T10:00:00+00:00",
                "mobile_average": 0.42,
                "desktop_average": 0.86,
                "alerts": [],
                "rows": [],
            },
        ),
    ):
        resp = TestClient(app).get("/api/shops/store.myshopify.com/pagespeed/status", headers=HEADERS)

    assert resp.status_code == 200
    body = resp.json()
    assert body["configured"] is True
    assert body["available"] is True
    assert body["targets"] == ["https://example.com"]
    assert body["mobile_average"] == 0.42


def test_pagespeed_import_enqueues_job(monkeypatch) -> None:
    monkeypatch.setenv("INTERNAL_API_SECRET", "internal")
    with (
        patch.dict("os.environ", ENV),
        patch("app.api.pagespeed.enqueue", return_value="job-123") as enqueue,
    ):
        resp = TestClient(app).post(
            "/api/shops/store.myshopify.com/pagespeed/import",
            headers=HEADERS,
            json={"urls": ["https://example.com"], "max_urls": 1},
        )

    assert resp.status_code == 202
    assert resp.json()["job_id"] == "job-123"
    enqueue.assert_called_once()
    assert enqueue.call_args.args[0] == "pagespeed_import"


def test_pagespeed_import_requires_api_key(monkeypatch) -> None:
    monkeypatch.setenv("INTERNAL_API_SECRET", "internal")
    env = {key: value for key, value in ENV.items() if key != "PAGESPEED_API_KEY"}
    with patch.dict("os.environ", env, clear=True):
        resp = TestClient(app).post(
            "/api/shops/store.myshopify.com/pagespeed/import",
            headers=HEADERS,
            json={"max_urls": 1},
        )

    assert resp.status_code == 409
    assert "PAGESPEED_API_KEY" in resp.json()["detail"]
