"""Tests for theme app embed detection from settings_data.json."""

from __future__ import annotations

import json

from app.apply.theme_extension_status import _app_embed_enabled


def _settings(blocks: dict) -> str:
    return json.dumps({"current": {"blocks": blocks}})


def test_enabled_when_app_embed_present_and_not_disabled() -> None:
    blocks = {"abc": {"type": "shopify://apps/giulio-geo/blocks/faq_embed/41c38ef1", "disabled": False}}
    assert _app_embed_enabled(_settings(blocks)) is True


def test_enabled_when_disabled_key_absent() -> None:
    blocks = {"abc": {"type": "leonie-seo-jsonld/faq_embed"}}
    assert _app_embed_enabled(_settings(blocks)) is True


def test_disabled_when_block_disabled() -> None:
    blocks = {"abc": {"type": "shopify://apps/x/blocks/faq_embed/41c38ef1", "disabled": True}}
    assert _app_embed_enabled(_settings(blocks)) is False


def test_false_when_no_matching_block() -> None:
    blocks = {"abc": {"type": "shopify://apps/other-app/blocks/foo/123", "disabled": False}}
    assert _app_embed_enabled(_settings(blocks)) is False


def test_none_on_malformed_json() -> None:
    assert _app_embed_enabled("{not json") is None


def test_false_when_no_blocks_section() -> None:
    """A valid theme with zero app embeds is 'not enabled', not 'unknown'."""
    assert _app_embed_enabled(json.dumps({"current": {}})) is False


def test_none_when_current_missing() -> None:
    assert _app_embed_enabled(json.dumps({"presets": {}})) is None

def test_enabled_when_current_is_a_preset_name() -> None:
    """Themes saved via the editor's preset picker store `current` as a preset
    NAME — the embed state then lives under presets[name].blocks."""
    settings = json.dumps({
        "current": "Default",
        "presets": {
            "Default": {
                "blocks": {
                    "abc": {"type": "shopify://apps/x/blocks/faq_embed/41c38ef1", "disabled": False}
                }
            }
        },
    })
    assert _app_embed_enabled(settings) is True


def test_disabled_when_preset_block_disabled() -> None:
    settings = json.dumps({
        "current": "Default",
        "presets": {
            "Default": {
                "blocks": {
                    "abc": {"type": "shopify://apps/x/blocks/faq_embed/41c38ef1", "disabled": True}
                }
            }
        },
    })
    assert _app_embed_enabled(settings) is False
