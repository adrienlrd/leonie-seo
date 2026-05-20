"""Tests for prompt template loader and rendering."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from app.llm.prompts import PromptError, load_prompt, reset_prompt_cache


@pytest.fixture(autouse=True)
def clear_cache():
    reset_prompt_cache()
    yield
    reset_prompt_cache()


@pytest.fixture()
def prompts_dir(tmp_path: Path) -> Path:
    d = tmp_path / "prompts"
    d.mkdir()
    return d


def _write_prompt(directory: Path, name: str, **overrides: object) -> Path:
    data = {
        "version": "1.0",
        "system": "You are an SEO expert.",
        "user": "Write a meta title for {{ product_title }}.",
        "max_tokens": 80,
        "temperature": 0.2,
        **overrides,
    }
    path = directory / f"{name}.yaml"
    path.write_text(yaml.dump(data), encoding="utf-8")
    return path


# ── Loading ───────────────────────────────────────────────────────────────────


def test_load_prompt_returns_template(prompts_dir):
    _write_prompt(prompts_dir, "meta_title")
    tmpl = load_prompt("meta_title", prompts_dir=prompts_dir)
    assert tmpl.name == "meta_title"
    assert tmpl.version == "1.0"
    assert tmpl.max_tokens == 80
    assert tmpl.temperature == 0.2


def test_load_prompt_raises_when_file_missing(prompts_dir):
    with pytest.raises(PromptError, match="not found"):
        load_prompt("nonexistent", prompts_dir=prompts_dir)


def test_load_prompt_error_lists_available_templates(prompts_dir):
    _write_prompt(prompts_dir, "meta_title")
    with pytest.raises(PromptError, match="meta_title"):
        load_prompt("missing", prompts_dir=prompts_dir)


def test_load_prompt_raises_when_required_field_missing(prompts_dir):
    path = prompts_dir / "bad.yaml"
    path.write_text(yaml.dump({"version": "1.0", "system": "s"}), encoding="utf-8")
    with pytest.raises(PromptError, match="missing required field"):
        load_prompt("bad", prompts_dir=prompts_dir)


def test_load_prompt_is_cached(prompts_dir):
    _write_prompt(prompts_dir, "meta_title")
    t1 = load_prompt("meta_title", prompts_dir=prompts_dir)
    t2 = load_prompt("meta_title", prompts_dir=prompts_dir)
    assert t1 is t2


# ── Rendering ─────────────────────────────────────────────────────────────────


def test_render_user_substitutes_variables(prompts_dir):
    _write_prompt(
        prompts_dir, "meta_title", user="Title for {{ product_title }} in {{ category }}."
    )
    tmpl = load_prompt("meta_title", prompts_dir=prompts_dir)
    result = tmpl.render_user(product_title="Pardessus Chien", category="Vêtements")
    assert result == "Title for Pardessus Chien in Vêtements."


def test_render_user_raises_on_missing_variable(prompts_dir):
    _write_prompt(prompts_dir, "meta_title", user="Title for {{ product_title }}.")
    tmpl = load_prompt("meta_title", prompts_dir=prompts_dir)
    with pytest.raises(PromptError, match="Missing variable"):
        tmpl.render_user()


def test_render_system_returns_static_system_prompt(prompts_dir):
    _write_prompt(prompts_dir, "meta_title", system="You are SEO expert.")
    tmpl = load_prompt("meta_title", prompts_dir=prompts_dir)
    assert tmpl.render_system() == "You are SEO expert."


def test_render_user_strips_whitespace(prompts_dir):
    _write_prompt(prompts_dir, "meta_title", user="  Hello {{ name }}  \n")
    tmpl = load_prompt("meta_title", prompts_dir=prompts_dir)
    assert tmpl.render_user(name="world") == "Hello world"


def test_render_user_supports_jinja2_filters(prompts_dir):
    _write_prompt(
        prompts_dir,
        "meta_title",
        user="Keywords: {{ keywords | join(', ') }}",
    )
    tmpl = load_prompt("meta_title", prompts_dir=prompts_dir)
    result = tmpl.render_user(keywords=["chien", "harnais", "premium"])
    assert result == "Keywords: chien, harnais, premium"


def test_render_user_supports_optional_blocks(prompts_dir):
    _write_prompt(
        prompts_dir,
        "meta_title",
        user="Product: {{ product_title }}{% if note %} ({{ note }}){% endif %}",
    )
    tmpl = load_prompt("meta_title", prompts_dir=prompts_dir)
    assert tmpl.render_user(product_title="Bol", note="") == "Product: Bol"
    assert tmpl.render_user(product_title="Bol", note="bio") == "Product: Bol (bio)"


# ── Real templates smoke test ─────────────────────────────────────────────────


@pytest.mark.parametrize(
    "template_name,variables",
    [
        (
            "meta_title",
            {
                "product_title": "Pardessus pour chien",
                "primary_niche": "vêtements pour chien",
                "brand_voice_tone": "professionnel",
                "primary_keyword": "pardessus chien",
                "secondary_keywords": ["manteau chien", "vêtement chien"],
                "confirmed_facts": [],
                "do_not_say": [],
                "feedback": "",
            },
        ),
        (
            "meta_description",
            {
                "product_title": "Pardessus pour chien",
                "primary_niche": "vêtements pour chien",
                "brand_voice_tone": "professionnel",
                "meta_title": "Pardessus chien premium",
                "primary_keyword": "pardessus chien",
                "current_seo_description": "Un beau pardessus.",
                "confirmed_facts": [],
                "customer_segments": [],
                "forbidden_promises": [],
                "do_not_say": [],
                "feedback": "",
            },
        ),
        (
            "alt_text",
            {
                "product_title": "Fontaine à eau chat",
                "primary_niche": "accessoires pour chat",
                "primary_keyword": "fontaine eau chat",
                "image_context": "chat qui boit",
                "confirmed_facts": [],
            },
        ),
        (
            "product_description",
            {
                "product_title": "Harnais chat",
                "primary_niche": "accessoires pour chat",
                "brand_voice_tone": "professionnel",
                "brand_voice_register": "standard",
                "primary_keyword": "harnais chat",
                "secondary_keywords": ["harnais chat escapade", "harnais chat sécurité"],
                "confirmed_facts": [{"key": "materials", "value": "coton bio"}],
                "marketing_angles": ["durabilité"],
                "current_description": "Harnais confortable.",
                "do_not_say": [],
                "forbidden_promises": [],
                "feedback": "",
            },
        ),
        (
            "blog_brief",
            {
                "target_query": "comment choisir harnais chat",
                "search_intent": "informationnelle",
                "cluster": "harnais chat",
                "competitor_titles": ["Top 5 harnais chats"],
                "search_volume": "320",
                "current_position": "non classé",
            },
        ),
    ],
)
def test_real_template_renders_without_error(template_name, variables):
    """Smoke test: all shipped templates render without missing-variable errors."""
    tmpl = load_prompt(template_name)
    rendered = tmpl.render_user(**variables)
    assert len(rendered) > 10
