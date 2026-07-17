"""Tests for the per-language prompt fragments."""

from __future__ import annotations

from app.llm.language_context import (
    grounding_market,
    language_context,
    market_line,
    output_instruction,
)


def test_output_instruction_names_the_target_language() -> None:
    assert "allemand" in output_instruction("de")
    assert "espagnol" in output_instruction("es")
    assert "anglais" in output_instruction("en")
    assert "français" in output_instruction("fr")


def test_market_line_anchors_the_right_country() -> None:
    assert "Deutschland" in market_line("de")
    assert "United States" in market_line("en")
    assert "España" in market_line("es")
    assert "France" in market_line("fr")


def test_language_context_combines_both() -> None:
    ctx = language_context("de")
    assert "allemand" in ctx and "Deutschland" in ctx


def test_unknown_language_falls_back_to_english_market() -> None:
    assert "United States" in market_line("zz")
    assert grounding_market("zz") == ("United States", "English")


def test_pass1_prompt_carries_language_context() -> None:
    from app.market_analysis.engine import _build_pass1_prompt

    prompt = _build_pass1_prompt(
        product_title="Hundegeschirr",
        handle="hundegeschirr",
        description="",
        collections=[],
        tags="",
        price="29",
        nb_variants=1,
        current_meta_title="",
        current_meta_description="",
        matched_queries=[],
        opportunity_score=50,
        niche_summary="",
        ga4_metrics={},
        trend_top=[],
        trend_rising=[],
        stock_qty=None,
        stock_status="",
        language="de",
    )
    assert "allemand" in prompt
    assert "Deutschland" in prompt


def test_grounding_prompt_targets_the_selected_market() -> None:
    from app.niche.signals.realtime_trends import _build_prompt, _build_verify_prompt

    prompt = _build_prompt("tienda de mascotas", ["Arnés para perros"], "es")
    assert "España" in prompt
    assert "español" in prompt
    verify = _build_verify_prompt(["arnés perro"], "mascotas", "es")
    assert "España" in verify
