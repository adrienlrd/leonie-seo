"""Tests for SERP-feature-driven search intent classification."""

from __future__ import annotations

from app.market_analysis import intent_classifier as ic


def _serp(
    paa: list[str] | None = None,
    competitors: list[dict] | None = None,
    featured_snippet: str | None = None,
    has_ai_overview: bool = False,
) -> dict:
    return {
        "paa": paa or [],
        "top_competitors": competitors or [],
        "featured_snippet": featured_snippet,
        "has_ai_overview": has_ai_overview,
    }


class TestClassifyIntent:
    def test_transactional_when_ecommerce_dominates_serp(self):
        result = ic.classify_intent(
            query="croquettes chien sans cereales",
            serp=_serp(
                competitors=[
                    {"domain": "zooplus.fr", "title": "Croquettes chien sans céréales | Acheter", "rank": 1},
                    {"domain": "amazon.fr", "title": "Croquettes chien — Livraison gratuite", "rank": 2},
                    {"domain": "wanimo.com", "title": "Croquettes premium sans céréales prix bas", "rank": 3},
                ]
            ),
        )
        assert result["intent_type"] == "transactional"
        assert result["intent_type_source"] == "serp_classified"

    def test_informational_when_paa_present_and_no_ecommerce(self):
        result = ic.classify_intent(
            query="pourquoi mon chien mange t-il de l'herbe",
            serp=_serp(
                paa=[
                    "Pourquoi mon chien mange de l'herbe ?",
                    "Est-ce dangereux ?",
                    "Que faire si mon chien vomit ?",
                ],
                competitors=[
                    {"domain": "wamiz.com", "title": "Pourquoi votre chien mange de l'herbe", "rank": 1},
                    {"domain": "30millionsdamis.fr", "title": "Chien mangeant de l'herbe : explications", "rank": 2},
                ],
            ),
        )
        assert result["intent_type"] == "informational"
        assert result["intent_type_source"] == "serp_classified"

    def test_commercial_investigation_when_comparison_pattern_in_titles(self):
        result = ic.classify_intent(
            query="meilleur harnais chien",
            serp=_serp(
                competitors=[
                    {"domain": "lesmeilleurschoix.fr", "title": "Top 10 des meilleurs harnais pour chien 2025", "rank": 1},
                    {"domain": "comparatif-test.com", "title": "Comparatif harnais chien : notre sélection", "rank": 2},
                    {"domain": "guide-chien.fr", "title": "Quel harnais choisir pour son chien ? Guide complet", "rank": 3},
                ]
            ),
        )
        assert result["intent_type"] == "commercial_investigation"

    def test_local_when_geo_signals_in_query_or_paa(self):
        result = ic.classify_intent(
            query="vétérinaire chien près de moi",
            serp=_serp(
                paa=["Quel vétérinaire à Lyon ?", "Coût consultation vétérinaire ?"],
            ),
        )
        assert result["intent_type"] == "local"

    def test_falls_back_to_llm_guess_when_serp_missing(self):
        result = ic.classify_intent(query="harnais chien", serp=None, llm_intent="commercial")
        assert result["intent_type"] == "commercial"
        assert result["intent_type_source"] == "llm_guessed"

    def test_falls_back_to_llm_guess_when_serp_empty(self):
        result = ic.classify_intent(query="harnais chien", serp=_serp(), llm_intent="transactional")
        assert result["intent_type"] == "transactional"
        assert result["intent_type_source"] == "llm_guessed"

    def test_unknown_when_no_serp_and_no_llm(self):
        result = ic.classify_intent(query="x", serp=None, llm_intent=None)
        assert result["intent_type"] == "unknown"
        assert result["intent_type_source"] == "unclassified"


class TestSerpFeatureTargets:
    def test_emits_paa_target_when_paa_present(self):
        result = ic.classify_intent(
            query="x", serp=_serp(paa=["Q1?", "Q2?"]), llm_intent="informational"
        )
        assert "paa" in result["serp_feature_targets"]

    def test_emits_featured_snippet_target_when_present(self):
        result = ic.classify_intent(
            query="x",
            serp=_serp(featured_snippet="Un harnais pour chien est…"),
            llm_intent="informational",
        )
        assert "featured_snippet" in result["serp_feature_targets"]

    def test_emits_ai_overview_target_when_flagged(self):
        result = ic.classify_intent(
            query="x", serp=_serp(has_ai_overview=True), llm_intent="informational"
        )
        assert "ai_overview" in result["serp_feature_targets"]

    def test_no_targets_when_no_features(self):
        result = ic.classify_intent(query="x", serp=_serp(), llm_intent="commercial")
        assert result["serp_feature_targets"] == []


class TestBatchClassify:
    def test_classifies_all_keywords_in_batch(self):
        serp_intel = {
            "croquettes chien": {
                "paa": [],
                "top_competitors": [
                    {"domain": "zooplus.fr", "title": "Acheter croquettes", "rank": 1},
                    {"domain": "amazon.fr", "title": "Croquettes prix", "rank": 2},
                    {"domain": "wanimo.com", "title": "Croquettes livraison", "rank": 3},
                ],
                "featured_snippet": None,
            },
            "pourquoi chien aboie": {
                "paa": ["Pourquoi ?", "Comment l'éviter ?"],
                "top_competitors": [
                    {"domain": "wamiz.com", "title": "Aboiements du chien", "rank": 1}
                ],
                "featured_snippet": None,
            },
        }
        results = ic.classify_batch(serp_intel, llm_intents={})
        assert results["croquettes chien"]["intent_type"] == "transactional"
        assert results["pourquoi chien aboie"]["intent_type"] == "informational"

    def test_uses_llm_intent_fallback_per_keyword(self):
        results = ic.classify_batch(
            serp_intel={"x": {"paa": [], "top_competitors": [], "featured_snippet": None}},
            llm_intents={"x": "commercial"},
        )
        assert results["x"]["intent_type_source"] == "llm_guessed"
