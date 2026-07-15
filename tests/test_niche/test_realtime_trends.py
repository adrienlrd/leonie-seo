"""Tests for the real-time market signals fetcher (Grande boutique plan only)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.billing.subscription_store import upsert_subscription
from app.db import init_db
from app.llm.provider import CompletionResult, LLMError
from app.niche.signals.realtime_trends import fetch_realtime_signals, load_realtime_signals

SHOP = "store.myshopify.com"


@pytest.fixture()
def db(tmp_path: Path) -> Path:
    path = tmp_path / "test.db"
    init_db(path)
    return path


@pytest.fixture()
def data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    d = tmp_path / "data_raw"
    monkeypatch.setattr("app.niche.signals.realtime_trends._DATA_DIR", d)
    return d


def _agency(db_path: Path) -> None:
    upsert_subscription(SHOP, "agency", "active", "gid://sub/1", db_path=db_path)


def test_returns_none_for_free_plan(db: Path, data_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "AIza-test")
    with patch("app.niche.signals.realtime_trends.get_router") as mock_router:
        result = fetch_realtime_signals(SHOP, {}, ["produit"], db_path=db)
    assert result is None
    mock_router.assert_not_called()


def test_returns_none_for_pro_plan(db: Path, data_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    upsert_subscription(SHOP, "pro", "active", "gid://sub/1", db_path=db)
    monkeypatch.setenv("GEMINI_API_KEY", "AIza-test")
    with patch("app.niche.signals.realtime_trends.get_router") as mock_router:
        result = fetch_realtime_signals(SHOP, {}, ["produit"], db_path=db)
    assert result is None
    mock_router.assert_not_called()


def test_returns_none_without_gemini_key(
    db: Path, data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _agency(db)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with patch("app.niche.signals.realtime_trends.get_router") as mock_router:
        result = fetch_realtime_signals(SHOP, {}, ["produit"], db_path=db)
    assert result is None
    mock_router.assert_not_called()


def test_agency_with_key_calls_grounded_router(
    db: Path, data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _agency(db)
    monkeypatch.setenv("GEMINI_API_KEY", "AIza-test")
    mock_router = MagicMock()
    mock_router.complete.return_value = CompletionResult(
        text=json.dumps({"events": [], "rising_queries": [], "competitor_moves": []}),
        provider="gemini",
        model="gemini-3.1-flash-lite",
        citations=[{"url": "https://example.com", "title": "Example"}],
    )
    with patch("app.niche.signals.realtime_trends.get_router", return_value=mock_router) as get_router_mock:
        result = fetch_realtime_signals(SHOP, {"niche_summary": "alimentation chat"}, ["Fontaine à eau"], db_path=db)
    get_router_mock.assert_called_once_with(shop=SHOP, tier="grounded")
    assert result is not None
    assert result["citations"] == [{"url": "https://example.com", "title": "Example"}]
    assert "fetched_at" in result


def test_persists_result_to_json_file(db: Path, data_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _agency(db)
    monkeypatch.setenv("GEMINI_API_KEY", "AIza-test")
    mock_router = MagicMock()
    mock_router.complete.return_value = CompletionResult(
        text=json.dumps(
            {
                "events": [{"title": "Canicule", "description": "...", "source_url": "https://meteo.fr"}],
                "rising_queries": [],
                "competitor_moves": [],
            }
        ),
        provider="gemini",
        model="gemini-3.1-flash-lite",
    )
    with patch("app.niche.signals.realtime_trends.get_router", return_value=mock_router):
        fetch_realtime_signals(SHOP, {}, ["produit"], db_path=db)

    saved = json.loads((data_dir / SHOP / "realtime_signals.json").read_text())
    assert saved["events"][0]["title"] == "Canicule"

    loaded = load_realtime_signals(SHOP, db_path=db)
    assert loaded is not None
    assert loaded["events"][0]["title"] == "Canicule"


def test_fail_open_when_llm_raises(db: Path, data_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _agency(db)
    monkeypatch.setenv("GEMINI_API_KEY", "AIza-test")
    with patch(
        "app.niche.signals.realtime_trends.get_router",
        side_effect=LLMError("all providers failed"),
    ):
        result = fetch_realtime_signals(SHOP, {}, ["produit"], db_path=db)
    assert result is None


def test_fail_open_when_response_is_not_valid_json(
    db: Path, data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _agency(db)
    monkeypatch.setenv("GEMINI_API_KEY", "AIza-test")
    mock_router = MagicMock()
    mock_router.complete.return_value = CompletionResult(
        text="not json at all", provider="gemini", model="gemini-3.1-flash-lite"
    )
    with patch("app.niche.signals.realtime_trends.get_router", return_value=mock_router):
        result = fetch_realtime_signals(SHOP, {}, ["produit"], db_path=db)
    assert result is None


def test_load_returns_none_when_nothing_persisted(
    db: Path, data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert load_realtime_signals(SHOP, db_path=db) is None
