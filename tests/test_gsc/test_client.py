"""Tests for Google Search Console import helpers."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import google.auth.exceptions
import pytest

from app.gsc.client import (
    GSCConnectionError,
    _credentials_for_shop,
    fetch_and_store_gsc_performance,
    latest_import_status,
)


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


def test_credentials_for_shop_raises_when_not_connected(monkeypatch) -> None:
    monkeypatch.setattr("app.gsc.client.get_google_token", lambda shop, **kw: None)

    with pytest.raises(GSCConnectionError, match="not connected"):
        _credentials_for_shop("store.myshopify.com")


def test_credentials_for_shop_clears_token_and_raises_on_invalid_grant(monkeypatch) -> None:
    fake_token = json.dumps(
        {
            "token": None,
            "refresh_token": "fake_refresh",
            "token_uri": "https://oauth2.googleapis.com/token",
            "client_id": "fake_client",
            "client_secret": "fake_secret",
            "scopes": ["https://www.googleapis.com/auth/webmasters.readonly"],
        }
    )
    monkeypatch.setattr(
        "app.gsc.client.get_google_token",
        lambda shop, **kw: {"token_json": fake_token},
    )
    deleted: list[str] = []
    monkeypatch.setattr(
        "app.gsc.client.delete_google_token", lambda shop, **kw: deleted.append(shop)
    )

    mock_creds = MagicMock()
    mock_creds.expired = True
    mock_creds.refresh_token = "fake_refresh"
    mock_creds.refresh.side_effect = google.auth.exceptions.RefreshError("invalid_grant")

    with patch("app.gsc.client.Credentials.from_authorized_user_info", return_value=mock_creds):
        with pytest.raises(GSCConnectionError, match="revoked"):
            _credentials_for_shop("store.myshopify.com")

    assert deleted == ["store.myshopify.com"]
