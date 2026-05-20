"""Tests for merchant niche understanding runtime."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from app.db import init_db
from app.llm.provider import CompletionResult
from app.niche.understanding import (
    generate_niche_hypothesis,
    get_niche_hypothesis,
    get_niche_hypothesis_history,
    get_validated_niche_hypothesis,
    save_niche_hypothesis,
)

SHOP = "store.myshopify.com"


class _FakeRouter:
    def __init__(self, text: str) -> None:
        self.text = text
        self.calls = 0

    def complete(self, *args, **kwargs) -> CompletionResult:
        self.calls += 1
        return CompletionResult(
            text=self.text,
            provider="fake",
            model="fake-advanced",
            tokens_in=100,
            tokens_out=50,
        )


def _products() -> list[dict]:
    return [
        {
            "id": "gid://shopify/Product/1",
            "title": "Harnais chien nylon",
            "product_type": "Harnais",
            "tags": ["chien", "nylon"],
            "status": "ACTIVE",
            "onlineStoreUrl": "https://example.com/products/harnais",
        }
    ]


def _gsc_queries() -> list[dict]:
    return [{"query": "harnais chien nylon", "impressions": 100, "clicks": 8, "position": 5.0}]


def _llm_json() -> str:
    return json.dumps(
        {
            "shop_summary": {
                "what_you_sell": "Des accessoires de promenade pour chiens.",
                "primary_niche": "Accessoires chien",
                "sub_niches": ["Harnais"],
                "languages_detected": ["fr"],
                "markets_detected": ["FR"],
            },
            "customer_segments": [
                {
                    "id": "dog_owners",
                    "label": "Propriétaires de chiens",
                    "description": "Clients cherchant un harnais fiable.",
                    "size_estimate": "large",
                    "confidence": "high",
                }
            ],
            "buying_motivations": [
                {
                    "segment_id": "dog_owners",
                    "motivation": "Promenade confortable",
                    "evidence": ["from_gsc_query"],
                    "confidence": "high",
                }
            ],
            "objections": [{"objection": "Taille difficile à choisir", "confidence": "medium"}],
            "priority_products": [
                {
                    "product_id": "gid://shopify/Product/1",
                    "reason": "Produit aligné avec la top query.",
                    "confidence": "high",
                }
            ],
            "marketing_angles": [
                {
                    "angle": "Rassurer sur le choix de taille.",
                    "for_segment_id": "dog_owners",
                    "confidence": "medium",
                }
            ],
            "conversational_intents": [
                {
                    "intent": "choisir un harnais chien",
                    "example_queries": ["harnais chien nylon"],
                    "confidence": "high",
                }
            ],
            "probable_competitors": [],
            "brand_voice": {
                "tone": "clair et rassurant",
                "register": "professional",
                "do_say": ["Guide de taille"],
                "do_not_say": ["garanti premier sur Google"],
                "confidence": "high",
            },
            "forbidden_promises": [
                {"promise": "garantir un ranking IA", "reason": "unverifiable"}
            ],
            "global_confidence": "high",
            "missing_inputs": [],
        }
    )


def _patch_config_db(db: Path):
    return patch("app.shop_config_store.DB_PATH", db)


def test_generate_niche_hypothesis_calls_llm_and_persists_result(tmp_path: Path) -> None:
    db = tmp_path / "history.db"
    init_db(db)
    router = _FakeRouter(_llm_json())

    with _patch_config_db(db):
        result = generate_niche_hypothesis(
            SHOP,
            _products(),
            _gsc_queries(),
            router=router,
            db_path=db,
        )
        stored = get_niche_hypothesis(SHOP)

    assert router.calls == 1
    assert result["status"] == "needs_review"
    assert result["shop_summary"]["primary_niche"] == "Accessoires chien"
    assert result["llm_meta"]["provider"] == "fake"
    assert result["cache"]["hit"] is False
    assert stored is not None
    assert stored["brand_voice"]["confidence"] == "high"


def test_generate_niche_hypothesis_uses_cache_when_signal_hash_matches(tmp_path: Path) -> None:
    db = tmp_path / "history.db"
    init_db(db)
    first_router = _FakeRouter(_llm_json())
    second_router = _FakeRouter(_llm_json())

    with _patch_config_db(db):
        generate_niche_hypothesis(
            SHOP,
            _products(),
            _gsc_queries(),
            router=first_router,
            db_path=db,
        )
        cached = generate_niche_hypothesis(
            SHOP,
            _products(),
            _gsc_queries(),
            router=second_router,
            db_path=db,
        )

    assert first_router.calls == 1
    assert second_router.calls == 0
    assert cached["cache"]["hit"] is True


def test_save_niche_hypothesis_keeps_history_and_validated_gate(tmp_path: Path) -> None:
    db = tmp_path / "history.db"
    init_db(db)
    base = json.loads(_llm_json())

    with _patch_config_db(db):
        first = save_niche_hypothesis(SHOP, {**base, "status": "needs_review"})
        assert get_validated_niche_hypothesis(SHOP) is None

        second = save_niche_hypothesis(
            SHOP,
            {
                **first,
                "status": "validated_by_merchant",
                "shop_summary": {**first["shop_summary"], "primary_niche": "Dog gear"},
            },
        )
        history = get_niche_hypothesis_history(SHOP)
        validated = get_validated_niche_hypothesis(SHOP)

    assert second["status"] == "validated_by_merchant"
    assert len(history) == 1
    assert history[0]["status"] == "needs_review"
    assert validated is not None
    assert validated["shop_summary"]["primary_niche"] == "Dog gear"


def test_generate_niche_hypothesis_can_use_deterministic_fallback(tmp_path: Path) -> None:
    db = tmp_path / "history.db"
    init_db(db)

    with _patch_config_db(db):
        result = generate_niche_hypothesis(
            SHOP,
            _products(),
            _gsc_queries(),
            use_llm=False,
            db_path=db,
        )

    assert result["llm_meta"]["provider"] == "deterministic"
    assert result["shop_summary"]["primary_niche"]
