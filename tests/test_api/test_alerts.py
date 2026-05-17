"""Tests for merchant alert summary endpoint."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import app

SHOP = "alerts-test.myshopify.com"

ENV = {
    "SHOPIFY_STORE_DOMAIN": SHOP,
    "SHOPIFY_ACCESS_TOKEN": "shpat_test",
    "SHOPIFY_CLIENT_ID": "client_id",
    "SHOPIFY_CLIENT_SECRET": "client_secret",
    "SHOPIFY_SCOPES": "read_products",
    "APP_URL": "https://example.com",
}


@pytest.fixture()
def client(tmp_path: Path):
    with patch.dict("os.environ", ENV):
        with patch("app.db_adapter.DB_PATH", tmp_path / "test.db"):
            from app.db import init_db

            init_db(tmp_path / "test.db")
            yield TestClient(app)


def _no_data():
    """Return empty status for shops with no data."""
    return {"available": False, "alerts": [], "issues": []}


def test_alerts_summary_empty_when_no_data(client: TestClient):
    """All sources unavailable → empty alerts, 200 OK."""
    with (
        patch("app.api.alerts._pagespeed_alerts", return_value=[]),
        patch("app.api.alerts._crawl_404_alerts", return_value=[]),
        patch("app.api.alerts._gsc_ctr_alerts", return_value=[]),
        patch("app.api.alerts._budget_alert", return_value=[]),
        patch("app.api.alerts._failed_jobs_alerts", return_value=[]),
    ):
        r = client.get(f"/api/shops/{SHOP}/alerts/summary")
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 0
    assert data["alerts"] == []
    assert data["by_severity"] == {}


def test_alerts_summary_aggregates_all_sources(client: TestClient):
    """Alerts from all sources are merged into a single list."""
    ps_alert = {"type": "cwv", "severity": "critical", "message": "Score bas", "url": "https://x.com"}
    ctr_alert = {"type": "low_ctr", "severity": "warning", "message": "CTR faible", "url": "https://x.com/p"}
    budget_alert = {"type": "llm_budget", "severity": "warning", "message": "80% budget", "url": None}
    job_alert = {"type": "job_failed", "severity": "error", "message": "Job échoué — seo_audit", "url": None}

    with (
        patch("app.api.alerts._pagespeed_alerts", return_value=[ps_alert]),
        patch("app.api.alerts._crawl_404_alerts", return_value=[]),
        patch("app.api.alerts._gsc_ctr_alerts", return_value=[ctr_alert]),
        patch("app.api.alerts._budget_alert", return_value=[budget_alert]),
        patch("app.api.alerts._failed_jobs_alerts", return_value=[job_alert]),
    ):
        r = client.get(f"/api/shops/{SHOP}/alerts/summary")
    data = r.json()
    assert data["total"] == 4
    assert data["by_severity"]["critical"] == 1
    assert data["by_severity"]["warning"] == 2
    assert data["by_severity"]["error"] == 1


def test_alerts_404_detected(client: TestClient):
    """Crawl 404 alert is surfaced correctly."""
    alert = {
        "type": "crawl_404",
        "severity": "critical",
        "message": "Page 404 — https://x.com/old",
        "url": "https://x.com/old",
    }
    with (
        patch("app.api.alerts._pagespeed_alerts", return_value=[]),
        patch("app.api.alerts._crawl_404_alerts", return_value=[alert]),
        patch("app.api.alerts._gsc_ctr_alerts", return_value=[]),
        patch("app.api.alerts._budget_alert", return_value=[]),
        patch("app.api.alerts._failed_jobs_alerts", return_value=[]),
    ):
        r = client.get(f"/api/shops/{SHOP}/alerts/summary")
    data = r.json()
    types = [a["type"] for a in data["alerts"]]
    assert "crawl_404" in types


def test_alerts_budget_custom_param(client: TestClient):
    """budget_usd query param is forwarded to the budget checker."""
    captured = {}

    def mock_budget(shop, budget_usd):
        captured["budget_usd"] = budget_usd
        return []

    with (
        patch("app.api.alerts._pagespeed_alerts", return_value=[]),
        patch("app.api.alerts._crawl_404_alerts", return_value=[]),
        patch("app.api.alerts._gsc_ctr_alerts", return_value=[]),
        patch("app.api.alerts._budget_alert", side_effect=mock_budget),
        patch("app.api.alerts._failed_jobs_alerts", return_value=[]),
    ):
        client.get(f"/api/shops/{SHOP}/alerts/summary?budget_usd=25.0")
    assert captured["budget_usd"] == 25.0


def test_pagespeed_alerts_helper_returns_empty_when_unavailable():
    """_pagespeed_alerts returns [] when no PageSpeed data is available."""
    from app.api.alerts import _pagespeed_alerts

    with patch("app.pagespeed.client.latest_pagespeed_status", return_value={"available": False, "alerts": []}):
        result = _pagespeed_alerts(SHOP)
    assert result == []


def test_pagespeed_alerts_helper_maps_severity():
    """_pagespeed_alerts returns alert dicts with correct type and severity."""
    from app.api.alerts import _pagespeed_alerts

    fake_status = {
        "available": True,
        "alerts": [
            {"url": "https://x.com", "strategy": "mobile", "performance_score": 0.45, "severity": "critical"},
        ],
    }
    with patch("app.pagespeed.client.latest_pagespeed_status", return_value=fake_status):
        result = _pagespeed_alerts(SHOP)
    assert len(result) == 1
    assert result[0]["type"] == "cwv"
    assert result[0]["severity"] == "critical"


def test_gsc_ctr_alerts_helper_filters_low_ctr():
    """_gsc_ctr_alerts flags pages with many impressions but low CTR."""
    from app.api.alerts import _gsc_ctr_alerts

    fake_rows = {
        "https://x.com/p1": {"impressions": 500, "ctr": 0.005, "position": 8.0},
        "https://x.com/p2": {"impressions": 50, "ctr": 0.002, "position": 12.0},  # below threshold
        "https://x.com/p3": {"impressions": 200, "ctr": 0.05, "position": 3.0},  # CTR fine
    }
    from unittest.mock import MagicMock

    mock_file = MagicMock()
    mock_file.read_text.return_value = ""
    with (
        patch("app.impact.report._find_gsc_file", return_value=mock_file),
        patch("app.impact.report._parse_gsc_csv", return_value=fake_rows),
    ):
        result = _gsc_ctr_alerts(SHOP)
    assert any(a["url"] == "https://x.com/p1" for a in result)
    assert not any(a["url"] == "https://x.com/p2" for a in result)
    assert not any(a["url"] == "https://x.com/p3" for a in result)


def test_failed_jobs_alerts_helper():
    """_failed_jobs_alerts returns one alert per failed job."""
    from app.api.alerts import _failed_jobs_alerts

    fake_jobs = [
        {"id": "abc", "queue": "seo_audit", "error": "timeout", "status": "failed"},
    ]
    with patch("app.jobs.store.list_jobs", return_value=fake_jobs):
        result = _failed_jobs_alerts(SHOP)
    assert len(result) == 1
    assert result[0]["type"] == "job_failed"
    assert result[0]["severity"] == "error"
