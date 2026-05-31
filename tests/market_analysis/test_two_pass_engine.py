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


def test_surface_plan_skips_facts_surfaces_without_verified_value_but_allows_blog_with_paa() -> (
    None
):
    # No confirmed facts → product_description/faq/geo blocked.
    # PAA present → blog allowed (blog does not require confirmed facts).
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
    assert plan["faq"]["generate"] is False
    assert plan["geo_answer"]["generate"] is False
    assert plan["blog"]["generate"] is True


def test_surface_plan_does_not_treat_thin_description_as_evidence_for_fact_surfaces() -> None:
    # Thin description (< 12 words, no NER facts) → product_description/faq/geo blocked.
    # Informational intent + PAA → blog still allowed.
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
    assert plan["faq"]["generate"] is False
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
