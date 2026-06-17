"""Tests for surface-aware outcome scoring, decomposition and word features."""

from __future__ import annotations

from app.learning.features import (
    features_for_candidate,
    features_for_observation,
    text_features,
)
from app.learning.models import CandidateAction, LearningObservation, RiskLevel
from app.learning.outcomes import calculate_confidence, calculate_outcome
from app.learning.surface_metrics import (
    decompose_outcome,
    get_metric_profile,
    weighted_outcome,
)


def _observation(*, window_purity: str, text_new: str = "Harnais Premium Chien") -> LearningObservation:
    return LearningObservation(
        shop="s.myshopify.com",
        resource_type="product",
        resource_id="gid://shopify/Product/1",
        action_type="meta_title",
        surface="product_page",
        keyword_source="gsc",
        before_metrics={},
        after_metrics={},
        control_metrics={},
        window_days=28,
        window_label="J+28",
        is_primary_window=True,
        outcome_score=20.0,
        confidence_score=70,
        metadata={
            "window_purity": window_purity,
            "text_field": "meta_title",
            "text_new": text_new,
        },
    )


def test_meta_description_profile_ignores_impressions() -> None:
    profile = get_metric_profile("meta_description")
    assert profile.get("impressions", 0.0) == 0.0
    assert profile.get("position", 0.0) == 0.0
    assert profile["ctr"] > 0
    assert profile["clicks"] > 0


def test_meta_title_profile_uses_position_and_ctr() -> None:
    profile = get_metric_profile("meta_title")
    assert profile["position"] > 0
    assert profile["ctr"] > 0


def test_unknown_surface_falls_back_to_default_profile() -> None:
    profile = get_metric_profile("totally_unknown_field")
    # Default profile mixes impressions + clicks like the historical weighting.
    assert profile["impressions"] > 0
    assert profile["clicks"] > 0


def test_action_type_alias_maps_to_surface() -> None:
    profile = get_metric_profile(None, "enrich_product_facts")
    assert profile == get_metric_profile("schema_facts")


def test_meta_description_outcome_ignores_impressions_gain() -> None:
    """A description that only moved impressions (impossible cause) scores ~0."""
    deltas_impressions_only = {
        "impressions": 1.0,
        "clicks": 0.0,
        "ctr": 0.0,
        "position": 0.0,
        "conversions": 0.0,
        "revenue": 0.0,
        "score": 0.0,
    }
    desc_score = weighted_outcome(deltas_impressions_only, get_metric_profile("meta_description"))
    title_score = weighted_outcome(deltas_impressions_only, get_metric_profile("meta_title"))
    assert desc_score == 0.0
    assert title_score > 0.0


def test_calculate_outcome_surface_aware_differs_from_default() -> None:
    before = {"gsc": {"impressions": 100, "clicks": 5, "ctr": 0.05, "position": 12.0}}
    after = {"gsc": {"impressions": 400, "clicks": 6, "ctr": 0.015, "position": 12.0}}
    # Big impressions gain, flat clicks. For a description this should NOT be
    # credited (impressions aren't its lever); for a title it should.
    desc = calculate_outcome(before_metrics=before, after_metrics=after, field="meta_description")
    title = calculate_outcome(before_metrics=before, after_metrics=after, field="meta_title")
    assert title["outcome_score"] > desc["outcome_score"]


def test_calculate_outcome_includes_decomposition() -> None:
    before = {"gsc": {"impressions": 100, "clicks": 5, "ctr": 0.05, "position": 12.0}}
    after = {"gsc": {"impressions": 100, "clicks": 9, "ctr": 0.09, "position": 12.0}}
    result = calculate_outcome(before_metrics=before, after_metrics=after, field="meta_description")
    decomp = result["decomposition"]
    assert decomp["primary_metric"] in {"ctr", "clicks"}
    assert decomp["direction"] == "up"
    assert decomp["cause_fr"]


def test_decompose_outcome_flat_when_no_movement() -> None:
    flat = dict.fromkeys(
        ["impressions", "clicks", "ctr", "position", "conversions", "revenue", "score"], 0.0
    )
    decomp = decompose_outcome(flat, field="meta_title")
    assert decomp["primary_metric"] is None
    assert decomp["direction"] == "flat"


def test_confidence_clean_window_beats_mixed_window() -> None:
    before = {"gsc": {"impressions": 600, "clicks": 30, "ctr": 0.05, "position": 10.0}}
    after = {"gsc": {"impressions": 700, "clicks": 40, "ctr": 0.057, "position": 8.0}}
    deltas = calculate_outcome(before_metrics=before, after_metrics=after, field="meta_title")[
        "deltas"
    ]
    clean = calculate_confidence(
        before_metrics=before,
        after_metrics=after,
        control_metrics=None,
        window_days=28,
        outcome_deltas=deltas,
        window_purity="clean",
    )
    mixed = calculate_confidence(
        before_metrics=before,
        after_metrics=after,
        control_metrics=None,
        window_days=28,
        outcome_deltas=deltas,
        window_purity="mixed",
    )
    assert clean > mixed


def test_text_features_extracts_surface_tagged_words() -> None:
    features = text_features("meta_title", "Harnais Premium pour Chien Naturel")
    keys = {k for k, _ in features}
    values = {v for _, v in features}
    assert "title_word" in keys
    assert "title_bigram" in keys
    assert "premium" in values
    assert "chien" in values


def test_text_features_strips_stopwords_and_accents() -> None:
    features = text_features("meta_description", "Le meilleur shampooing très naturel pour la peau")
    values = {v for _, v in features}
    # Stopwords dropped, accents normalised.
    assert "le" not in values
    assert "tres" not in values  # "très" → "tres" but it is a stopword → dropped
    assert "naturel" in values
    assert "shampooing" in values


def test_text_features_respects_limit() -> None:
    long_text = " ".join(f"mot{i}" for i in range(50))
    features = text_features("meta_description", long_text, limit=8)
    assert len(features) <= 8


def test_text_features_different_prefix_per_surface() -> None:
    title = text_features("meta_title", "chien premium")
    desc = text_features("meta_description", "chien premium")
    title_keys = {k for k, _ in title}
    desc_keys = {k for k, _ in desc}
    assert "title_word" in title_keys
    assert "desc_word" in desc_keys
    assert title_keys.isdisjoint(desc_keys)


def test_observation_emits_word_features_on_clean_window() -> None:
    features = features_for_observation(_observation(window_purity="clean"))
    values = {v for _, v in features}
    assert "premium" in values
    assert "chien" in values


def test_observation_skips_word_features_on_mixed_window() -> None:
    features = features_for_observation(_observation(window_purity="mixed"))
    values = {v for _, v in features}
    # No word-level features credited when several surfaces changed together.
    assert "premium" not in values
    assert "chien" not in values
    # Base features still present.
    assert any(k == "action_type" for k, _ in features)


def test_candidate_emits_word_features_from_proposed_value() -> None:
    candidate = CandidateAction(
        shop="s.myshopify.com",
        resource_type="product",
        resource_id="gid://shopify/Product/1",
        resource_title="Harnais",
        action_type="meta_title",
        field="meta_title",
        surface="product_page",
        current_score=50.0,
        potential_score=70.0,
        confidence_score=60,
        risk_level=RiskLevel.LOW,
        proposed_value="Harnais Premium Chien Naturel",
    )
    features = features_for_candidate(candidate)
    values = {v for _, v in features}
    assert "premium" in values
    assert "naturel" in values
