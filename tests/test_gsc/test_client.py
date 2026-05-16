"""Tests for Google Search Console import helpers."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

from app.gsc.client import fetch_and_store_gsc_performance, latest_import_status


def _service(page_rows: list[dict], query_page_rows: list[dict]) -> MagicMock:
    service = MagicMock()
    service.searchanalytics().query().execute.side_effect = [
        {"rows": page_rows},
        {"rows": query_page_rows},
    ]
    return service


def test_fetch_and_store_gsc_performance_writes_shop_scoped_exports_when_rows_exist(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr("app.gsc.client._DATA_DIR", tmp_path)
    service = _service(
        [
            {
                "keys": ["https://example.com/products/harnais"],
                "clicks": 10,
                "impressions": 100,
                "ctr": 0.1,
                "position": 7.2,
            }
        ],
        [
            {
                "keys": ["harnais chien", "https://example.com/products/harnais"],
                "clicks": 5,
                "impressions": 80,
                "ctr": 0.0625,
                "position": 11.0,
            }
        ],
    )

    result = fetch_and_store_gsc_performance(
        "store.myshopify.com",
        days=30,
        site_url="sc-domain:example.com",
        service=service,
    )

    shop_dir = tmp_path / "store.myshopify.com"
    assert result["page_rows"] == 1
    assert result["query_page_rows"] == 1
    assert (shop_dir / "gsc_performance.csv").exists()
    assert (shop_dir / "gsc_query_page.csv").exists()

    payload = json.loads(Path(result["json_path"]).read_text(encoding="utf-8"))
    assert payload["site_url"] == "sc-domain:example.com"
    assert payload["rows"][0]["query"] == "harnais chien"


def test_latest_import_status_returns_empty_when_no_import_exists(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("app.gsc.client._DATA_DIR", tmp_path)

    status = latest_import_status("missing.myshopify.com")

    assert status == {"available": False, "row_count": 0, "imported_at": None}
