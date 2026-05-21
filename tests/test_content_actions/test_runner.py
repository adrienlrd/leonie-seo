"""Tests for the Content Actions runner orchestrator."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.content_actions.schema import (
    ContentActionRequest,
    ContentStatus,
    ContentType,
    PreviousContent,
    ResourceInput,
)


def _make_request(
    ct: ContentType = ContentType.META_TITLE,
    resource_id: str = "gid://shopify/Product/1",
    feedback: str | None = None,
) -> ContentActionRequest:
    return ContentActionRequest(
        content_type=ct,
        resource=ResourceInput(id=resource_id, title="Harnais nylon chien"),
        previous_content=PreviousContent(feedback=feedback),
    )


def _make_niche(status: str = "validated_by_merchant") -> dict:
    return {
        "status": status,
        "shop_summary": {"primary_niche": "accessoires animaux"},
        "brand_voice": {"tone": "professionnel", "do_not_say": []},
        "marketing_angles": ["durabilité", "confort"],
        "customer_segments": [{"label": "propriétaires de chiens"}],
        "forbidden_promises": [],
        "conversational_intents": [],
    }


def _mock_llm_router(text: str = "Harnais nylon chien réglable confort quotidien") -> MagicMock:
    from app.llm.provider import CompletionResult  # noqa: PLC0415

    router = MagicMock()
    router.complete.return_value = CompletionResult(text=text, provider="openai", model="gpt-4o-mini")
    return router


# ── run_content_action ────────────────────────────────────────────────────────


def test_run_meta_title_returns_result(tmp_path):
    from app.content_actions.runner import run_content_action  # noqa: PLC0415

    request = _make_request(ContentType.META_TITLE)
    router = _mock_llm_router("Harnais nylon chien réglable confort et sécurité")

    with (
        patch("app.observability.metrics.check_budget", return_value={"over_budget": False}),
        patch("app.content_actions.runner._persist_action"),
    ):
        result = run_content_action(
            request,
            "shop.myshopify.com",
            niche_hypothesis=None,
            llm_router=router,
            plan="pro",
            db_path=tmp_path / "test.db",
        )

    assert result.content_type == ContentType.META_TITLE
    assert result.output.primary_text != ""
    assert result.action_id != ""
    assert result.status in {ContentStatus.DRAFT, ContentStatus.NEEDS_REVIEW}


def test_run_factual_content_requires_validated_niche():
    from app.content_actions.runner import run_content_action  # noqa: PLC0415

    request = _make_request(ContentType.PRODUCT_DESCRIPTION)
    router = _mock_llm_router()

    with pytest.raises(ValueError, match="merchant-validated niche hypothesis"):
        run_content_action(
            request,
            "shop.myshopify.com",
            niche_hypothesis=None,
            llm_router=router,
            plan="free",
        )


def test_run_factual_content_refused_when_niche_not_validated():
    from app.content_actions.runner import run_content_action  # noqa: PLC0415

    request = _make_request(ContentType.FAQ_BLOCK)
    router = _mock_llm_router()
    niche = _make_niche(status="pending")

    with pytest.raises(ValueError, match="merchant-validated niche hypothesis"):
        run_content_action(
            request,
            "shop.myshopify.com",
            niche_hypothesis=niche,
            llm_router=router,
            plan="free",
        )


def test_run_budget_exceeded_raises():
    from app.content_actions.runner import run_content_action  # noqa: PLC0415

    request = _make_request(ContentType.META_TITLE)
    router = _mock_llm_router()

    with (
        patch("app.observability.metrics.check_budget", return_value={"over_budget": True}),
        pytest.raises(ValueError, match="budget exceeded"),
    ):
        run_content_action(
            request,
            "shop.myshopify.com",
            niche_hypothesis=None,
            llm_router=router,
            plan="pro",
        )


def test_run_forbidden_promise_triggers_needs_review():
    from app.content_actions.runner import run_content_action  # noqa: PLC0415
    from app.content_actions.schema import NicheContext  # noqa: PLC0415

    niche_text = "Ce produit guérit les douleurs articulaires de votre chien."
    router = _mock_llm_router(niche_text)
    request = ContentActionRequest(
        content_type=ContentType.META_TITLE,
        resource=ResourceInput(id="gid://shopify/Product/1", title="Harnais"),
        niche_context=NicheContext(
            primary_niche="petfood",
            forbidden_promises=["guérit"],
        ),
    )

    with (
        patch("app.observability.metrics.check_budget", return_value={"over_budget": False}),
        patch("app.content_actions.runner._persist_action"),
    ):
        result = run_content_action(
            request,
            "shop.myshopify.com",
            niche_hypothesis=None,
            llm_router=router,
            plan="pro",
        )

    assert result.status == ContentStatus.NEEDS_REVIEW
    assert result.constraints_check.forbidden_promise_violations != []


def test_run_jsonld_faqpage_no_llm_call():
    from app.content_actions.runner import run_content_action  # noqa: PLC0415

    faq_content = '{"items": [{"question": "Quelle taille ?", "answer": "M et L disponibles."}]}'
    request = ContentActionRequest(
        content_type=ContentType.JSONLD_FAQPAGE,
        resource=ResourceInput(id="gid://shopify/Product/1", title="Harnais"),
        previous_content=PreviousContent(content=faq_content),
    )
    router = MagicMock()

    with patch("app.content_actions.runner._persist_action"):
        result = run_content_action(
            request,
            "shop.myshopify.com",
            niche_hypothesis=None,
            llm_router=router,
            plan="free",
        )

    router.complete.assert_not_called()
    assert result.llm_meta.tier == "deterministic"
    assert "@type" in result.output.primary_text


def test_run_jsonld_faqpage_requires_previous_content():
    from app.content_actions.runner import run_content_action  # noqa: PLC0415

    request = _make_request(ContentType.JSONLD_FAQPAGE)

    with pytest.raises(ValueError, match="previous_content"):
        run_content_action(
            request,
            "shop.myshopify.com",
            niche_hypothesis=None,
            plan="free",
        )


def test_low_cost_only_env_var_forces_low_cost_tier(monkeypatch):
    from app.content_actions.runner import _effective_tier  # noqa: PLC0415

    monkeypatch.setenv("LEONIE_LLM_LOW_COST_ONLY", "true")
    assert _effective_tier(ContentType.PRODUCT_DESCRIPTION) == "low-cost"
    assert _effective_tier(ContentType.FAQ_BLOCK) == "low-cost"
    assert _effective_tier(ContentType.META_TITLE) == "low-cost"


def test_low_cost_only_env_var_preserves_deterministic(monkeypatch):
    from app.content_actions.runner import ContentType as CT  # noqa: PLC0415
    from app.content_actions.runner import _effective_tier  # noqa: PLC0415

    monkeypatch.setenv("LEONIE_LLM_LOW_COST_ONLY", "true")
    assert _effective_tier(CT.JSONLD_FAQPAGE) == "deterministic"


def test_effective_tier_returns_normal_when_env_unset(monkeypatch):
    from app.content_actions.runner import _effective_tier  # noqa: PLC0415

    monkeypatch.delenv("LEONIE_LLM_LOW_COST_ONLY", raising=False)
    assert _effective_tier(ContentType.PRODUCT_DESCRIPTION) == "medium"
    assert _effective_tier(ContentType.META_TITLE) == "low-cost"


def test_run_meta_title_with_validated_niche():
    from app.content_actions.runner import run_content_action  # noqa: PLC0415

    request = _make_request(ContentType.META_TITLE)
    router = _mock_llm_router("Harnais nylon chien réglable — confort et sécurité")
    niche = _make_niche()

    with (
        patch("app.observability.metrics.check_budget", return_value={"over_budget": False}),
        patch("app.content_actions.runner._persist_action"),
    ):
        result = run_content_action(
            request,
            "shop.myshopify.com",
            niche_hypothesis=niche,
            llm_router=router,
            plan="pro",
        )

    assert result.output.primary_text != ""
    assert result.action_id != ""
