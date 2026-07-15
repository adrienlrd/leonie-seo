"""Per-section blog generator: fact-grounded output with claims_used."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from app.blog.section_generator import generate_section
from app.llm.provider import CompletionResult


def _completion(payload: dict) -> CompletionResult:
    return CompletionResult(text=json.dumps(payload), provider="openai", model="m")


def test_generate_section_returns_structured_chunks():
    router = MagicMock()
    router.complete.return_value = _completion(
        {
            "direct_answer": "Une fontaine inox pour chat encourage l'hydratation en oxygénant l'eau.",
            "body": "L'inox est résistant à la corrosion…",
            "claims_used": [{"claim": "Capacité 2,8 L", "fact_keys": ["description"]}],
        }
    )
    with patch("app.blog.section_generator.get_router", return_value=router):
        out = generate_section(
            blog_title="Guide fontaine chat",
            h2_question="Pourquoi choisir une fontaine en inox ?",
            product_title="Fontaine Smart",
            product_summary="Fontaine sans fil 2,8L.",
            confirmed_facts=[{"key": "description", "value": "2,8 litres, sans fil"}],
            shop="s.myshopify.com",
        )

    assert out["direct_answer"].startswith("Une fontaine inox")
    assert out["body"]
    assert out["claims_used"][0]["fact_keys"] == ["description"]

    # The call was made deterministic + json-mode (so the parser is reliable).
    kwargs = router.complete.call_args.kwargs
    assert kwargs["temperature"] == 0.0
    assert kwargs["json_mode"] is True


def test_generate_section_falls_back_on_parse_failure():
    router = MagicMock()
    router.complete.return_value = CompletionResult(
        text="not json", provider="openai", model="m"
    )
    with patch("app.blog.section_generator.get_router", return_value=router):
        out = generate_section(
            blog_title="x",
            h2_question="y",
            product_title="z",
            product_summary="",
            confirmed_facts=[],
        )
    assert out == {"direct_answer": "", "body": "", "claims_used": [], "citations": []}


def test_agency_shop_uses_grounded_tier_and_returns_citations():
    router = MagicMock()
    router.complete.return_value = CompletionResult(
        text=json.dumps({"direct_answer": "x", "body": "y", "claims_used": []}),
        provider="gemini",
        model="gemini-3.1-flash-lite",
        citations=[{"url": "https://example.com", "title": "Example"}],
    )
    with (
        patch("app.blog.section_generator.get_plan_for_shop", return_value="agency"),
        patch("app.blog.section_generator.get_router", return_value=router) as mock_get_router,
    ):
        out = generate_section(
            blog_title="x",
            h2_question="y",
            product_title="z",
            product_summary="",
            confirmed_facts=[],
            shop="agency-shop.myshopify.com",
        )
    mock_get_router.assert_called_once_with(shop="agency-shop.myshopify.com", tier="grounded")
    assert out["citations"] == [{"url": "https://example.com", "title": "Example"}]


def test_agency_shop_reads_sources_the_model_wrote_into_its_own_json():
    """Verified live: Gemini's groundingMetadata side-channel is absent when
    grounding + forced JSON are combined, so `sources` must be requested
    directly in the JSON schema and read from there (see _build_prompt's
    `grounded` param). completion.citations (the side channel) stays empty
    in this scenario but is still merged in case the API ever changes."""
    router = MagicMock()
    router.complete.return_value = CompletionResult(
        text=json.dumps(
            {
                "direct_answer": "x",
                "body": "y",
                "claims_used": [],
                "sources": [{"url": "https://meteo.fr/canicule", "title": "Météo France"}],
            }
        ),
        provider="gemini",
        model="gemini-3.1-flash-lite",
        citations=[],
    )
    with (
        patch("app.blog.section_generator.get_plan_for_shop", return_value="agency"),
        patch("app.blog.section_generator.get_router", return_value=router),
    ):
        out = generate_section(
            blog_title="x",
            h2_question="y",
            product_title="z",
            product_summary="",
            confirmed_facts=[],
            shop="agency-shop.myshopify.com",
        )
    assert out["citations"] == [{"url": "https://meteo.fr/canicule", "title": "Météo France"}]
    prompt = router.complete.call_args.args[0]
    assert "sources" in prompt
    assert "N'invente JAMAIS une URL" in prompt


def test_free_shop_prompt_does_not_request_sources():
    router = MagicMock()
    router.complete.return_value = CompletionResult(
        text=json.dumps({"direct_answer": "x", "body": "y", "claims_used": []}),
        provider="openai",
        model="gpt-4o-mini",
    )
    with (
        patch("app.blog.section_generator.get_plan_for_shop", return_value="free"),
        patch("app.blog.section_generator.get_router", return_value=router),
    ):
        generate_section(
            blog_title="x",
            h2_question="y",
            product_title="z",
            product_summary="",
            confirmed_facts=[],
            shop="free-shop.myshopify.com",
        )
    prompt = router.complete.call_args.args[0]
    assert "sources" not in prompt


def test_free_shop_uses_default_tier_and_has_no_citations():
    router = MagicMock()
    router.complete.return_value = CompletionResult(
        text=json.dumps({"direct_answer": "x", "body": "y", "claims_used": []}),
        provider="openai",
        model="gpt-4o-mini",
    )
    with (
        patch("app.blog.section_generator.get_plan_for_shop", return_value="free"),
        patch("app.blog.section_generator.get_router", return_value=router) as mock_get_router,
    ):
        out = generate_section(
            blog_title="x",
            h2_question="y",
            product_title="z",
            product_summary="",
            confirmed_facts=[],
            shop="free-shop.myshopify.com",
        )
    mock_get_router.assert_called_once_with(shop="free-shop.myshopify.com", tier="default")
    assert out["citations"] == []


def test_no_shop_uses_default_tier_without_billing_lookup():
    router = MagicMock()
    router.complete.return_value = CompletionResult(
        text=json.dumps({"direct_answer": "x", "body": "y", "claims_used": []}),
        provider="openai",
        model="gpt-4o-mini",
    )
    with (
        patch("app.blog.section_generator.get_plan_for_shop") as mock_plan,
        patch("app.blog.section_generator.get_router", return_value=router) as mock_get_router,
    ):
        generate_section(
            blog_title="x", h2_question="y", product_title="z", product_summary="", confirmed_facts=[]
        )
    mock_plan.assert_not_called()
    mock_get_router.assert_called_once_with(shop=None, tier="default")


def test_keywords_are_injected_into_the_prompt():
    router = MagicMock()
    router.complete.return_value = _completion({"direct_answer": "x", "body": "y", "claims_used": []})
    with patch("app.blog.section_generator.get_router", return_value=router):
        generate_section(
            blog_title="Guide fontaine",
            h2_question="Pourquoi une fontaine ?",
            product_title="Fontaine Smart",
            product_summary="",
            confirmed_facts=[],
            keywords="fontaine à eau pour chat, fontaine silencieuse",
        )
    prompt = router.complete.call_args.args[0]
    assert "fontaine à eau pour chat" in prompt
    assert "MOTS-CLÉS" in prompt
