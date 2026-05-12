"""Tests for concurrent LLM batch generation."""

from __future__ import annotations

import pytest

from app.llm.batch import MetaResult, _primary_keyword, generate_meta_for_products
from app.llm.provider import CompletionResult, LLMError, LLMProvider
from app.llm.router import LLMRouter


def _make_router(responses: list) -> LLMRouter:
    """Build a router whose provider returns responses in order."""
    call_count = [0]

    class _FakeProvider(LLMProvider):
        name = "fake"
        model = "fake-model"

        def complete(self, prompt, *, system="", max_tokens=512, temperature=0.3):
            idx = call_count[0]
            call_count[0] += 1
            r = responses[idx % len(responses)]
            if isinstance(r, Exception):
                raise r
            return CompletionResult(text=r, provider="fake", model="fake-model")

    router = object.__new__(LLMRouter)
    router.providers = [_FakeProvider()]
    router._shop = None
    return router


def _products(n: int) -> list[dict]:
    return [
        {
            "id": f"gid://shopify/Product/{i}",
            "title": f"Produit {i}",
            "product_type": "Vêtements chien",
            "body_html": f"Description du produit {i}.",
        }
        for i in range(n)
    ]


# ── MetaResult ─────────────────────────────────────────────────────────────────


def test_meta_result_success_when_title_generated():
    r = MetaResult(
        product_id="1",
        product_title="P",
        generated_title="T",
        generated_description="D",
        provider="openai",
    )
    assert r.success is True


def test_meta_result_not_success_when_error():
    r = MetaResult(product_id="1", product_title="P", error="failed")
    assert r.success is False


def test_meta_result_not_success_when_empty_title():
    r = MetaResult(product_id="1", product_title="P", generated_title="", generated_description="D")
    assert r.success is False


# ── _primary_keyword ───────────────────────────────────────────────────────────


def test_primary_keyword_strips_brand_name():
    kw = _primary_keyword("Pardessus Léonie pour chien", brand="Léonie Delacroix")
    assert "léonie" not in kw.lower()
    assert "pardessus" in kw


def test_primary_keyword_returns_lowercase():
    kw = _primary_keyword("Fontaine À Eau Chat", brand="Léonie Delacroix")
    assert kw == kw.lower()


def test_primary_keyword_falls_back_to_title_when_all_brand():
    kw = _primary_keyword("Léonie", brand="Léonie Delacroix")
    assert kw  # not empty


def test_primary_keyword_without_brand_returns_full_title():
    """When no brand is provided, the title passes through unchanged (lowercased)."""
    kw = _primary_keyword("Pardessus Léonie pour chien")
    assert kw == "pardessus léonie pour chien"


def test_primary_keyword_with_different_brand_per_tenant():
    """Multi-tenant: brand="Bijou de Paris" must strip Bijou and Paris tokens."""
    kw = _primary_keyword("Collier Bijou Paris Or", brand="Bijou de Paris")
    assert "bijou" not in kw
    assert "paris" not in kw
    assert "collier" in kw


# ── generate_meta_for_products ────────────────────────────────────────────────


def test_generate_meta_returns_one_result_per_product():
    router = _make_router(["Meta title", "Meta description"] * 10)
    results = generate_meta_for_products(_products(3), router, max_workers=3)
    assert len(results) == 3


def test_generate_meta_marks_failure_on_llm_error():
    # First call (title) raises, second (description) would succeed — error is captured.
    router = _make_router([LLMError("quota exceeded")])
    results = generate_meta_for_products(_products(1), router, max_workers=1)
    assert len(results) == 1
    assert results[0].success is False
    assert "quota exceeded" in results[0].error


def test_generate_meta_partial_failure_does_not_stop_batch():
    """One failing product must not abort the others."""
    responses = [
        LLMError("fail"),  # product 0 title → error
        "Good title",  # product 1 title
        "Good desc",  # product 1 description
    ]
    router = _make_router(responses)
    results = generate_meta_for_products(_products(2), router, max_workers=2)
    assert len(results) == 2
    successes = [r for r in results if r.success]
    failures = [r for r in results if not r.success]
    assert len(successes) == 1
    assert len(failures) == 1


def test_generate_meta_returns_empty_for_empty_input():
    router = _make_router(["title", "desc"])
    results = generate_meta_for_products([], router)
    assert results == []


def test_generate_meta_uses_correct_product_fields():
    captured = []

    class _CapturingProvider(LLMProvider):
        name = "fake"
        model = "fake"

        def complete(self, prompt, *, system="", max_tokens=512, temperature=0.3):
            captured.append(prompt)
            return CompletionResult(text="Result", provider="fake", model="fake")

    router = object.__new__(LLMRouter)
    router.providers = [_CapturingProvider()]
    router._shop = None

    products = [
        {"id": "1", "title": "Harnais Chat", "product_type": "Harnais", "body_html": "Desc."}
    ]
    generate_meta_for_products(products, router, max_workers=1)

    # The title prompt should contain the product title
    assert any("Harnais Chat" in p for p in captured)


# ── meta_store ─────────────────────────────────────────────────────────────────


def test_save_and_list_results(tmp_path):
    from app.db import init_db
    from app.llm.meta_store import list_suggestions, save_results

    db = tmp_path / "test.db"
    init_db(db)

    results = [
        MetaResult(
            product_id="1",
            product_title="P1",
            generated_title="T1",
            generated_description="D1",
            provider="openai",
        ),
        MetaResult(product_id="2", product_title="P2", error="fail"),
    ]
    save_results(results, shop="myshop.myshopify.com", job_id="job-123", db_path=db)

    rows = list_suggestions("myshop.myshopify.com", db_path=db)
    assert len(rows) == 2


def test_list_suggestions_filters_by_status(tmp_path):
    from app.db import init_db
    from app.llm.meta_store import list_suggestions, save_results

    db = tmp_path / "test.db"
    init_db(db)

    results = [
        MetaResult(
            product_id="1",
            product_title="P",
            generated_title="T",
            generated_description="D",
            provider="openai",
        ),
        MetaResult(product_id="2", product_title="P", error="fail"),
    ]
    save_results(results, shop="shop.myshopify.com", job_id="j", db_path=db)

    pending = list_suggestions("shop.myshopify.com", status="pending", db_path=db)
    errors = list_suggestions("shop.myshopify.com", status="error", db_path=db)
    assert len(pending) == 1
    assert len(errors) == 1


def test_update_status_changes_row(tmp_path):
    from app.db import init_db
    from app.llm.meta_store import list_suggestions, save_results, update_status

    db = tmp_path / "test.db"
    init_db(db)

    results = [
        MetaResult(
            product_id="1",
            product_title="P",
            generated_title="T",
            generated_description="D",
            provider="openai",
        )
    ]
    save_results(results, shop="s.myshopify.com", job_id="j", db_path=db)

    rows = list_suggestions("s.myshopify.com", db_path=db)
    update_status(rows[0]["id"], "approved", db_path=db)

    approved = list_suggestions("s.myshopify.com", status="approved", db_path=db)
    assert len(approved) == 1


def test_update_status_rejects_invalid_status(tmp_path):
    from app.llm.meta_store import update_status

    with pytest.raises(ValueError, match="Invalid status"):
        update_status(1, "unknown")
