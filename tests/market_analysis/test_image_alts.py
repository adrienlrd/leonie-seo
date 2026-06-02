"""Unit tests for product image alt-text generation in the market analysis engine."""

from __future__ import annotations

from app.market_analysis import engine


def _images(n: int) -> list[dict[str, str]]:
    return [
        {"id": f"gid://shopify/MediaImage/{i}", "url": f"https://cdn/{i}.jpg", "current_alt": None}
        for i in range(1, n + 1)
    ]


def test_fill_image_alts_keeps_llm_value_matched_by_id() -> None:
    images = _images(2)
    llm = [{"image_id": "gid://shopify/MediaImage/2", "proposed_alt": "Sac de croquettes senior"}]

    result = engine._fill_image_alts(llm, images, "Croquettes Chien Senior", "croquettes senior")

    assert len(result) == 2
    assert result[1] == {
        "image_id": "gid://shopify/MediaImage/2",
        "proposed_alt": "Sac de croquettes senior",
    }


def test_fill_image_alts_falls_back_for_missing_images() -> None:
    images = _images(3)
    llm = [{"image_id": "gid://shopify/MediaImage/1", "proposed_alt": "Vue principale du sac"}]

    result = engine._fill_image_alts(llm, images, "Croquettes Chien Senior", "croquettes senior")

    assert len(result) == 3
    assert result[0]["proposed_alt"] == "Vue principale du sac"
    # The two images the LLM skipped get a deterministic, keyword-aware fallback.
    assert "Croquettes Chien Senior" in result[1]["proposed_alt"]
    assert "croquettes senior" in result[1]["proposed_alt"]
    assert "vue 3" in result[2]["proposed_alt"]
    assert all(len(item["proposed_alt"]) <= 125 for item in result)


def test_fill_image_alts_returns_empty_without_images() -> None:
    assert engine._fill_image_alts([], [], "Produit", "mot-clé") == []


def test_default_image_alt_truncates_to_125_chars() -> None:
    long_title = "A" * 200
    alt = engine._default_image_alt(long_title, "mot-clé", 0)
    assert len(alt) <= 125
