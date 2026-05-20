"""Tests for ContentAction schema models."""

from __future__ import annotations

from app.content_actions.schema import (
    ContentActionRequest,
    ContentActionResult,
    ContentOutput,
    ContentStatus,
    ContentType,
    ResourceInput,
)


def test_content_type_values():
    assert ContentType.META_TITLE == "meta_title"
    assert ContentType.FAQ_BLOCK == "faq_block"
    assert ContentType.JSONLD_FAQPAGE == "jsonld_faqpage"


def test_content_action_request_defaults():
    req = ContentActionRequest(
        content_type=ContentType.META_TITLE,
        resource=ResourceInput(id="gid://shopify/Product/1"),
    )
    assert req.content_type == ContentType.META_TITLE
    assert req.confirmed_facts == []
    assert req.missing_facts == []
    assert req.constraints.locale == "fr"


def test_content_action_result_defaults():
    result = ContentActionResult(
        action_id="abc123",
        content_type=ContentType.META_TITLE,
        resource_id="gid://shopify/Product/1",
        generated_at="2026-05-20T12:00:00+00:00",
        output=ContentOutput(primary_text="Test meta title SEO"),
    )
    assert result.status == ContentStatus.DRAFT
    assert result.facts_used == []
    assert result.quality.score == 0


def test_content_output_serializes():
    out = ContentOutput(primary_text="Hello", structured={"key": "value"})
    d = out.model_dump()
    assert d["primary_text"] == "Hello"
    assert d["structured"] == {"key": "value"}


def test_request_roundtrip_json():
    req = ContentActionRequest(
        content_type=ContentType.PRODUCT_DESCRIPTION,
        resource=ResourceInput(id="gid://shopify/Product/42", title="Harnais nylon"),
    )
    serialized = req.model_dump_json()
    restored = ContentActionRequest.model_validate_json(serialized)
    assert restored.content_type == ContentType.PRODUCT_DESCRIPTION
    assert restored.resource.id == "gid://shopify/Product/42"
