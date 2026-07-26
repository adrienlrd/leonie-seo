"""Tests for the AI visibility measurement (grounded citations = the signal)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.db import init_db
from app.llm.provider import CompletionResult, LLMError
from app.niche.signals.ai_visibility import (
    _domain_of,
    load_ai_visibility,
    measure_ai_visibility,
)

SHOP = "store.myshopify.com"
QUESTIONS = ["Quelle fontaine à eau pour chat choisir ?", "Quel griffoir pour un chat destructeur ?"]


@pytest.fixture()
def db(tmp_path: Path) -> Path:
    path = tmp_path / "test.db"
    init_db(path)
    return path


@pytest.fixture()
def data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    d = tmp_path / "data_raw"
    monkeypatch.setattr("app.niche.signals.ai_visibility._DATA_DIR", d)
    return d


def _answer(domains: list[str], *, grounded: bool = True) -> CompletionResult:
    """An ungrounded answer carries no citations either — the API only returns
    grounding metadata when a search actually ran."""
    return CompletionResult(
        text="Voici quelques options.",
        provider="gemini",
        model="gemini-3.5-flash-lite",
        search_queries=["fontaine chat"] if grounded else [],
        citations=(
            [{"url": f"https://redirect/{d}", "title": d} for d in domains] if grounded else []
        ),
    )


def test_returns_none_without_questions(db: Path, data_dir: Path) -> None:
    assert measure_ai_visibility(SHOP, [], [SHOP], db_path=db) is None


def test_counts_cited_domains_across_questions(db: Path, data_dir: Path) -> None:
    router = MagicMock()
    router.complete.side_effect = [
        _answer(["zoomalia.com", "minouland.com"]),
        _answer(["minouland.com"]),
    ]
    with patch("app.niche.signals.ai_visibility.get_router", return_value=router):
        result = measure_ai_visibility(SHOP, QUESTIONS, [SHOP], db_path=db)

    assert result is not None
    assert result["questions_measured"] == 2
    # minouland cited by both questions, so it outranks zoomalia.
    assert result["top_domains"][0] == {"domain": "minouland.com", "citations": 2}
    assert result["shop_cited_count"] == 0


def test_detects_the_shop_being_cited(db: Path, data_dir: Path) -> None:
    router = MagicMock()
    router.complete.side_effect = [_answer(["boutique-chat.fr"]), _answer(["autre.com"])]
    with patch("app.niche.signals.ai_visibility.get_router", return_value=router):
        result = measure_ai_visibility(SHOP, QUESTIONS, ["www.Boutique-Chat.fr"], db_path=db)

    assert result is not None
    assert result["shop_cited_count"] == 1
    assert result["questions"][0]["shop_cited"] is True


def test_ungrounded_answer_contributes_no_domains(db: Path, data_dir: Path) -> None:
    """No grounding metadata means the model answered from memory: it observed
    nothing, so it must not be counted as a measurement."""
    router = MagicMock()
    router.complete.side_effect = [
        _answer([], grounded=False),
        _answer(["reel.com"]),
    ]
    with patch("app.niche.signals.ai_visibility.get_router", return_value=router):
        result = measure_ai_visibility(SHOP, QUESTIONS, [SHOP], db_path=db)

    assert result is not None
    assert result["questions_asked"] == 2
    assert result["questions_measured"] == 1
    assert result["questions"][0]["grounded"] is False
    assert result["questions"][0]["domains"] == []
    assert [d["domain"] for d in result["top_domains"]] == ["reel.com"]


def test_returns_none_when_nothing_was_grounded(db: Path, data_dir: Path) -> None:
    router = MagicMock()
    router.complete.side_effect = [_answer([], grounded=False), _answer([], grounded=False)]
    with patch("app.niche.signals.ai_visibility.get_router", return_value=router):
        assert measure_ai_visibility(SHOP, QUESTIONS, [SHOP], db_path=db) is None


def test_fail_open_when_the_router_is_unavailable(db: Path, data_dir: Path) -> None:
    with patch(
        "app.niche.signals.ai_visibility.get_router", side_effect=LLMError("no provider")
    ):
        assert measure_ai_visibility(SHOP, QUESTIONS, [SHOP], db_path=db) is None


def test_persists_and_reloads(db: Path, data_dir: Path) -> None:
    router = MagicMock()
    router.complete.side_effect = [_answer(["zoomalia.com"]), _answer(["zoomalia.com"])]
    with patch("app.niche.signals.ai_visibility.get_router", return_value=router):
        measure_ai_visibility(SHOP, QUESTIONS, [SHOP], db_path=db)

    saved = json.loads((data_dir / SHOP / "ai_visibility.json").read_text())
    assert saved["top_domains"][0]["domain"] == "zoomalia.com"
    assert load_ai_visibility(SHOP, db_path=db)["questions_measured"] == 2


def test_domain_of_prefers_the_chunk_title_over_the_redirect_host() -> None:
    """Grounding URLs point at vertexaisearch, so the host is useless."""
    citation = {
        "url": "https://vertexaisearch.cloud.google.com/grounding-api-redirect/abc",
        "title": "www.Meteofrance.com",
    }
    assert _domain_of(citation) == "meteofrance.com"
    assert _domain_of({"url": "https://zoomalia.com/x", "title": "Zoomalia | Animalerie"}) == (
        "zoomalia.com"
    )
