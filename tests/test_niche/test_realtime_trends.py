"""Tests for the real-time market signals fetcher (Grande boutique plan only)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.billing.subscription_store import upsert_subscription
from app.db import init_db
from app.llm.provider import CompletionResult, LLMError
from app.niche.signals.realtime_trends import (
    fetch_realtime_signals,
    load_realtime_signals,
    verify_keywords_against_market,
)

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


def test_force_bypasses_plan_gate_for_pro_plan(
    db: Path, data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """force=True (Pro/Grande boutique comparison tool only) must still exercise
    the grounded call even on a non-agency plan, without touching the shop's
    real billing state — this test never writes to the subscription store."""
    upsert_subscription(SHOP, "pro", "active", "gid://sub/1", db_path=db)
    monkeypatch.setenv("GEMINI_API_KEY", "AIza-test")
    mock_router = MagicMock()
    mock_router.complete.return_value = CompletionResult(
        text=json.dumps({"events": [], "rising_queries": [], "competitor_moves": []}),
        provider="gemini",
        model="gemini-3.1-flash-lite",
    )
    with patch("app.niche.signals.realtime_trends.get_router", return_value=mock_router):
        result = fetch_realtime_signals(SHOP, {}, ["produit"], db_path=db, force=True)
    assert result is not None
    # Real plan is untouched — still "pro" in the subscription store.
    from app.billing.subscription_store import get_plan_for_shop

    assert get_plan_for_shop(SHOP, db_path=db) == "pro"


def test_force_still_requires_gemini_key(
    db: Path, data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    upsert_subscription(SHOP, "pro", "active", "gid://sub/1", db_path=db)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with patch("app.niche.signals.realtime_trends.get_router") as mock_router:
        result = fetch_realtime_signals(SHOP, {}, ["produit"], db_path=db, force=True)
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


def test_persist_false_does_not_write_file(
    db: Path, data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The per-product grounding loop (engine.py) calls this once per product
    with persist=False, then merges + saves once itself — a per-product call
    must never silently overwrite a previous product's saved snapshot."""
    _agency(db)
    monkeypatch.setenv("GEMINI_API_KEY", "AIza-test")
    mock_router = MagicMock()
    mock_router.complete.return_value = CompletionResult(
        text=json.dumps({"events": [], "rising_queries": [], "competitor_moves": []}),
        provider="gemini",
        model="gemini-3.1-flash-lite",
    )
    with patch("app.niche.signals.realtime_trends.get_router", return_value=mock_router):
        result = fetch_realtime_signals(SHOP, {}, ["produit"], db_path=db, persist=False)

    assert result is not None
    assert not (data_dir / SHOP / "realtime_signals.json").exists()


def test_persist_realtime_signals_writes_the_merged_snapshot(
    db: Path, data_dir: Path
) -> None:
    from app.niche.signals.realtime_trends import persist_realtime_signals

    merged = {"events": [{"title": "Merged event"}], "rising_queries": [], "competitor_moves": []}
    persist_realtime_signals(SHOP, merged, db_path=db)

    saved = json.loads((data_dir / SHOP / "realtime_signals.json").read_text())
    assert saved["events"][0]["title"] == "Merged event"

    loaded = load_realtime_signals(SHOP, db_path=db)
    assert loaded is not None
    assert loaded["events"][0]["title"] == "Merged event"


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


# ── status_out diagnostics (fetch_realtime_signals) ─────────────────────────


def test_status_out_no_gemini_key(db: Path, data_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _agency(db)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    status: dict = {}
    fetch_realtime_signals(SHOP, {}, ["produit"], db_path=db, status_out=status)
    assert status["status"] == "no_gemini_key"


def test_status_out_plan_not_agency(db: Path, data_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "AIza-test")
    status: dict = {}
    fetch_realtime_signals(SHOP, {}, ["produit"], db_path=db, status_out=status)
    assert status["status"] == "plan_not_agency"


def test_status_out_ok(db: Path, data_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _agency(db)
    monkeypatch.setenv("GEMINI_API_KEY", "AIza-test")
    mock_router = MagicMock()
    mock_router.complete.return_value = CompletionResult(
        text=json.dumps({"events": [], "rising_queries": [], "competitor_moves": []}),
        provider="gemini",
        model="gemini-3.1-flash-lite",
    )
    status: dict = {}
    with patch("app.niche.signals.realtime_trends.get_router", return_value=mock_router):
        fetch_realtime_signals(SHOP, {}, ["produit"], db_path=db, status_out=status)
    assert status["status"] == "ok"


def test_status_out_llm_error(db: Path, data_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _agency(db)
    monkeypatch.setenv("GEMINI_API_KEY", "AIza-test")
    status: dict = {}
    with patch(
        "app.niche.signals.realtime_trends.get_router",
        side_effect=LLMError("all providers failed"),
    ):
        fetch_realtime_signals(SHOP, {}, ["produit"], db_path=db, status_out=status)
    assert status["status"] == "llm_error"


def test_status_out_parse_error(db: Path, data_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _agency(db)
    monkeypatch.setenv("GEMINI_API_KEY", "AIza-test")
    mock_router = MagicMock()
    mock_router.complete.return_value = CompletionResult(
        text="not json", provider="gemini", model="gemini-3.1-flash-lite"
    )
    status: dict = {}
    with patch("app.niche.signals.realtime_trends.get_router", return_value=mock_router):
        fetch_realtime_signals(SHOP, {}, ["produit"], db_path=db, status_out=status)
    assert status["status"] == "parse_error"


# ── verify_keywords_against_market ──────────────────────────────────────────


def test_verify_returns_none_for_free_plan(
    db: Path, data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "AIza-test")
    with patch("app.niche.signals.realtime_trends.get_router") as mock_router:
        result = verify_keywords_against_market(SHOP, ["fontaine à eau chat"], "accessoires pour chats", db_path=db)
    assert result is None
    mock_router.assert_not_called()


def test_verify_returns_none_without_gemini_key(
    db: Path, data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _agency(db)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with patch("app.niche.signals.realtime_trends.get_router") as mock_router:
        result = verify_keywords_against_market(SHOP, ["fontaine à eau chat"], "accessoires pour chats", db_path=db)
    assert result is None
    mock_router.assert_not_called()


def test_verify_parses_verifications_by_query(
    db: Path, data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _agency(db)
    monkeypatch.setenv("GEMINI_API_KEY", "AIza-test")
    mock_router = MagicMock()
    mock_router.complete.return_value = CompletionResult(
        text=json.dumps(
            {
                "verifications": [
                    {
                        "query": "Fontaine à eau chat",
                        "market_evidence": "rising",
                        "evidence_note": "Recherches en hausse pendant la canicule",
                        "source_url": "https://example.com/trend",
                    },
                    {"query": "griffoir arbre à chat", "market_evidence": "no_signal"},
                ]
            }
        ),
        provider="gemini",
        model="gemini-3.1-flash-lite",
    )
    with patch("app.niche.signals.realtime_trends.get_router", return_value=mock_router):
        result = verify_keywords_against_market(
            SHOP, ["Fontaine à eau chat", "griffoir arbre à chat"], "accessoires pour chats", db_path=db
        )
    assert result is not None
    assert result["fontaine à eau chat"]["evidence"] == "rising"
    assert result["fontaine à eau chat"]["source_url"] == "https://example.com/trend"
    assert result["griffoir arbre à chat"]["evidence"] == "no_signal"


def test_verify_caps_keyword_list(db: Path, data_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _agency(db)
    monkeypatch.setenv("GEMINI_API_KEY", "AIza-test")
    mock_router = MagicMock()
    mock_router.complete.return_value = CompletionResult(
        text=json.dumps({"verifications": []}), provider="gemini", model="gemini-3.1-flash-lite"
    )
    keywords = [f"kw{i}" for i in range(50)]
    with patch("app.niche.signals.realtime_trends.get_router", return_value=mock_router):
        verify_keywords_against_market(SHOP, keywords, "niche", db_path=db)
    prompt = mock_router.complete.call_args.args[0]
    assert "kw29" in prompt
    assert "kw30" not in prompt


def test_verify_batches_keywords_into_calls_of_ten_and_merges_results(
    db: Path, data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """25 keywords → 3 grounded calls (10+10+5), verdicts merged across batches.
    Live finding (2026-07-16): one 30-keyword call only yielded ~6 verdicts."""
    _agency(db)
    monkeypatch.setenv("GEMINI_API_KEY", "AIza-test")
    mock_router = MagicMock()
    mock_router.complete.side_effect = [
        CompletionResult(
            text=json.dumps(
                {"verifications": [{"query": f"kw{i}", "market_evidence": "confirmed"}]}
            ),
            provider="gemini",
            model="gemini-3.1-flash-lite",
        )
        for i in (0, 10, 20)
    ]
    keywords = [f"kw{i}" for i in range(25)]
    with patch("app.niche.signals.realtime_trends.get_router", return_value=mock_router):
        status: dict = {}
        result = verify_keywords_against_market(
            SHOP, keywords, "niche", db_path=db, status_out=status
        )
    assert mock_router.complete.call_count == 3
    prompts = [c.args[0] for c in mock_router.complete.call_args_list]
    assert "kw0" in prompts[0] and "kw10" not in prompts[0]
    assert "kw10" in prompts[1] and "kw20" not in prompts[1]
    assert "kw20" in prompts[2] and "kw24" in prompts[2]
    assert result is not None
    assert set(result) == {"kw0", "kw10", "kw20"}
    assert status["status"] == "ok"


def test_verify_partial_status_when_one_batch_fails(
    db: Path, data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _agency(db)
    monkeypatch.setenv("GEMINI_API_KEY", "AIza-test")
    mock_router = MagicMock()
    mock_router.complete.side_effect = [
        CompletionResult(
            text=json.dumps(
                {"verifications": [{"query": "kw0", "market_evidence": "rising"}]}
            ),
            provider="gemini",
            model="gemini-3.1-flash-lite",
        ),
        LLMError("boom"),
    ]
    keywords = [f"kw{i}" for i in range(15)]
    with patch("app.niche.signals.realtime_trends.get_router", return_value=mock_router):
        status: dict = {}
        result = verify_keywords_against_market(
            SHOP, keywords, "niche", db_path=db, status_out=status
        )
    assert result == {"kw0": {"evidence": "rising", "note": "", "source_url": ""}}
    assert status["status"] == "partial"


def test_verify_fail_open_when_llm_raises(
    db: Path, data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _agency(db)
    monkeypatch.setenv("GEMINI_API_KEY", "AIza-test")
    with patch(
        "app.niche.signals.realtime_trends.get_router",
        side_effect=LLMError("all providers failed"),
    ):
        result = verify_keywords_against_market(SHOP, ["fontaine à eau chat"], "niche", db_path=db)
    assert result is None


def test_verify_force_bypasses_plan_gate(
    db: Path, data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    upsert_subscription(SHOP, "pro", "active", "gid://sub/1", db_path=db)
    monkeypatch.setenv("GEMINI_API_KEY", "AIza-test")
    mock_router = MagicMock()
    mock_router.complete.return_value = CompletionResult(
        text=json.dumps({"verifications": []}), provider="gemini", model="gemini-3.1-flash-lite"
    )
    with patch("app.niche.signals.realtime_trends.get_router", return_value=mock_router):
        result = verify_keywords_against_market(SHOP, ["fontaine à eau chat"], "niche", db_path=db, force=True)
    assert result is not None
