"""Tests for E-E-A-T signal detection (petfood FR focus)."""

from __future__ import annotations

from app.market_analysis import eeat


def _fact(key: str, value: str) -> dict:
    return {
        "key": key,
        "label": key.title(),
        "value": value,
        "source": "merchant_confirmation",
        "confidence": "confirmed",
    }


class TestDetectEeatSignals:
    def test_detects_known_french_certification(self):
        signals = eeat.detect_signals(
            confirmed_facts=[_fact("certifications", "Ecocert AB")],
            business_profile=None,
        )
        kinds = {s["kind"] for s in signals}
        assert "certification" in kinds
        cert = next(s for s in signals if s["kind"] == "certification")
        assert "Ecocert" in cert["label"]
        assert cert["confidence"] == "confirmed"
        assert cert["source"] == "merchant_confirmation"

    def test_detects_made_in_france_origin(self):
        signals = eeat.detect_signals(
            confirmed_facts=[_fact("origins", "Fabriqué en France")],
            business_profile=None,
        )
        kinds = {s["kind"] for s in signals}
        assert "origin" in kinds

    def test_detects_warranty_when_value_non_blank(self):
        signals = eeat.detect_signals(
            confirmed_facts=[_fact("warranty", "Garantie 2 ans pièces et main d'œuvre")],
            business_profile=None,
        )
        assert any(s["kind"] == "warranty" for s in signals)

    def test_emits_no_signal_when_facts_empty(self):
        assert eeat.detect_signals(confirmed_facts=[], business_profile=None) == []

    def test_ignores_facts_with_unrelated_keys(self):
        signals = eeat.detect_signals(
            confirmed_facts=[_fact("color", "rouge")],
            business_profile=None,
        )
        assert signals == []

    def test_detects_merchant_experience_from_business_profile(self):
        signals = eeat.detect_signals(
            confirmed_facts=[],
            business_profile={"founded_year": 2010, "primary_expertise": "Vétérinaire"},
        )
        kinds = {s["kind"] for s in signals}
        assert "merchant_experience" in kinds
        assert "expertise_authority" in kinds

    def test_handles_list_value_in_certifications(self):
        signals = eeat.detect_signals(
            confirmed_facts=[_fact("certifications", "Ecocert, AB, GOTS")],
            business_profile=None,
        )
        cert_labels = " ".join(s["label"] for s in signals if s["kind"] == "certification")
        assert "Ecocert" in cert_labels
        assert "AB" in cert_labels
        assert "GOTS" in cert_labels


class TestFormatPromptBlock:
    def test_empty_signals_returns_empty_string(self):
        assert eeat.format_prompt_block([]) == ""

    def test_block_lists_signals_with_source(self):
        signals = eeat.detect_signals(
            confirmed_facts=[
                _fact("certifications", "Ecocert"),
                _fact("origins", "France"),
            ],
            business_profile=None,
        )
        block = eeat.format_prompt_block(signals)
        assert "SIGNAUX E-E-A-T" in block
        assert "Ecocert" in block
        assert "France" in block
