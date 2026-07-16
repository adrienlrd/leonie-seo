"""Tests for the two-pass market analysis engine.

Pass 1 produces understanding + candidate keywords; pass 2 writes the content
pack informed by real SERP/PAA/volume/crawl data.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from app.market_analysis import engine

_SHOP = "test.myshopify.com"

_PASS1_JSON = json.dumps(
    {
        "product_summary": "Fontaine à eau pour chat, 2 litres, filtre charbon.",
        "target_customer": "Propriétaires de chats exigeants.",
        "buying_intents": ["hydratation", "silence"],
        "seo_keywords": [
            {
                "query": "fontaine à chat",
                "intent_type": "commercial",
                "demand_score": 50,
                "competition_score": 40,
                "product_fit_score": 90,
                "reason": "produit principal",
            }
        ],
        "geo_questions": [
            {
                "question": "Comment ça marche ?",
                "answer_angle": "filtration",
                "content_block_type": "faq",
                "confidence": "high",
            }
        ],
    }
)

_PASS2_JSON = json.dumps(
    {
        "proposed_meta_title": "Fontaine à chat silencieuse 2L — eau filtrée en continu",
        "proposed_meta_description": "Hydratez votre chat avec une eau toujours fraîche et filtrée.",
        "proposed_product_title_if_different": "Fontaine à chat 2L",
        "proposed_product_description": "Une fontaine silencieuse qui oxygène l'eau.",
        "proposed_faq": [
            {
                "q": "Comment nettoyer la fontaine à chat ?",
                "a": "Démontez et rincez chaque semaine.",
            }
        ],
        "proposed_geo_answer_block": "La fontaine à chat oxygène l'eau en continu pour encourager l'hydratation.",
        "proposed_blog_title": "Pourquoi votre chat boit-il peu ?",
        "proposed_blog_outline": ["Hydratation", "Solutions"],
        "proposed_blog_intro": "Les chats boivent peu...",
        "recommended_content_actions": ["Ajouter une FAQ"],
        "facts_used": ["2 litres"],
        "facts_missing": ["matériau exact"],
        "claims_used": [{"claim": "Contenance 2L", "fact_keys": ["description"]}],
        "confidence": "high",
    }
)


class _FakeDataForSEO:
    """DataForSEO stub with deterministic enrichment + SERP intelligence."""

    available = True

    def enrich(self, signals, *, shop):  # noqa: ARG002
        for sig in signals:
            sig["source"] = "dataforseo"
            sig["search_volume"] = 1200
            sig["difficulty_score"] = 42
            sig["difficulty_source"] = "dataforseo"
        return signals

    def fetch_serp_intelligence(self, keywords):
        return {
            keywords[0].strip().lower(): {
                "paa": ["Comment nettoyer une fontaine à chat ?"],
                "top_competitors": [
                    {
                        "domain": "concurrent.fr",
                        "title": "Fontaine à chat silencieuse",
                        "url": "https://c.fr",
                        "rank": 1,
                    }
                ],
                "featured_snippet": "Une fontaine à chat oxygène l'eau.",
            }
        }

    def fetch_serp_competitors(self, keywords):  # noqa: ARG002
        return []

    def fetch_keyword_ideas(self, seeds, *, limit=15):  # noqa: ARG002
        return []

    def fetch_domain_competitors(self, domain, *, limit=20):  # noqa: ARG002
        return []


class _FakeDataForSEOWithWinningIdea(_FakeDataForSEO):
    """Provider returning an idea that should become the selected primary target."""

    requested_serp_keywords: list[str]

    def __init__(self) -> None:
        self.requested_serp_keywords = []

    def fetch_keyword_ideas(self, seeds, *, limit=15):  # noqa: ARG002
        return [
            {
                "query": "fontaine chat silencieuse",
                "intent_type": "commercial",
                "demand_score": 95,
                "competition_score": 15,
                "product_fit_score": 0,
                "reason": "suggestion à haut potentiel",
                "data_source": "dataforseo",
                "difficulty_source": "dataforseo",
                "search_volume": 5000,
                "cpc": 1.25,
                "ads_competition": 0.2,
                "notes": [],
            }
        ]

    def fetch_serp_intelligence(self, keywords):
        self.requested_serp_keywords = list(keywords)
        return {
            keyword.lower(): {
                "paa": [f"Comment choisir une {keyword} ?"],
                "top_competitors": [],
                "featured_snippet": None,
            }
            for keyword in keywords
        }


def _product():
    return {
        "id": "gid://shopify/Product/1",
        "title": "Fontaine à chat",
        "handle": "fontaine-chat",
        "status": "ACTIVE",
        "body_html": "<p>Fontaine 2L</p>",
        "seo": {"title": "Fontaine chat", "description": ""},
        "variants": [{"price": "29.90", "inventory_quantity": 15}],
    }


def _router(*texts):
    from app.llm.provider import CompletionResult  # noqa: PLC0415

    router = MagicMock()
    router.complete.side_effect = [
        CompletionResult(text=t, provider="openai", model="gpt-4o-mini") for t in texts
    ]
    return router


def _run(
    router,
    *,
    dataforseo,
    over_budget=False,
    crawl_findings=None,
    business_profile=None,
    reflection_test=False,
):
    budget = {
        "over_budget": over_budget,
        "budget_usd": 20.0,
        "spent_usd": 0.0,
        "remaining_usd": 20.0,
        "usage_pct": 0.0,
        "alert": None,
    }
    with (
        patch.object(engine, "get_router", return_value=router),
        patch.object(engine, "check_budget", return_value=budget),
        patch.object(engine, "_fetch_trends_once", return_value=[]),
        patch.object(engine, "fetch_suggestions_bulk", return_value=[]),
        patch.object(engine, "DataForSEOProvider", return_value=dataforseo),
    ):
        return engine.run_market_analysis(
            [_product()],
            _SHOP,
            {},
            [],
            crawl_findings=crawl_findings,
            business_profile=business_profile,
            reflection_test=reflection_test,
        )


def test_two_pass_feeds_serp_paa_volume_crawl_into_pass2_prompt():
    router = _router(_PASS1_JSON, _PASS2_JSON)
    crawl = [
        {
            "url": "https://test.myshopify.com/products/fontaine-chat",
            "issue_type": "missing_canonical",
            "severity": "low",
            "detail": "Canonical absent",
        }
    ]
    result = _run(router, dataforseo=_FakeDataForSEO(), crawl_findings=crawl)

    assert router.complete.call_count == 2
    pass2_prompt = router.complete.call_args_list[1].args[0]
    assert "Comment nettoyer une fontaine à chat ?" in pass2_prompt  # PAA
    assert "1200/mois" in pass2_prompt  # real volume
    assert "concurrent.fr" in pass2_prompt  # SERP competitor angle
    assert "missing_canonical" in pass2_prompt  # crawl finding
    assert "FAITS PRODUIT CONFIRMÉS" in pass2_prompt
    assert "claims_used" in pass2_prompt
    assert "absent chez" not in pass2_prompt

    pack = result["products"][0]["content_test_pack"]
    assert pack["proposed_meta_title"].startswith("Fontaine à chat silencieuse")
    assert pack["proposed_faq"]
    assert "dataforseo_serp" in result["sources_used"]


def test_reflection_test_retries_low_quality_content_and_exports_attempts():
    bad_pass2 = json.dumps(
        {
            **json.loads(_PASS2_JSON),
            "proposed_meta_title": "Fontaine luxe",
            "proposed_meta_description": "Belle fontaine premium.",
            "proposed_product_description": "Belle fontaine premium pour la maison.",
            "proposed_faq": [],
            "proposed_geo_answer_block": "",
            "proposed_blog_title": "",
            "proposed_blog_outline": [],
            "proposed_blog_intro": "",
            "claims_used": [],
            "confidence": "low",
        }
    )
    improved_pass2 = json.dumps(
        {
            **json.loads(_PASS2_JSON),
            "proposed_meta_title": "Fontaine à chat silencieuse 2L",
            "proposed_meta_description": "Fontaine à chat 2L avec eau filtrée pour aider votre chat à boire plus souvent.",
            "proposed_product_description": "Cette fontaine à chat 2L garde une eau filtrée accessible. Elle aide à créer un point d'hydratation clair pour les chats à la maison.",
            "proposed_geo_answer_block": "Une fontaine à chat 2L maintient une eau filtrée disponible pour encourager l'hydratation quotidienne.",
            "claims_used": [{"claim": "Fontaine 2L", "fact_keys": ["description"]}],
            "confidence": "high",
        }
    )
    router = _router(_PASS1_JSON, bad_pass2, improved_pass2)

    result = _run(router, dataforseo=_FakeDataForSEO(), reflection_test=True)

    pack = result["products"][0]["content_test_pack"]
    reflection = pack["content_guardrail_reflection"]
    assert router.complete.call_count == 3
    assert reflection["enabled"] is True
    assert reflection["retry_count"] == 1
    assert len(reflection["attempts"]) == 2
    assert reflection["attempts"][0]["score"] < reflection["threshold"]
    assert "content_guardrail_reflection" in result["sources_used"]


def test_free_mode_runs_pass2_without_serp_block():
    fake = _FakeDataForSEO()
    fake.available = False
    router = _router(_PASS1_JSON, _PASS2_JSON)
    result = _run(router, dataforseo=fake)

    assert router.complete.call_count == 2
    pass2_prompt = router.complete.call_args_list[1].args[0]
    # The section headers are absent (no data block), but the rules text
    # may still mention PAA/competitors as conditional instructions.
    assert "=== QUESTIONS PAA" not in pass2_prompt
    assert "=== CONCURRENTS SERP" not in pass2_prompt
    # Content still generated.
    assert result["products"][0]["content_test_pack"]["proposed_meta_title"]


def test_business_profile_context_feeds_product_targeting_and_content_prompts():
    router = _router(_PASS1_JSON, _PASS2_JSON)
    profile = {
        "status": "validated",
        "brand_name": "Léonie",
        "niche_summary": "Accessoires premium pour chats urbains.",
        "brand_voice": "Expert, rassurant et précis.",
        "target_personas": [
            {
                "name": "Propriétaire exigeant",
                "main_need": "Choisir un accessoire fiable",
                "buying_trigger": "Remplacer un produit bas de gamme",
            }
        ],
        "content_style": {
            "tone": "expert et pédagogique",
            "vocabulary_to_use": ["hydratation", "entretien simple"],
            "vocabulary_to_avoid": ["miracle"],
        },
        "key_themes": ["bien-être félin", "maison propre"],
        "competitor_domains": ["competitor.example"],
        "competitor_insights": ["Les concurrents insistent sur le silence."],
        "content_gaps": ["Guide de choix par usage"],
        "internal_link_priorities": ["fontaine-chat"],
    }

    result = _run(router, dataforseo=_FakeDataForSEO(), business_profile=profile)

    pass1_prompt = router.complete.call_args_list[0].args[0]
    pass2_prompt = router.complete.call_args_list[1].args[0]
    assert "PROFIL ENTREPRISE VALIDÉ" in pass1_prompt
    assert "Accessoires premium pour chats urbains" in pass1_prompt
    assert "Propriétaire exigeant" in pass2_prompt
    assert "competitor.example" in pass2_prompt
    assert "Guide de choix par usage" in pass2_prompt
    assert "business_profile" in result["sources_used"]
    assert result["business_profile_context"]["hash"]
    assert (
        result["products"][0]["business_profile_context_hash"]
        == result["business_profile_context"]["hash"]
    )
    assert result["products"][0]["business_profile_context_status"] == "current"


def test_over_budget_skips_pass2_keeps_keywords():
    fake = _FakeDataForSEO()
    fake.available = False
    router = _router(_PASS1_JSON)  # only pass 1 should run
    result = _run(router, dataforseo=fake, over_budget=True)

    assert router.complete.call_count == 1
    assert "budget_skipped_pass2" in result["sources_used"]
    product = result["products"][0]
    assert product["seo_keywords"]  # targeting survived
    # Content pack falls back to current meta title, no generated description.
    assert product["content_test_pack"]["proposed_product_description"] == ""


def test_keyword_idea_is_serp_checked_when_it_becomes_primary_target():
    provider = _FakeDataForSEOWithWinningIdea()
    # The high-volume idea now enters the candidate pool; the LLM selects it from
    # the real pool and labels it the best fit, so it becomes the primary target.
    pass1 = json.dumps(
        {
            "product_summary": "Fontaine à eau pour chat.",
            "target_customer": "Propriétaires de chats.",
            "buying_intents": ["hydratation"],
            "seo_keywords": [
                {
                    "query": "fontaine chat silencieuse",
                    "intent_type": "commercial",
                    "product_fit_score": 95,
                    "reason": "demande réelle élevée",
                }
            ],
            "geo_questions": [],
        }
    )
    router = _router(pass1, _PASS2_JSON)

    result = _run(router, dataforseo=provider)

    product = result["products"][0]
    primary = product["seo_keywords"][0]
    assert primary["query"] == "fontaine chat silencieuse"
    assert primary["target_rank"] == 1
    assert primary["target_role"] == "primary"
    assert primary["data_source"] == "dataforseo"  # grounded in the real pool
    assert primary["serp_evidence"] is True
    assert provider.requested_serp_keywords[0] == "fontaine chat silencieuse"

    pass2_prompt = router.complete.call_args_list[1].args[0]
    assert '"fontaine chat silencieuse" [primary]' in pass2_prompt
    assert "SERP/PAA vérifié" in pass2_prompt


def test_content_quality_is_publish_ready_when_targets_and_evidence_are_covered():
    description = (
        "Cette fontaine chat fournit une eau filtrée chat grâce à son réservoir documenté. "
        "Son format permet de placer le point d'eau dans la maison et de suivre facilement "
        "le remplissage. La fiche produit confirme la filtration et la capacité indiquée, "
        "afin de décrire clairement son utilisation quotidienne sans ajouter de promesse. "
        "Le réservoir rassemble l'eau dans un point dédié ; cette présentation décrit son "
        "placement, son remplissage et le rôle indiqué de filtration sans allégation supplémentaire."
    )
    pack = {
        "seo_keywords": [
            {
                "query": "fontaine chat",
                "target_role": "primary",
                "paa_questions": ["Comment nettoyer une fontaine chat ?"],
            },
            {"query": "eau filtrée chat", "target_role": "secondary", "paa_questions": []},
        ],
        "proposed_meta_title": "Fontaine chat avec eau filtrée au quotidien",
        "proposed_meta_description": "Fontaine chat pour une eau filtrée au quotidien, conçue pour accompagner votre animal.",
        "proposed_product_description": description,
        "proposed_faq": [
            {"q": "Comment nettoyer une fontaine chat ?", "a": "Rincez chaque élément amovible."},
        ],
        "proposed_geo_answer_block": "Une fontaine chat diffuse une eau filtrée lorsque ce fait est confirmé.",
        "proposed_blog_title": "",
        "proposed_blog_intro": "",
        "proposed_blog_outline": [],
        "facts_used": ["description: fontaine chat, eau filtrée chat"],
        "claims_used": [{"claim": "Eau filtrée", "fact_keys": ["description"]}],
        "confidence": "high",
    }

    quality = engine._build_content_quality(
        pack,
        confirmed_facts=[
            {
                "key": "description",
                "value": description,
                "source": "shopify_snapshot",
                "confidence": "confirmed",
            }
        ],
        source_product_text=description,
        surface_plan={
            "metadata": {"generate": True},
            "product_description": {"generate": True},
            "faq": {"generate": True},
            "geo_answer": {"generate": True},
            "blog": {"generate": False},
        },
    )

    assert quality["publish_ready"] is True
    assert quality["issues"] == []
    assert len(quality["evidence_ledger"]) == 1


def test_content_quality_is_blocked_when_primary_target_is_missing_from_meta_title():
    pack = {
        "seo_keywords": [{"query": "fontaine chat", "target_role": "primary", "paa_questions": []}],
        "proposed_meta_title": "Eau fraîche au quotidien",
        "proposed_meta_description": "Découvrez notre fontaine chat pour garder de l'eau fraîche au quotidien.",
        "proposed_product_description": "Cette fontaine chat accompagne le quotidien de votre animal.",
        "proposed_faq": [],
        "proposed_geo_answer_block": "La fontaine chat répond au besoin d'hydratation décrit.",
        "facts_used": ["meta_description: fontaine chat"],
        "claims_used": [{"claim": "Produit pour chat", "fact_keys": ["description"]}],
        "confidence": "high",
    }

    quality = engine._build_content_quality(
        pack,
        confirmed_facts=[
            {
                "key": "description",
                "value": "Produit pour chat.",
                "source": "shopify_snapshot",
                "confidence": "confirmed",
            }
        ],
        surface_plan={
            "metadata": {"generate": True},
            "product_description": {"generate": True},
            "faq": {"generate": False},
            "geo_answer": {"generate": True},
            "blog": {"generate": False},
        },
    )

    assert quality["publish_ready"] is False
    assert "meta_title_missing_primary_target" in quality["issues"]


def test_content_quality_blocks_unverified_product_claim() -> None:
    pack = {
        "seo_keywords": [{"query": "fontaine chat", "target_role": "primary", "paa_questions": []}],
        "proposed_meta_title": "Fontaine chat pour le quotidien",
        "proposed_meta_description": "Fontaine chat pratique pour aménager un point d'eau à la maison.",
        "proposed_product_description": (
            "Cette fontaine chat ultra-silencieuse accompagne votre animal au quotidien avec un "
            "format adapté à son espace. Sa conception facilite le positionnement du point d'eau "
            "et son utilisation dans la maison, tout en décrivant clairement le produit présenté."
        ),
        "proposed_faq": [],
        "proposed_geo_answer_block": "Cette fontaine chat est proposée comme point d'eau pour la maison.",
        "proposed_blog_title": "",
        "proposed_blog_intro": "",
        "proposed_blog_outline": [],
        "claims_used": [{"claim": "Produit pour chat", "fact_keys": ["description"]}],
        "confidence": "high",
    }

    quality = engine._build_content_quality(
        pack,
        confirmed_facts=[
            {
                "key": "description",
                "value": "Fontaine pour chat.",
                "source": "shopify_snapshot",
                "confidence": "confirmed",
            }
        ],
        source_product_text="Fontaine pour chat.",
        surface_plan={
            "metadata": {"generate": True},
            "product_description": {"generate": True},
            "faq": {"generate": False},
            "geo_answer": {"generate": True},
            "blog": {"generate": False},
        },
    )

    assert quality["publish_ready"] is False
    assert quality["auto_apply_allowed"] is False
    assert quality["final_status"] == "blocked"
    assert "unsupported_product_claims" in quality["issues"]
    assert quality["unsupported_claims"]
    assert "performance" in quality["unsupported_claim_categories"]


def test_content_quality_blocks_faq_when_surface_plan_disables_it() -> None:
    pack = {
        "seo_keywords": [
            {
                "query": "fontaine chat",
                "target_role": "primary",
                "paa_questions": ["Comment nettoyer une fontaine chat ?"],
            }
        ],
        "proposed_meta_title": "Fontaine chat pour le quotidien",
        "proposed_meta_description": "Fontaine chat pratique pour aménager un point d'eau à la maison.",
        "proposed_product_description": "",
        "proposed_faq": [
            {"q": "Comment nettoyer une fontaine chat ?", "a": "Rincez chaque élément."}
        ],
        "proposed_geo_answer_block": "",
        "proposed_blog_title": "",
        "proposed_blog_intro": "",
        "proposed_blog_outline": [],
        "claims_used": [{"claim": "Produit pour chat", "fact_keys": ["description"]}],
        "confidence": "high",
    }
    surface_plan = {
        "metadata": {"generate": True},
        "product_description": {"generate": False},
        "faq": {"generate": False, "reason": "insufficient_question_or_fact_evidence"},
        "geo_answer": {"generate": False},
        "blog": {"generate": False},
    }

    quality = engine._build_content_quality(
        pack,
        confirmed_facts=[
            {
                "key": "description",
                "value": "Fontaine pour chat.",
                "source": "shopify_snapshot",
                "confidence": "confirmed",
            }
        ],
        surface_plan=surface_plan,
    )
    pack["content_quality"] = quality
    pack["surface_plan"] = surface_plan
    result = engine._build_product_result(_product(), {"opportunity_score": 10}, pack, _SHOP)

    assert quality["publish_ready"] is False
    assert quality["auto_apply_allowed"] is False
    assert quality["final_status"] == "blocked"
    assert "faq_blocked_missing_evidence" in quality["issues"]
    assert all("faq" not in item["fields"] for item in quality["keyword_coverage"])
    assert result["content_test_pack"]["proposed_faq"] == []
    assert result["surface_statuses"]["faq"]["status"] == "blocked"


def test_product_consistency_below_threshold_blocks_reflection_status() -> None:
    pack = {
        "seo_keywords": [{"query": "fontaine chat", "target_role": "primary"}],
        "proposed_meta_title": "Fontaine chat pour le quotidien",
        "proposed_meta_description": "Fontaine chat pratique pour la maison.",
        "proposed_product_description": "Fontaine chat pour le quotidien.",
        "claims_used": [{"claim": "Produit pour chat", "fact_keys": ["description"]}],
        "content_quality": {
            "publish_ready": True,
            "issues": [],
            "covered_target_count": 1,
            "target_count": 1,
            "product_consistency_score": 65,
            "seo_geo_score": 90,
            "publish_status": "publish_ready",
            "publish_blockers": [],
        },
    }

    attempt = engine._build_content_reflection_attempt(
        pack,
        fields={
            "confirmed_facts": [
                {
                    "key": "description",
                    "value": "Fontaine pour chat.",
                    "source": "shopify_snapshot",
                    "confidence": "confirmed",
                }
            ],
            "source_product_text": "Fontaine chat pour le quotidien.",
            "product_title": "Fontaine à chat",
            "merchant_label": "",
            "handle": "fontaine-chat",
        },
        business_context="Fontaine chat premium pour chats urbains.",
        business_profile={},
        niche_summary="Accessoires chat premium",
    )

    assert attempt["status"] == "blocked"
    assert attempt["product_consistency_score"] < 70


def test_keyword_guardrail_blocks_content_quality_before_content_generation() -> None:
    pack = {
        "seo_keywords": [
            {"query": "léonie delacroix avis", "target_role": "primary", "paa_questions": []},
            {"query": "modèle tricot pull chien gratuit", "target_role": "secondary"},
        ],
        "proposed_meta_title": "",
        "proposed_meta_description": "",
        "proposed_product_description": "",
        "proposed_faq": [],
        "proposed_geo_answer_block": "",
        "proposed_blog_title": "",
        "proposed_blog_intro": "",
        "proposed_blog_outline": [],
        "claims_used": [],
        "confidence": "low",
        "keyword_guardrail": {
            "status": "blocked",
            "issues": [
                "keyword_customer_need_alignment_low",
                "insufficient_product_page_keyword_targets",
            ],
        },
    }

    quality = engine._build_content_quality(
        pack,
        confirmed_facts=[],
        surface_plan={
            "metadata": {"generate": True},
            "product_description": {"generate": False},
            "faq": {"generate": False},
            "geo_answer": {"generate": False},
            "blog": {"generate": False},
        },
    )

    assert quality["publish_ready"] is False
    assert quality["auto_apply_allowed"] is False
    assert quality["final_status"] == "blocked"
    assert "keyword_guardrail_blocked" in quality["issues"]
    assert "keyword_customer_need_alignment_low" in quality["publish_blockers"]
    assert "Bloqué : mots-clés non alignés avec le besoin client" in quality["blocking_reasons"]


def test_content_quality_blocks_when_top_secondary_keywords_are_not_used() -> None:
    description = (
        "Cette fontaine chat est décrite comme une fontaine pour le point d'eau du foyer. "
        "La fiche produit confirme son usage comme accessoire d'eau pour chat et permet "
        "de présenter la page sans ajouter de promesse non vérifiée. Le texte explique "
        "simplement le rôle du produit, son contexte d'utilisation et la façon dont le "
        "marchand peut le présenter sur une page produit."
    )
    pack = {
        "seo_keywords": [
            {"query": "fontaine chat", "target_role": "primary", "keyword_surface": "product_page"},
            {
                "query": "fontaine chat inox",
                "target_role": "secondary",
                "keyword_surface": "product_page",
            },
            {
                "query": "fontaine chat sans fil",
                "target_role": "secondary",
                "keyword_surface": "product_page",
            },
            {
                "query": "fontaine chat design",
                "target_role": "secondary",
                "keyword_surface": "product_page",
            },
        ],
        "proposed_meta_title": "Fontaine chat pour le point d'eau du foyer",
        "proposed_meta_description": "Fontaine chat pour présenter un point d'eau dédié dans la maison.",
        "proposed_product_description": description,
        "proposed_faq": [
            {"q": "Comment utiliser une fontaine chat ?", "a": "Suivez la fiche produit."}
        ],
        "proposed_geo_answer_block": "Une fontaine chat est un point d'eau décrit dans la fiche produit.",
        "proposed_blog_title": "",
        "proposed_blog_intro": "",
        "proposed_blog_outline": [],
        "claims_used": [{"claim": "Produit pour chat", "fact_keys": ["description"]}],
        "confidence": "high",
    }

    quality = engine._build_content_quality(
        pack,
        confirmed_facts=[
            {
                "key": "description",
                "value": description,
                "source": "shopify_snapshot",
                "confidence": "confirmed",
            }
        ],
        source_product_text=description,
        surface_plan={
            "metadata": {"generate": True},
            "product_description": {"generate": True},
            "faq": {"generate": True},
            "geo_answer": {"generate": True},
            "blog": {"generate": False},
        },
    )

    assert quality["publish_ready"] is False
    assert quality["keyword_content_guardrail"]["status"] == "blocked"
    assert "secondary_keyword_coverage_low" in quality["issues"]
    assert "important_keyword_coverage_low" in quality["publish_blockers"]
    assert quality["keyword_content_guardrail"]["uncovered_important_keywords"] == [
        "fontaine chat inox",
        "fontaine chat sans fil",
        "fontaine chat design",
    ]


def test_commercial_modifier_keyword_is_covered_without_forcing_exact_buy_word() -> None:
    description = (
        "Ce pull en cachemire pour chien est présenté dans la fiche produit comme un "
        "vêtement en cachemire pour chien. La page décrit le produit, sa matière et son "
        "usage comme vêtement pour chien, sans ajouter de promesse non vérifiée. Cette "
        "présentation permet de couvrir l'intention d'achat avec une formulation naturelle "
        "de page produit."
    )
    pack = {
        "seo_keywords": [
            {"query": "pull chien", "target_role": "primary", "keyword_surface": "product_page"},
            {
                "query": "pull chien acheter",
                "target_role": "secondary",
                "keyword_surface": "product_page",
            },
        ],
        "proposed_meta_title": "Pull chien en cachemire pour page produit",
        "proposed_meta_description": "Pull en cachemire pour chien présenté clairement dans la fiche produit.",
        "proposed_product_description": description,
        "proposed_faq": [
            {"q": "Comment présenter un pull chien ?", "a": "Avec les faits confirmés."}
        ],
        "proposed_geo_answer_block": "Un pull chien est un vêtement décrit par la fiche produit.",
        "proposed_blog_title": "",
        "proposed_blog_intro": "",
        "proposed_blog_outline": [],
        "claims_used": [{"claim": "Pull en cachemire pour chien", "fact_keys": ["description"]}],
        "confidence": "high",
    }

    quality = engine._build_content_quality(
        pack,
        confirmed_facts=[
            {
                "key": "description",
                "value": description,
                "source": "shopify_snapshot",
                "confidence": "confirmed",
            }
        ],
        source_product_text=description,
        surface_plan={
            "metadata": {"generate": True},
            "product_description": {"generate": True},
            "faq": {"generate": True},
            "geo_answer": {"generate": True},
            "blog": {"generate": False},
        },
    )

    coverage = {item["query"]: item for item in quality["keyword_coverage"]}
    assert coverage["pull chien acheter"]["coverage_query"] == "pull chien"
    assert coverage["pull chien acheter"]["coverage_mode"] == "commercial_intent_normalized"
    assert coverage["pull chien acheter"]["adapted_fields_covered"]
    assert quality["keyword_content_guardrail"]["status"] == "pass"
    assert "secondary_keyword_coverage_low" not in quality["issues"]


def test_generated_pack_adds_faq_blog_ideas_and_geo_pack_to_description() -> None:
    pack = {
        "seo_keywords": [
            {
                "query": "pull cachemire chien",
                "target_role": "primary",
                "keyword_surface": "product_page",
            },
            {
                "query": "pull pour chien",
                "target_role": "secondary",
                "keyword_surface": "product_page",
            },
            {
                "query": "chien qui a froid",
                "target_role": "secondary",
                "keyword_surface": "blog",
            },
            {
                "query": "comment choisir pull chien",
                "target_role": "secondary",
                "keyword_surface": "blog",
            },
            {
                "query": "pull chien hiver",
                "target_role": "secondary",
                "keyword_surface": "blog",
            },
        ],
        "geo_questions": [
            {
                "question": "Comment choisir un pull pour chien ?",
                "answer_angle": "Critères de choix à confirmer",
                "content_block_type": "faq",
                "confidence": "high",
            }
        ],
        "proposed_product_description": "Le pull cachemire chien est présenté avec les faits confirmés.",
        "proposed_faq": [],
        "proposed_geo_answer_block": "Le pull cachemire chien est un vêtement décrit par la fiche produit.",
        "proposed_geo_definition_block": "Le pull cachemire chien est un vêtement pour chien.",
        "proposed_geo_quick_facts": ["Matière indiquée dans la fiche produit"],
        "proposed_geo_comparison_table": [{"critère": "Matière", "valeur": "Cachemire"}],
        "proposed_blog_title": "",
        "proposed_blog_intro": "",
        "proposed_blog_outline": [],
        "proposed_blog_ideas": [],
    }

    normalized = engine._normalize_generated_content_pack(
        pack,
        confirmed_facts=[
            {
                "key": "description",
                "value": "Pull en cachemire pour chien confirmé dans la fiche produit.",
                "source": "shopify_snapshot",
                "confidence": "confirmed",
            }
        ],
    )

    assert len(normalized["proposed_faq"]) >= 5
    assert normalized["proposed_faq"][0]["q"] == "Comment choisir un pull pour chien ?"
    assert len(normalized["proposed_blog_ideas"]) == 5
    assert all(idea["target_keyword"] for idea in normalized["proposed_blog_ideas"])
    assert "Réponse courte" in normalized["proposed_product_description"]
    assert (
        "Le pull cachemire chien est un vêtement pour chien."
        in normalized["proposed_product_description"]
    )
    assert "Définition GEO/IA" not in normalized["proposed_product_description"]


def test_generated_pack_builds_five_blog_ideas_from_one_keyword_when_needed() -> None:
    pack = {
        "seo_keywords": [
            {
                "query": "pull pour chien",
                "target_role": "primary",
                "keyword_surface": "product_page",
            }
        ],
        "geo_questions": [],
        "proposed_product_description": "",
        "proposed_faq": [],
        "proposed_blog_title": "",
        "proposed_blog_intro": "",
        "proposed_blog_outline": [],
        "proposed_blog_ideas": [],
    }

    normalized = engine._normalize_generated_content_pack(
        pack,
        confirmed_facts=[],
    )

    assert len(normalized["proposed_blog_ideas"]) == 5
    assert all(
        "pull pour chien" in idea["target_keyword"] for idea in normalized["proposed_blog_ideas"]
    )
    assert all(idea["outline"] for idea in normalized["proposed_blog_ideas"])


def test_content_quality_requires_important_keywords_in_metadata() -> None:
    description = (
        "Cette fontaine chat inox est décrite dans la fiche produit. La description "
        "couvre aussi fontaine chat sans fil avec les faits confirmés, mais les métadonnées "
        "ne couvrent pas tous les mots-clés secondaires sélectionnés."
    )
    pack = {
        "seo_keywords": [
            {
                "query": "fontaine chat inox",
                "target_role": "primary",
                "keyword_surface": "product_page",
            },
            {
                "query": "fontaine chat sans fil",
                "target_role": "secondary",
                "keyword_surface": "product_page",
            },
        ],
        "proposed_meta_title": "Fontaine chat inox pour la maison",
        "proposed_meta_description": "Fontaine chat inox décrite avec les faits de la fiche produit.",
        "proposed_product_description": description,
        "proposed_faq": [
            {"q": "Comment utiliser une fontaine chat inox ?", "a": "Avec les faits confirmés."}
        ],
        "proposed_geo_answer_block": "La fontaine chat inox est décrite par la fiche produit.",
        "proposed_blog_title": "",
        "proposed_blog_intro": "",
        "proposed_blog_outline": [],
        "claims_used": [{"claim": "Fontaine chat inox", "fact_keys": ["description"]}],
        "confidence": "high",
    }

    quality = engine._build_content_quality(
        pack,
        confirmed_facts=[
            {
                "key": "description",
                "value": description,
                "source": "shopify_snapshot",
                "confidence": "confirmed",
            }
        ],
        source_product_text=description,
        surface_plan={
            "metadata": {"generate": True},
            "product_description": {"generate": True},
            "faq": {"generate": True},
            "geo_answer": {"generate": True},
            "blog": {"generate": False},
        },
    )

    assert quality["keyword_content_guardrail"]["status"] == "blocked"
    assert "important_keyword_missing_from_metadata" in quality["publish_blockers"]
    assert quality["keyword_content_guardrail"]["metadata_uncovered_keywords"] == [
        "fontaine chat sans fil"
    ]


def test_keyword_assignment_keeps_diy_free_queries_out_of_product_primary() -> None:
    keywords = [
        {
            "query": "modèle tricot pull chien gratuit",
            "intent_type": "informational",
            "demand_score": 95,
            "competition_score": 20,
            "product_fit_score": 90,
            "data_source": "dataforseo",
            "difficulty_source": "dataforseo",
        },
        {
            "query": "pull en cachemire pour chien",
            "intent_type": "commercial",
            "demand_score": 55,
            "competition_score": 35,
            "product_fit_score": 95,
            "data_source": "dataforseo",
            "difficulty_source": "dataforseo",
        },
    ]

    ranked = engine._assign_keyword_targets(keywords, frozenset({"pull", "chien", "cachemire"}))
    primary = next(keyword for keyword in ranked if keyword.get("target_role") == "primary")
    mapping = engine._build_keyword_surface_mapping(ranked)

    assert primary["query"] == "pull en cachemire pour chien"
    assert ranked[1]["query"] == "modèle tricot pull chien gratuit"
    assert ranked[1]["target_role"] != "primary"
    assert mapping[1]["surface"] == "blog"
    assert mapping[1]["product_primary_allowed"] is False


def test_best_fountain_query_is_blog_not_product_primary() -> None:
    keywords = [
        {
            "query": "meilleure fontaine à eau chat",
            "intent_type": "commercial",
            "demand_score": 95,
            "competition_score": 30,
            "product_fit_score": 95,
            "data_source": "dataforseo",
            "difficulty_source": "dataforseo",
        },
        {
            "query": "fontaine eau chat sans fil",
            "intent_type": "commercial",
            "demand_score": 70,
            "competition_score": 40,
            "product_fit_score": 92,
            "data_source": "dataforseo",
            "difficulty_source": "dataforseo",
        },
    ]

    ranked = engine._assign_keyword_targets(keywords, frozenset({"fontaine", "eau", "chat"}))
    primary = next(keyword for keyword in ranked if keyword.get("target_role") == "primary")
    mapping = {item["query"]: item for item in engine._build_keyword_surface_mapping(ranked)}

    assert primary["query"] == "fontaine eau chat sans fil"
    assert mapping["meilleure fontaine à eau chat"]["surface"] == "blog"
    assert mapping["meilleure fontaine à eau chat"]["product_primary_allowed"] is False


def test_surface_plan_keeps_mandatory_faq_but_blocks_fact_surfaces_without_verified_value() -> None:
    # No confirmed facts → product_description/geo blocked.
    # PAA present → FAQ/blog can be drafted, then content quality decides publishability.
    keywords = [
        {
            "query": "bol chat",
            "target_role": "primary",
            "intent_type": "commercial",
            "paa_questions": ["Quel bol choisir pour un chat ?"],
        }
    ]

    plan = engine._build_surface_plan(keywords, [])

    assert plan["metadata"]["generate"] is True
    assert plan["product_description"]["generate"] is False
    assert plan["faq"]["generate"] is True
    assert plan["faq"]["reason"] == "paa_questions_available_pending_fact_validation"
    assert plan["geo_answer"]["generate"] is False
    assert plan["blog"]["generate"] is True


def test_surface_plan_does_not_treat_thin_description_as_evidence_for_fact_surfaces() -> None:
    # Thin description (< 12 words, no NER facts) → product_description/geo blocked.
    # Informational intent + PAA → FAQ/blog still drafted before publish validation.
    keywords = [
        {
            "query": "fontaine chat",
            "target_role": "primary",
            "intent_type": "informational",
            "paa_questions": ["Comment choisir une fontaine chat ?"],
        }
    ]
    facts = [
        {
            "key": "description",
            "value": "Fontaine 2L.",
            "source": "shopify_snapshot",
            "confidence": "confirmed",
        }
    ]

    plan = engine._build_surface_plan(keywords, facts)

    assert plan["metadata"]["generate"] is True
    assert plan["product_description"]["generate"] is False
    assert plan["faq"]["generate"] is True
    assert plan["faq"]["reason"] == "paa_questions_available_pending_fact_validation"
    assert plan["geo_answer"]["generate"] is False
    assert plan["blog"]["generate"] is True


def test_enrichment_questions_reuse_primary_keyword_for_missing_warranty_and_article() -> None:
    keywords = [
        {
            "query": "fontaine chat silencieuse",
            "target_role": "primary",
            "intent_type": "commercial",
            "paa_questions": [],
        }
    ]
    plan = engine._build_surface_plan(keywords, [])

    questions = engine._build_enrichment_questions(
        keywords,
        [{"key": "warranty", "label": "Warranty"}],
        plan,
    )

    assert questions[0]["key"] == "warranty"
    assert "fontaine chat silencieuse" in questions[0]["question"]
    assert any(question["key"] == "selection_criteria" for question in questions)
    assert all(question["target_keyword"] == "fontaine chat silencieuse" for question in questions)


def test_build_enrichment_questions_surfaces_all_missing_facts() -> None:
    keywords = [
        {
            "query": "harnais chien",
            "target_role": "primary",
            "intent_type": "commercial",
            "paa_questions": [],
        }
    ]
    plan = engine._build_surface_plan(keywords, [])
    missing = [
        {"key": "origins", "label": "Manufacturing origin"},
        {"key": "care", "label": "Care instructions"},
        {"key": "dimensions", "label": "Dimensions"},
        {"key": "size_recommendation", "label": "Size recommendation"},
    ]

    questions = engine._build_enrichment_questions(keywords, missing, plan)
    keys = {q["key"] for q in questions}

    # Every missing fact gets its own question (no 2-question cap), plus the two
    # editorial questions.
    assert {"origins", "care", "dimensions", "size_recommendation"} <= keys
    assert {"use_cases", "selection_criteria"} <= keys


def test_merchant_answers_unlock_keyword_grounded_optional_content() -> None:
    keywords = [
        {
            "query": "fontaine chat",
            "target_role": "primary",
            "intent_type": "commercial",
            "paa_questions": [],
        }
    ]
    facts = engine._merge_merchant_confirmed_facts(
        [],
        {
            "warranty": "Garantie de 2 ans.",
            "use_cases": "Pour maintenir un point d'eau disponible au quotidien.",
        },
    )

    plan = engine._build_surface_plan(keywords, facts)

    assert {fact["source"] for fact in facts} == {"merchant_confirmation"}
    assert plan["faq"]["generate"] is True
    assert plan["geo_answer"]["generate"] is True
    assert plan["blog"]["generate"] is True


def test_catalog_conflict_blocks_lower_priority_duplicate_target() -> None:
    first_quality = {"publish_ready": True, "issues": []}
    second_quality = {"publish_ready": True, "issues": []}
    results = [
        {
            "product_id": "gid://shopify/Product/1",
            "opportunity_score": 80,
            "seo_keywords": [{"query": "fontaine chat", "target_role": "primary"}],
            "content_test_pack": {
                "proposed_meta_title": "Fontaine chat premium",
                "proposed_meta_description": "Premier contenu original.",
                "proposed_product_description": "",
                "content_quality": first_quality,
            },
        },
        {
            "product_id": "gid://shopify/Product/2",
            "opportunity_score": 50,
            "seo_keywords": [{"query": "fontaine chat", "target_role": "primary"}],
            "content_test_pack": {
                "proposed_meta_title": "Fontaine chat standard",
                "proposed_meta_description": "Second contenu original.",
                "proposed_product_description": "",
                "content_quality": second_quality,
            },
        },
    ]

    engine._apply_catalog_content_conflicts(results, [])

    assert first_quality["publish_ready"] is True
    assert second_quality["publish_ready"] is False
    assert "primary_target_cannibalization_risk" in second_quality["issues"]


# ── Real-time grounding injection (fetch_realtime) ─────────────────────────


def _product2():
    return {
        "id": "gid://shopify/Product/2",
        "title": "Griffoir pour chat",
        "handle": "griffoir-chat",
        "status": "ACTIVE",
        "body_html": "<p>Griffoir en sisal</p>",
        "seo": {"title": "Griffoir chat", "description": ""},
        "variants": [{"price": "19.90", "inventory_quantity": 8}],
    }


def _default_budget(*, over_budget=False):
    return {
        "over_budget": over_budget,
        "budget_usd": 20.0,
        "spent_usd": 0.0,
        "remaining_usd": 20.0,
        "usage_pct": 0.0,
        "alert": None,
    }


def _run_with_realtime(
    router,
    *,
    fetch_realtime,
    realtime_signals,
    verifications=None,
    products=None,
    over_budget=False,
):
    with (
        patch.object(engine, "get_router", return_value=router),
        patch.object(engine, "check_budget", return_value=_default_budget(over_budget=over_budget)),
        patch.object(engine, "_fetch_trends_once", return_value=[]),
        patch.object(engine, "_fetch_realtime_signals_once", return_value=realtime_signals) as mock_fetch,
        # Never let a real GEMINI_API_KEY in the test environment trigger a live
        # HTTP call from this unrelated engine-level test — always mocked here.
        patch.object(engine, "_verify_keywords_once", return_value=verifications) as mock_verify,
        patch.object(engine, "fetch_suggestions_bulk", return_value=[]),
        patch.object(engine, "DataForSEOProvider", return_value=_FakeDataForSEO()),
    ):
        result = engine.run_market_analysis(
            products if products is not None else [_product()],
            _SHOP,
            {},
            [],
            fetch_realtime=fetch_realtime,
        )
    return result, mock_fetch, mock_verify


def test_fetch_realtime_false_never_calls_realtime_fetcher():
    router = _router(_PASS1_JSON, _PASS2_JSON)
    result, mock_fetch, _mock_verify = _run_with_realtime(router, fetch_realtime=False, realtime_signals=None)
    mock_fetch.assert_not_called()
    assert "realtime_grounding" not in result["sources_used"]
    pass1_prompt = router.complete.call_args_list[0].args[0]
    assert "DONNÉES TEMPS RÉEL" not in pass1_prompt


def test_fetch_realtime_true_with_signal_injects_prompt_and_source():
    router = _router(_PASS1_JSON, _PASS2_JSON)
    signals = {
        "events": [{"title": "Canicule en France cette semaine"}],
        "rising_queries": [{"query": "fontaine à eau chat canicule"}],
        "competitor_moves": [],
        "citations": [{"url": "https://meteo-france.fr/canicule", "title": "Météo France"}],
        "fetched_at": "2026-07-15T00:00:00+00:00",
    }
    result, mock_fetch, _mock_verify = _run_with_realtime(router, fetch_realtime=True, realtime_signals=signals)
    mock_fetch.assert_called_once()
    assert "realtime_grounding" in result["sources_used"]
    pass1_prompt = router.complete.call_args_list[0].args[0]
    assert "DONNÉES TEMPS RÉEL" in pass1_prompt
    assert "Canicule en France cette semaine" in pass1_prompt
    assert "fontaine à eau chat canicule" in pass1_prompt


def test_fetch_realtime_true_without_signal_is_a_safe_no_op():
    """Free/pro shop (or Gemini unavailable): fetcher returns None — the
    analysis must proceed exactly as if fetch_realtime had been False."""
    router = _router(_PASS1_JSON, _PASS2_JSON)
    result, mock_fetch, _mock_verify = _run_with_realtime(router, fetch_realtime=True, realtime_signals=None)
    mock_fetch.assert_called_once()
    assert "realtime_grounding" not in result["sources_used"]
    pass1_prompt = router.complete.call_args_list[0].args[0]
    assert "DONNÉES TEMPS RÉEL" not in pass1_prompt


def test_fetch_realtime_false_result_carries_not_attempted_status():
    """The new diagnostic fields must always be present, even when grounding
    was never attempted, so a caller never needs to guess why."""
    router = _router(_PASS1_JSON, _PASS2_JSON)
    result, _mock_fetch, _mock_verify = _run_with_realtime(
        router, fetch_realtime=False, realtime_signals=None
    )
    assert result["realtime_signals"] is None
    assert result["realtime_status"]["status"] == "not_attempted"
    assert result["market_verification_status"]["status"] == "not_attempted"
    assert result["keywords_with_market_verification"] == 0


def test_fetch_realtime_true_includes_realtime_signals_in_result():
    """realtime_signals must be fully surfaced in the result, not just left
    persisted to disk (previously invisible in exports)."""
    router = _router(_PASS1_JSON, _PASS2_JSON)
    signals = {
        "events": [{"title": "Canicule en France cette semaine"}],
        "rising_queries": [],
        "competitor_moves": [],
        "citations": [{"url": "https://meteo-france.fr/canicule", "title": "Météo France"}],
        "fetched_at": "2026-07-15T00:00:00+00:00",
    }
    result, _mock_fetch, _mock_verify = _run_with_realtime(
        router, fetch_realtime=True, realtime_signals=signals
    )
    assert result["realtime_signals"] == signals


def test_market_verification_annotates_matching_keyword_and_bumps_demand_score():
    router = _router(_PASS1_JSON, _PASS2_JSON)
    verifications = {
        "fontaine à chat": {
            "evidence": "rising",
            "note": "Recherches en hausse pendant la canicule",
            "source_url": "https://example.com/trend",
        }
    }
    result, _mock_fetch, mock_verify = _run_with_realtime(
        router, fetch_realtime=True, realtime_signals=None, verifications=verifications
    )
    mock_verify.assert_called_once()
    assert "realtime_market_verification" in result["sources_used"]
    assert result["keywords_with_market_verification"] == 1
    kw = result["products"][0]["seo_keywords"][0]
    assert kw["market_verification"]["evidence"] == "rising"
    base_demand_score = 75.0  # post-enrichment baseline (not the raw pass-1 fixture value)
    assert kw["demand_score"] == base_demand_score + 10
    assert "verified_by_market" in kw["notes"]


def test_market_verification_declining_bumps_demand_score_down():
    router = _router(_PASS1_JSON, _PASS2_JSON)
    verifications = {
        "fontaine à chat": {"evidence": "declining", "note": "", "source_url": ""}
    }
    result, _mock_fetch, _mock_verify = _run_with_realtime(
        router, fetch_realtime=True, realtime_signals=None, verifications=verifications
    )
    kw = result["products"][0]["seo_keywords"][0]
    base_demand_score = 75.0  # post-enrichment baseline (not the raw pass-1 fixture value)
    assert kw["demand_score"] == base_demand_score - 10


def test_market_verification_no_verifications_leaves_keywords_untouched():
    router = _router(_PASS1_JSON, _PASS2_JSON)
    result, _mock_fetch, mock_verify = _run_with_realtime(
        router, fetch_realtime=True, realtime_signals=None, verifications=None
    )
    mock_verify.assert_called_once()
    assert "realtime_market_verification" not in result["sources_used"]
    assert result["keywords_with_market_verification"] == 0
    kw = result["products"][0]["seo_keywords"][0]
    assert "market_verification" not in kw


def test_fetch_realtime_force_defaults_to_false_and_is_threaded_through():
    """fetch_realtime_force must reach _fetch_realtime_signals_once's `force`
    kwarg unchanged — used only by the Pro/Grande boutique comparison tool to
    exercise the agency branch without touching the shop's real plan."""
    router = _router(_PASS1_JSON, _PASS2_JSON)
    budget = {
        "over_budget": False, "budget_usd": 20.0, "spent_usd": 0.0,
        "remaining_usd": 20.0, "usage_pct": 0.0, "alert": None,
    }
    with (
        patch.object(engine, "get_router", return_value=router),
        patch.object(engine, "check_budget", return_value=budget),
        patch.object(engine, "_fetch_trends_once", return_value=[]),
        patch.object(engine, "_fetch_realtime_signals_once", return_value=None) as mock_fetch,
        patch.object(engine, "fetch_suggestions_bulk", return_value=[]),
        patch.object(engine, "DataForSEOProvider", return_value=_FakeDataForSEO()),
    ):
        engine.run_market_analysis(
            [_product()], _SHOP, {}, [], fetch_realtime=True, fetch_realtime_force=True,
        )
    assert mock_fetch.call_args.kwargs["force"] is True


def test_fetch_realtime_multiple_products_each_get_own_grounded_call():
    """Core behavior change: 2 products must trigger 2 independent realtime
    calls and 2 independent verification calls (one pair per product), not one
    shared catalog-wide pair."""
    router = _router(_PASS1_JSON, _PASS1_JSON, _PASS2_JSON, _PASS2_JSON)
    result, mock_fetch, mock_verify = _run_with_realtime(
        router,
        fetch_realtime=True,
        realtime_signals=None,
        products=[_product(), _product2()],
    )
    assert mock_fetch.call_count == 2
    assert mock_verify.call_count == 2
    fetched_titles = {call.args[2][0] for call in mock_fetch.call_args_list}
    assert fetched_titles == {"Fontaine à chat", "Griffoir pour chat"}
    assert result["realtime_status"]["products_attempted"] == 2
    assert result["market_verification_status"]["products_attempted"] == 2


def test_realtime_status_is_partial_when_only_some_products_succeed():
    router = _router(_PASS1_JSON, _PASS1_JSON, _PASS2_JSON, _PASS2_JSON)
    signal = {
        "events": [],
        "rising_queries": [],
        "competitor_moves": [],
        "citations": [],
        "fetched_at": "2026-07-15T00:00:00+00:00",
    }
    with (
        patch.object(engine, "get_router", return_value=router),
        patch.object(engine, "check_budget", return_value=_default_budget()),
        patch.object(engine, "_fetch_trends_once", return_value=[]),
        patch.object(engine, "_fetch_realtime_signals_once", side_effect=[signal, None]) as mock_fetch,
        patch.object(engine, "_verify_keywords_once", return_value=None) as mock_verify,
        patch.object(engine, "fetch_suggestions_bulk", return_value=[]),
        patch.object(engine, "DataForSEOProvider", return_value=_FakeDataForSEO()),
    ):
        result = engine.run_market_analysis(
            [_product(), _product2()], _SHOP, {}, [], fetch_realtime=True,
        )
    assert mock_fetch.call_count == 2
    assert mock_verify.call_count == 2
    assert result["realtime_status"]["products_attempted"] == 2
    assert result["realtime_status"]["products_ok"] == 1
    assert result["realtime_status"]["status"] == "partial"


def test_realtime_signals_from_multiple_products_merge_and_dedupe():
    router = _router(_PASS1_JSON, _PASS1_JSON, _PASS2_JSON, _PASS2_JSON)
    signal_a = {
        "events": [{"title": "Canicule en France cette semaine"}],
        "rising_queries": [{"query": "fontaine à eau chat canicule"}],
        "competitor_moves": [],
        "citations": [{"url": "https://meteo-france.fr/canicule", "title": "Météo France"}],
        "fetched_at": "2026-07-15T00:00:00+00:00",
    }
    signal_b = {
        # Same event as product A (should be deduped), plus a new one of its own.
        "events": [
            {"title": "Canicule en France cette semaine"},
            {"title": "Rentrée des classes"},
        ],
        "rising_queries": [{"query": "griffoir chat sisal"}],
        "competitor_moves": [],
        "citations": [],
        "fetched_at": "2026-07-16T00:00:00+00:00",
    }
    with (
        patch.object(engine, "get_router", return_value=router),
        patch.object(engine, "check_budget", return_value=_default_budget()),
        patch.object(engine, "_fetch_trends_once", return_value=[]),
        patch.object(
            engine, "_fetch_realtime_signals_once", side_effect=[signal_a, signal_b]
        ),
        patch.object(engine, "_verify_keywords_once", return_value=None),
        patch.object(engine, "fetch_suggestions_bulk", return_value=[]),
        patch.object(engine, "DataForSEOProvider", return_value=_FakeDataForSEO()),
    ):
        result = engine.run_market_analysis(
            [_product(), _product2()], _SHOP, {}, [], fetch_realtime=True,
        )
    merged = result["realtime_signals"]
    assert len(merged["events"]) == 2
    assert {e["title"] for e in merged["events"]} == {
        "Canicule en France cette semaine",
        "Rentrée des classes",
    }
    assert {q["query"] for q in merged["rising_queries"]} == {
        "fontaine à eau chat canicule",
        "griffoir chat sisal",
    }
    # Latest fetched_at across all merged products.
    assert merged["fetched_at"] == "2026-07-16T00:00:00+00:00"


def test_grounding_budget_exhausted_skips_every_product():
    """A catalog large enough to already be over the monthly LLM budget must
    skip ALL per-product grounded calls, not partially drain the budget."""
    router = _router(_PASS1_JSON, _PASS1_JSON, _PASS2_JSON, _PASS2_JSON)
    result, mock_fetch, mock_verify = _run_with_realtime(
        router,
        fetch_realtime=True,
        realtime_signals=None,
        products=[_product(), _product2()],
        over_budget=True,
    )
    mock_fetch.assert_not_called()
    mock_verify.assert_not_called()
    assert result["realtime_status"]["status"] == "budget_skipped"
    assert result["market_verification_status"]["status"] == "budget_skipped"
