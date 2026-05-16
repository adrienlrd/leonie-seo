"""Tests for PageSpeed embedded app helpers."""

from __future__ import annotations

from app.pagespeed.client import (
    fetch_and_store_pagespeed,
    latest_pagespeed_status,
    regression_alerts,
)


def test_fetch_and_store_pagespeed_writes_shop_scoped_exports(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("app.pagespeed.client._DATA_DIR", tmp_path)
    monkeypatch.setattr(
        "app.pagespeed.client.fetch_scores_for_urls",
        lambda urls, delay: [
            {
                "url": urls[0],
                "strategy": "mobile",
                "performance_score": 0.42,
                "lcp_ms": 4300,
                "cls": 0.05,
                "tbt_ms": 550,
                "fcp_ms": 2300,
            },
            {
                "url": urls[0],
                "strategy": "desktop",
                "performance_score": 0.86,
                "lcp_ms": 1700,
                "cls": 0.02,
                "tbt_ms": 80,
                "fcp_ms": 900,
            },
        ],
    )

    result = fetch_and_store_pagespeed(
        "store.myshopify.com",
        urls=["https://example.com"],
        delay=0,
    )

    shop_dir = tmp_path / "store.myshopify.com"
    assert result["rows"] == 2
    assert (shop_dir / "pagespeed.csv").exists()
    assert list(shop_dir.glob("pagespeed_*.csv"))


def test_latest_pagespeed_status_returns_alerts_and_averages(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("app.pagespeed.client._DATA_DIR", tmp_path)
    shop_dir = tmp_path / "store.myshopify.com"
    shop_dir.mkdir(parents=True)
    (shop_dir / "pagespeed.csv").write_text(
        "\n".join(
            [
                "url,strategy,performance_score,lcp_ms,cls,tbt_ms,fcp_ms",
                "https://example.com,mobile,0.42,4300,0.05,550,2300",
                "https://example.com,desktop,0.86,1700,0.02,80,900",
            ]
        ),
        encoding="utf-8",
    )

    status = latest_pagespeed_status("store.myshopify.com")

    assert status["available"] is True
    assert status["url_count"] == 1
    assert status["mobile_average"] == 0.42
    assert status["desktop_average"] == 0.86
    assert status["alerts"][0]["severity"] == "critical"
    assert status["alerts"][0]["recommendations"]


def test_regression_alerts_detect_score_drop() -> None:
    alerts = regression_alerts(
        [{"url": "https://example.com", "strategy": "mobile", "performance_score": 0.61}],
        [{"url": "https://example.com", "strategy": "mobile", "performance_score": 0.78}],
    )

    assert alerts == [
        {
            "url": "https://example.com",
            "strategy": "mobile",
            "previous_score": 0.78,
            "current_score": 0.61,
            "drop": 0.17,
            "severity": "warning",
        }
    ]
