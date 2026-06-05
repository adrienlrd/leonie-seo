"""Tests for the competitor exclusion list and signal filtering."""

from __future__ import annotations

import app.market_analysis.competitors as competitors
from app.market_analysis.engine import _drop_excluded_signals


def test_save_and_load_excluded_round_trip(tmp_path, monkeypatch):
    monkeypatch.setattr(competitors, "_DATA_DIR", tmp_path)
    competitors.save_excluded_competitors("demo.myshopify.com", ["Zooplus.fr", "https://www.wanimo.com/x"])

    loaded = competitors.load_excluded_competitors("demo.myshopify.com")

    # Normalized: lowercased, www/protocol/path stripped, deduped
    assert loaded == {"zooplus.fr", "wanimo.com"}


def test_load_excluded_empty_when_absent(tmp_path, monkeypatch):
    monkeypatch.setattr(competitors, "_DATA_DIR", tmp_path)
    assert competitors.load_excluded_competitors("demo.myshopify.com") == set()


def test_save_excluded_dedupes_normalized(tmp_path, monkeypatch):
    monkeypatch.setattr(competitors, "_DATA_DIR", tmp_path)
    competitors.save_excluded_competitors("s.myshopify.com", ["zooplus.fr", "www.zooplus.fr", "ZOOPLUS.FR"])
    assert competitors.load_excluded_competitors("s.myshopify.com") == {"zooplus.fr"}


def test_drop_excluded_signals_filters_by_domain():
    signals = [
        {"domain": "zooplus.fr"},
        {"domain": "www.wanimo.com"},
        {"domain": "croquetteland.com"},
    ]
    out = _drop_excluded_signals(signals, {"zooplus.fr", "wanimo.com"})
    assert [s["domain"] for s in out] == ["croquetteland.com"]


def test_drop_excluded_signals_noop_when_empty():
    signals = [{"domain": "zooplus.fr"}]
    assert _drop_excluded_signals(signals, set()) == signals
