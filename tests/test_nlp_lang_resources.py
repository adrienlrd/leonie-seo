"""Tests for the multi-language NLP resource unions."""

from __future__ import annotations

from app.nlp.lang_resources import (
    commercial_signals_all,
    informational_signals_all,
    origin_patterns_all,
    stopwords_all,
)


def test_stopwords_cover_the_three_added_languages() -> None:
    sw = stopwords_all()
    assert {"the", "der", "las"} <= sw


def test_intent_signals_cover_de_and_es() -> None:
    assert {"warum", "cómo", "how"} <= informational_signals_all()
    assert {"kaufen", "comprar", "buy"} <= commercial_signals_all()


def test_origin_patterns_cover_target_markets() -> None:
    pats = origin_patterns_all()
    assert "made in germany" in pats
    assert "fabricado en españa" in pats


def test_intent_classifier_detects_german_and_spanish_intents() -> None:
    from app.niche.intent import _INFORMATIONAL_SIGNALS, _STOPWORDS

    assert "warum" in _INFORMATIONAL_SIGNALS
    assert "cómo" in _INFORMATIONAL_SIGNALS
    assert "einen" in _STOPWORDS


def test_engine_confidence_accepts_german_and_spanish_wordings() -> None:
    from app.market_analysis.engine import _normalize_confidence

    assert _normalize_confidence("hoch") == "high"
    assert _normalize_confidence("alta") == "high"
    assert _normalize_confidence("niedrig") == "low"
    assert _normalize_confidence("medio") == "medium"
