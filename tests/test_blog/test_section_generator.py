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
    assert out == {"direct_answer": "", "body": "", "claims_used": []}
