"""Tests for versioned business profile context metadata."""

from __future__ import annotations

from app.business_profile.context import (
    build_business_profile_context_meta,
    compute_business_profile_context_hash,
    resolve_business_profile_context_status,
)


def _profile(**overrides: object) -> dict[str, object]:
    profile: dict[str, object] = {
        "brand_name": "Leonie",
        "niche_summary": "Premium cat accessories.",
        "brand_voice": "Expert and reassuring.",
        "target_personas": [{"name": "Careful owner", "main_need": "Reliable product"}],
        "content_style": {"tone": "precise", "vocabulary_to_use": ["hydration"]},
        "key_themes": ["cat wellbeing"],
        "competitor_domains": ["competitor.example"],
        "competitor_insights": ["Competitors focus on silence."],
        "content_gaps": ["Usage guide"],
        "internal_link_priorities": ["cat-fountain"],
        "generated_at": "2026-05-28T10:00:00+00:00",
    }
    profile.update(overrides)
    return profile


def test_hash_ignores_generated_at_when_profile_content_is_unchanged() -> None:
    first = _profile(generated_at="2026-05-28T10:00:00+00:00")
    second = _profile(generated_at="2026-05-28T11:00:00+00:00")

    assert compute_business_profile_context_hash(first) == compute_business_profile_context_hash(
        second
    )


def test_hash_changes_when_profile_context_changes() -> None:
    first = _profile(brand_voice="Expert and reassuring.")
    second = _profile(brand_voice="Playful and direct.")

    assert compute_business_profile_context_hash(first) != compute_business_profile_context_hash(
        second
    )


def test_status_is_stale_when_stored_hash_differs_from_current_profile() -> None:
    stored = build_business_profile_context_meta(_profile())["hash"]

    assert (
        resolve_business_profile_context_status(stored, _profile(content_gaps=["Comparison page"]))
        == "stale"
    )


def test_status_is_unknown_when_analysis_has_no_stored_hash() -> None:
    assert resolve_business_profile_context_status(None, _profile()) == "unknown"
