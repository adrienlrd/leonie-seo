"""Tests for blog and collection brief generators."""

from __future__ import annotations

from app.llm.briefs import (
    BlogBriefResult,
    CollectionBriefResult,
    generate_blog_brief,
    generate_blog_briefs,
    generate_collection_brief,
    generate_collection_briefs,
)
from app.llm.provider import CompletionResult, LLMError, LLMProvider
from app.llm.router import LLMRouter


def _make_router(text: str = "Brief généré.", *, raises: Exception | None = None) -> LLMRouter:
    class _FakeProvider(LLMProvider):
        name = "fake"
        model = "fake-model"

        def complete(self, prompt, *, system="", max_tokens=512, temperature=0.3):
            if raises is not None:
                raise raises
            return CompletionResult(text=text, provider="fake", model="fake-model")

    router = object.__new__(LLMRouter)
    router.providers = [_FakeProvider()]
    router._shop = None
    return router


def _gap(
    query: str = "comment choisir harnais chien",
    impressions: int = 100,
    position: float = 8.5,
    cluster_name: str | None = "harnais chien",
) -> dict:
    return {
        "query": query,
        "impressions": impressions,
        "clicks": 10,
        "position": position,
        "cluster_name": cluster_name,
        "saturation": "medium",
        "opportunity_score": 0.65,
    }


def _cluster(
    name: str = "harnais chien",
    size: int = 5,
    keywords: list[str] | None = None,
) -> dict:
    return {
        "name": name,
        "product_ids": [f"gid://shopify/Product/{i}" for i in range(size)],
        "product_titles": [f"Harnais {i}" for i in range(size)],
        "keywords": keywords or ["harnais", "chien", "cuir", "confort"],
        "size": size,
    }


# ---------------------------------------------------------------------------
# BlogBriefResult
# ---------------------------------------------------------------------------


def test_blog_brief_result_success_property():
    r = BlogBriefResult(
        query="q",
        intent="informational",
        cluster_name=None,
        impressions=50,
        current_position=9.0,
        brief="Le brief",
        provider="fake",
    )
    assert r.success is True


def test_blog_brief_result_failure_when_error():
    r = BlogBriefResult(
        query="q",
        intent="informational",
        cluster_name=None,
        impressions=50,
        current_position=9.0,
        error="LLM failed",
    )
    assert r.success is False


def test_blog_brief_result_failure_when_empty_brief():
    r = BlogBriefResult(
        query="q",
        intent="informational",
        cluster_name=None,
        impressions=50,
        current_position=9.0,
        brief="",
        provider="fake",
    )
    assert r.success is False


# ---------------------------------------------------------------------------
# generate_blog_brief
# ---------------------------------------------------------------------------


def test_generate_blog_brief_success():
    router = _make_router("**H1 :** Meilleur harnais pour chien\n**Intention :** ...")
    result = generate_blog_brief(_gap(), router)

    assert result.success is True
    assert result.query == "comment choisir harnais chien"
    assert result.intent == "informational"
    assert result.cluster_name == "harnais chien"
    assert result.impressions == 100
    assert result.provider == "fake"
    assert "H1" in result.brief


def test_generate_blog_brief_detects_intent_automatically():
    router = _make_router("brief")
    result = generate_blog_brief(_gap(query="acheter harnais chien cuir"), router)
    assert result.intent == "transactional"


def test_generate_blog_brief_handles_llm_error():
    router = _make_router(raises=LLMError("API down"))
    result = generate_blog_brief(_gap(), router)

    assert result.success is False
    assert "API down" in result.error


def test_generate_blog_brief_no_cluster():
    router = _make_router("brief")
    result = generate_blog_brief(_gap(cluster_name=None), router)
    assert result.cluster_name is None
    assert result.success is True


def test_generate_blog_brief_position_zero_becomes_non_classe():
    """Position 0 means not ranked — should send 'non classé' string to LLM."""
    router = _make_router("brief")
    # Just verify no error is raised — the internal render is tested in test_prompts.py
    result = generate_blog_brief(_gap(position=0.0), router)
    assert result.success is True


# ---------------------------------------------------------------------------
# generate_blog_briefs (batch)
# ---------------------------------------------------------------------------


def test_generate_blog_briefs_returns_all():
    router = _make_router("brief text")
    gaps = [_gap(query=f"query {i}") for i in range(3)]
    results = generate_blog_briefs(gaps, router, max_workers=2)

    assert len(results) == 3
    assert all(r.success for r in results)


def test_generate_blog_briefs_empty_input():
    router = _make_router("brief")
    assert generate_blog_briefs([], router) == []


def test_generate_blog_briefs_partial_failures():
    call_count = [0]

    class _FlakyProvider(LLMProvider):
        name = "flaky"
        model = "m"

        def complete(self, prompt, *, system="", max_tokens=512, temperature=0.3):
            call_count[0] += 1
            if call_count[0] % 2 == 0:
                raise LLMError("rate limited")
            return CompletionResult(text="brief", provider="flaky", model="m")

    router = object.__new__(LLMRouter)
    router.providers = [_FlakyProvider()]
    router._shop = None

    gaps = [_gap(query=f"q{i}") for i in range(4)]
    results = generate_blog_briefs(gaps, router, max_workers=1)

    assert len(results) == 4
    successes = [r for r in results if r.success]
    failures = [r for r in results if not r.success]
    assert len(successes) == 2
    assert len(failures) == 2


# ---------------------------------------------------------------------------
# CollectionBriefResult
# ---------------------------------------------------------------------------


def test_collection_brief_result_success_property():
    r = CollectionBriefResult(
        cluster_name="harnais chien",
        product_count=5,
        brief="brief",
        provider="fake",
    )
    assert r.success is True


def test_collection_brief_result_failure_when_error():
    r = CollectionBriefResult(
        cluster_name="harnais chien",
        product_count=5,
        error="failed",
    )
    assert r.success is False


# ---------------------------------------------------------------------------
# generate_collection_brief
# ---------------------------------------------------------------------------


def test_generate_collection_brief_success():
    router = _make_router("**H1 :** Harnais chien premium\n**Meta title :** ...")
    result = generate_collection_brief(_cluster(), router)

    assert result.success is True
    assert result.cluster_name == "harnais chien"
    assert result.product_count == 5
    assert result.provider == "fake"
    assert "H1" in result.brief


def test_generate_collection_brief_handles_llm_error():
    router = _make_router(raises=LLMError("timeout"))
    result = generate_collection_brief(_cluster(), router)

    assert result.success is False
    assert "timeout" in result.error


def test_generate_collection_brief_uses_keywords():
    captured = []

    class _CapturingProvider(LLMProvider):
        name = "cap"
        model = "m"

        def complete(self, prompt, *, system="", max_tokens=512, temperature=0.3):
            captured.append(prompt)
            return CompletionResult(text="brief", provider="cap", model="m")

    router = object.__new__(LLMRouter)
    router.providers = [_CapturingProvider()]
    router._shop = None

    result = generate_collection_brief(
        _cluster(keywords=["harnais", "cuir", "confort", "chien"]), router
    )

    assert result.success is True
    assert "harnais" in captured[0]
    assert "cuir" in captured[0]


# ---------------------------------------------------------------------------
# generate_collection_briefs (batch)
# ---------------------------------------------------------------------------


def test_generate_collection_briefs_returns_all():
    router = _make_router("brief")
    clusters = [_cluster(name=f"cluster {i}") for i in range(3)]
    results = generate_collection_briefs(clusters, router, max_workers=2)

    assert len(results) == 3
    assert all(r.success for r in results)


def test_generate_collection_briefs_empty_input():
    router = _make_router("brief")
    assert generate_collection_briefs([], router) == []
