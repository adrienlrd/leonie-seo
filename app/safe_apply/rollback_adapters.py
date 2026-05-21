"""Rollback adapters — extend revert support to new content types."""

from __future__ import annotations

from app.content_actions.schema import ContentType
from app.safe_apply.writer_adapters import FIELD_FOR_CONTENT_TYPE

# Fields that can be reverted from seo_changes (includes V1 content action fields).
EXTENDED_REVERTIBLE_FIELDS = frozenset(FIELD_FOR_CONTENT_TYPE.values())


def is_revertible(content_type: ContentType) -> bool:
    """Return True if this content type supports live rollback via seo_changes in V1."""
    return content_type in FIELD_FOR_CONTENT_TYPE


def revert_field(
    resource_id: str,
    field: str,
    old_value: str,
    *,
    writer,
) -> dict:
    """Revert a single seo_changes field to its old value.

    Args:
        resource_id: Shopify product GID.
        field: Field name from seo_changes (seo.title / seo.description / descriptionHtml).
        old_value: Previous value to restore.
        writer: ShopifyWriter instance.

    Returns:
        Dict with applied (bool), field, errors.
    """
    from app.apply.shopify_writer import ShopifyWriteError  # noqa: PLC0415

    try:
        if field == "seo.title":
            result = writer.apply_product_seo(resource_id, title=old_value, description=None)
        elif field == "seo.description":
            result = writer.apply_product_seo(resource_id, title=None, description=old_value)
        elif field == "descriptionHtml":
            result = writer.apply_product_description(resource_id, old_value)
        else:
            return {
                "applied": False,
                "field": field,
                "errors": [f"Revert not supported for field '{field}' in V1."],
            }

        return {
            "applied": result.applied,
            "field": field,
            "errors": [result.error] if result.error else [],
        }
    except (ShopifyWriteError, Exception) as exc:
        return {"applied": False, "field": field, "errors": [str(exc)]}
