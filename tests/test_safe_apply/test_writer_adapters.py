"""Tests for the writer adapters — dry-run preview and live write dispatch."""

from __future__ import annotations

from unittest.mock import MagicMock

from app.apply.shopify_writer import ApplyResult
from app.content_actions.schema import ContentType
from app.safe_apply.writer_adapters import dry_run_preview, is_live_supported, live_write


def test_dry_run_meta_title_preview():
    preview = dry_run_preview(ContentType.META_TITLE, "gid://shopify/Product/1", "Harnais chien")
    assert preview["dry_run"] is True
    assert preview["would_succeed"] is True
    assert "seo.title" in preview["would_change_fields"]
    assert preview["errors"] == []


def test_dry_run_faq_block_not_supported():
    preview = dry_run_preview(ContentType.FAQ_BLOCK, "gid://shopify/Product/1", '{"items":[]}')
    assert preview["would_succeed"] is False
    assert len(preview["errors"]) == 1
    assert "not supported" in preview["errors"][0]


def test_dry_run_all_supported_types_succeed():
    for ct in [ContentType.META_TITLE, ContentType.META_DESCRIPTION, ContentType.PRODUCT_DESCRIPTION]:
        preview = dry_run_preview(ct, "gid://shopify/Product/1", "texte test")
        assert preview["would_succeed"] is True, f"{ct} should succeed"


def test_is_live_supported_true_for_meta_types():
    assert is_live_supported(ContentType.META_TITLE) is True
    assert is_live_supported(ContentType.META_DESCRIPTION) is True
    assert is_live_supported(ContentType.PRODUCT_DESCRIPTION) is True


def test_is_live_supported_false_for_faq():
    assert is_live_supported(ContentType.FAQ_BLOCK) is False
    assert is_live_supported(ContentType.BUYING_GUIDE) is False


def test_live_write_meta_title_calls_apply_product_seo():
    writer = MagicMock()
    writer.apply_product_seo.return_value = ApplyResult(
        resource_id="gid://shopify/Product/1", applied=True, old_title="Ancien titre"
    )
    result = live_write(
        ContentType.META_TITLE,
        "gid://shopify/Product/1",
        "Nouveau titre",
        writer=writer,
    )
    writer.apply_product_seo.assert_called_once_with(
        "gid://shopify/Product/1", title="Nouveau titre", description=None
    )
    assert result["applied"] is True
    assert result["field"] == "seo.title"
    assert result["old_value"] == "Ancien titre"


def test_live_write_meta_description_calls_apply_product_seo():
    writer = MagicMock()
    writer.apply_product_seo.return_value = ApplyResult(
        resource_id="gid://shopify/Product/1", applied=True, old_description="Ancienne desc"
    )
    result = live_write(
        ContentType.META_DESCRIPTION,
        "gid://shopify/Product/1",
        "Nouvelle description",
        writer=writer,
    )
    writer.apply_product_seo.assert_called_once_with(
        "gid://shopify/Product/1", title=None, description="Nouvelle description"
    )
    assert result["applied"] is True
    assert result["old_value"] == "Ancienne desc"


def test_live_write_product_description_calls_apply_product_description():
    writer = MagicMock()
    writer.apply_product_description.return_value = ApplyResult(
        resource_id="gid://shopify/Product/1", applied=True
    )
    result = live_write(
        ContentType.PRODUCT_DESCRIPTION,
        "gid://shopify/Product/1",
        "<p>Description HTML.</p>",
        writer=writer,
    )
    writer.apply_product_description.assert_called_once()
    assert result["applied"] is True
    assert result["field"] == "descriptionHtml"


def test_live_write_unsupported_type_returns_not_applied():
    writer = MagicMock()
    result = live_write(
        ContentType.FAQ_BLOCK,
        "gid://shopify/Product/1",
        "[]",
        writer=writer,
    )
    assert result["applied"] is False
    writer.apply_product_seo.assert_not_called()


def test_live_write_shopify_error_returns_error_dict():
    from app.apply.shopify_writer import ShopifyWriteError  # noqa: PLC0415

    writer = MagicMock()
    writer.apply_product_seo.side_effect = ShopifyWriteError("rate limited")
    result = live_write(
        ContentType.META_TITLE,
        "gid://shopify/Product/1",
        "Titre test",
        writer=writer,
    )
    assert result["applied"] is False
    assert "rate limited" in result["errors"][0]
