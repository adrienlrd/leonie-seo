"""Auto-refresh of GSC data before market analysis runs.

The merchant should never have to remember to re-import: a stale or missing CSV
is refreshed transparently when an analysis starts, and a disconnected shop is
detected without any API call.
"""

from __future__ import annotations

import time
from unittest.mock import MagicMock

from app.gsc import client


def _set_data_dir(monkeypatch, tmp_path):
    monkeypatch.setattr(client, "_DATA_DIR", tmp_path / "raw")


def _write_csv(tmp_path, *, age_days: float) -> None:
    shop_dir = tmp_path / "raw" / "shop.myshopify.com"
    shop_dir.mkdir(parents=True)
    csv = shop_dir / "gsc_performance.csv"
    csv.write_text("url,clicks\n", encoding="utf-8")
    if age_days > 0:
        past = time.time() - age_days * 86400
        import os

        os.utime(csv, (past, past))


def test_returns_not_connected_without_any_api_call(monkeypatch, tmp_path):
    _set_data_dir(monkeypatch, tmp_path)
    monkeypatch.setattr(client, "get_google_token", lambda _shop: None)
    fetch = MagicMock()
    monkeypatch.setattr(client, "fetch_and_store_gsc_performance", fetch)

    out = client.ensure_fresh_gsc("shop.myshopify.com")

    assert out["status"] == "not_connected"
    fetch.assert_not_called()


def test_returns_fresh_when_csv_is_within_max_age(monkeypatch, tmp_path):
    _set_data_dir(monkeypatch, tmp_path)
    monkeypatch.setattr(client, "get_google_token", lambda _shop: {"token": "x"})
    _write_csv(tmp_path, age_days=2)
    fetch = MagicMock()
    monkeypatch.setattr(client, "fetch_and_store_gsc_performance", fetch)

    out = client.ensure_fresh_gsc("shop.myshopify.com", max_age_days=7)

    assert out["status"] == "fresh"
    fetch.assert_not_called()


def test_refreshes_when_csv_is_stale(monkeypatch, tmp_path):
    _set_data_dir(monkeypatch, tmp_path)
    monkeypatch.setattr(client, "get_google_token", lambda _shop: {"token": "x"})
    _write_csv(tmp_path, age_days=30)
    fetch = MagicMock(return_value={"page_rows": 42, "query_page_rows": 10})
    monkeypatch.setattr(client, "fetch_and_store_gsc_performance", fetch)

    out = client.ensure_fresh_gsc("shop.myshopify.com", max_age_days=7)

    assert out["status"] == "refreshed"
    assert out["rows"] == 42
    fetch.assert_called_once()


def test_refreshes_when_csv_is_missing(monkeypatch, tmp_path):
    _set_data_dir(monkeypatch, tmp_path)
    monkeypatch.setattr(client, "get_google_token", lambda _shop: {"token": "x"})
    fetch = MagicMock(return_value={"page_rows": 7})
    monkeypatch.setattr(client, "fetch_and_store_gsc_performance", fetch)

    out = client.ensure_fresh_gsc("shop.myshopify.com")

    assert out["status"] == "refreshed"
    assert out["rows"] == 7
    fetch.assert_called_once()


def test_fail_open_when_provider_raises(monkeypatch, tmp_path):
    _set_data_dir(monkeypatch, tmp_path)
    monkeypatch.setattr(client, "get_google_token", lambda _shop: {"token": "x"})

    def boom(*_a, **_kw):
        raise RuntimeError("Google down")

    monkeypatch.setattr(client, "fetch_and_store_gsc_performance", boom)

    out = client.ensure_fresh_gsc("shop.myshopify.com")

    assert out["status"] == "failed"
    assert "Google down" in out["error"]
