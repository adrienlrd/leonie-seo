"""Writer adapters — dispatch ContentType to the appropriate Shopify mutation."""

from __future__ import annotations

from app.content_actions.schema import ContentType

# V1: content types with real live-write support via existing shopify_writer mutations.
_LIVE_SUPPORTED = frozenset({
    ContentType.META_TITLE,
    ContentType.META_DESCRIPTION,
    ContentType.PRODUCT_DESCRIPTION,
})

# Maps content_type → field label stored in seo_changes for rollback.
FIELD_FOR_CONTENT_TYPE: dict[ContentType, str] = {
    ContentType.META_TITLE: "seo.title",
    ContentType.META_DESCRIPTION: "seo.description",
    ContentType.PRODUCT_DESCRIPTION: "descriptionHtml",
}


def is_live_supported(content_type: ContentType) -> bool:
    """Return True if live Shopify apply is available for this content type in V1."""
    return content_type in _LIVE_SUPPORTED


def dry_run_preview(
    content_type: ContentType,
    resource_id: str,
    text: str,
) -> dict:
    """Return a dry-run preview without touching Shopify.

    Args:
        content_type: The ContentType being applied.
        resource_id: Shopify resource GID.
        text: The generated text to preview.

    Returns:
        DryRunResult dict compatible with the /dry-run endpoint schema.
    """
    field = FIELD_FOR_CONTENT_TYPE.get(content_type)
    supported = field is not None
    return {
        "dry_run": True,
        "would_succeed": supported,
        "would_change_fields": [field] if field else [],
        "before_drift_detected": False,
        "shopify_request_preview": {
            "resource_id": resource_id,
            "field": field,
            "new_value_preview": text[:120] + "…" if len(text) > 120 else text,
        },
        "errors": (
            []
            if supported
            else [f"{content_type.value} live apply not supported in V1 — use export instead."]
        ),
    }


def live_write(
    content_type: ContentType,
    resource_id: str,
    text: str,
    *,
    writer,
) -> dict:
    """Apply content to Shopify via the appropriate mutation.

    Args:
        content_type: The ContentType being applied.
        resource_id: Shopify product/collection GID.
        text: Generated text to push.
        writer: ShopifyWriter instance.

    Returns:
        Dict with applied (bool), field, old_value, errors.
    """
    from app.apply.shopify_writer import ShopifyWriteError  # noqa: PLC0415

    field = FIELD_FOR_CONTENT_TYPE.get(content_type)
    if field is None:
        return {
            "applied": False,
            "field": None,
            "old_value": None,
            "errors": [f"{content_type.value} live apply not supported in V1 — use export."],
        }

    try:
        if content_type == ContentType.META_TITLE:
            result = writer.apply_product_seo(resource_id, title=text, description=None)
            old_val = result.old_title
        elif content_type == ContentType.META_DESCRIPTION:
            result = writer.apply_product_seo(resource_id, title=None, description=text)
            old_val = result.old_description
        else:
            result = writer.apply_product_description(resource_id, text)
            old_val = None

        return {
            "applied": result.applied,
            "field": field,
            "old_value": old_val,
            "errors": [result.error] if result.error else [],
        }
    except (ShopifyWriteError, Exception) as exc:
        return {
            "applied": False,
            "field": field,
            "old_value": None,
            "errors": [str(exc)],
        }
