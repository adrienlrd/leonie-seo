"""Tests for the reusable proposal constraint validator."""

from __future__ import annotations

from app.content_actions.audit import validate_proposal_text


def test_valid_meta_title_passes() -> None:
    safe, reasons = validate_proposal_text("meta_title", "Harnais Premium pour Chien de Berger")
    assert safe is True
    assert reasons == []


def test_forbidden_promise_is_blocked() -> None:
    safe, reasons = validate_proposal_text(
        "meta_description",
        "Notre croquette guérit votre chien de toutes ses maladies en une semaine garantie.",
        forbidden_promises=["guérit", "garantie"],
    )
    assert safe is False
    assert any("forbidden_promise" in r for r in reasons)


def test_meta_title_too_long_is_blocked() -> None:
    safe, reasons = validate_proposal_text("meta_title", "x" * 120)
    assert safe is False
    assert "length_out_of_bounds" in reasons


def test_meta_title_too_short_is_blocked() -> None:
    safe, reasons = validate_proposal_text("meta_title", "Court")
    assert safe is False
    assert "length_out_of_bounds" in reasons


def test_do_not_say_word_is_blocked() -> None:
    safe, reasons = validate_proposal_text(
        "meta_title",
        "Le meilleur harnais pas cher du marché",
        do_not_say=["pas cher"],
    )
    assert safe is False
    assert any("do_not_say" in r for r in reasons)


def test_non_french_description_is_blocked() -> None:
    safe, reasons = validate_proposal_text(
        "description",
        "This is a fully English product description that should be at least six hundred "
        "characters long to pass the length check but must fail the language check because "
        "it contains no French marker words at all. " + ("filler text here " * 30),
    )
    assert safe is False
    assert "language_mismatch" in reasons


def test_short_french_title_not_flagged_for_language() -> None:
    # A short French title has too few markers for the heuristic; we must not
    # falsely flag it as non-French.
    safe, reasons = validate_proposal_text("meta_title", "Croquettes Naturelles Chien Adulte")
    assert "language_mismatch" not in reasons
    assert safe is True


def test_unknown_field_skips_length_check() -> None:
    safe, reasons = validate_proposal_text("some_unknown_field", "anything")
    assert safe is True
    assert reasons == []
