"""Tests for scripts.apply.add_schema."""

import pytest

from scripts.apply.add_schema import ShopifyUserError, build_product_schema, push_schema

_PRODUCT = {
    "id": "gid://shopify/Product/1",
    "title": "Le Pardessus Pour Chien",
    "handle": "le-pardessus-pour-chien",
    "description": "Un pardessus élégant pour votre chien.",
    "status": "ACTIVE",
    "images": {
        "edges": [
            {"node": {"url": "https://cdn.shopify.com/img1.jpg"}},
            {"node": {"url": "https://cdn.shopify.com/img2.jpg"}},
        ]
    },
    "variants": {"edges": [{"node": {"price": "49.99"}}]},
}


# ── build_product_schema ──────────────────────────────────────────────────────


def test_build_product_schema_required_fields():
    schema = build_product_schema(_PRODUCT)
    assert schema["@context"] == "https://schema.org"
    assert schema["@type"] == "Product"
    assert schema["name"] == "Le Pardessus Pour Chien"
    assert "leoniedelacroix.com" in schema["url"]
    assert schema["brand"]["name"] == "Léonie Delacroix"


def test_build_product_schema_includes_offers_when_price_available():
    schema = build_product_schema(_PRODUCT)
    assert "offers" in schema
    assert schema["offers"]["price"] == "49.99"
    assert schema["offers"]["priceCurrency"] == "EUR"
    assert "InStock" in schema["offers"]["availability"]


def test_build_product_schema_out_of_stock_when_not_active():
    product = {**_PRODUCT, "status": "DRAFT"}
    schema = build_product_schema(product)
    assert "OutOfStock" in schema["offers"]["availability"]


def test_build_product_schema_no_offers_without_variants():
    product = {**_PRODUCT, "variants": {"edges": []}}
    schema = build_product_schema(product)
    assert "offers" not in schema


def test_build_product_schema_multiple_images():
    schema = build_product_schema(_PRODUCT)
    assert isinstance(schema["image"], list)
    assert len(schema["image"]) == 2


def test_build_product_schema_single_image_not_list():
    product = {
        **_PRODUCT,
        "images": {"edges": [{"node": {"url": "https://cdn.shopify.com/img1.jpg"}}]},
    }
    schema = build_product_schema(product)
    assert isinstance(schema["image"], str)


def test_build_product_schema_no_description_when_empty():
    product = {**_PRODUCT, "description": ""}
    schema = build_product_schema(product)
    assert "description" not in schema


# ── push_schema ───────────────────────────────────────────────────────────────


def test_push_schema_calls_metafields_set_mutation(mocker):
    mock_post = mocker.patch("requests.post")
    mock_post.return_value.status_code = 200
    mock_post.return_value.json.return_value = {
        "data": {
            "metafieldsSet": {
                "metafields": [
                    {
                        "id": "gid://shopify/Metafield/1",
                        "namespace": "custom",
                        "key": "json_ld",
                        "value": "{}",
                    }
                ],
                "userErrors": [],
            }
        }
    }

    push_schema("gid://shopify/Product/1", {"@type": "Product"}, endpoint="http://test", headers={})

    assert mock_post.called
    payload = mock_post.call_args.kwargs["json"]
    assert "metafieldsSet" in payload["query"]
    metafield = payload["variables"]["metafields"][0]
    assert metafield["namespace"] == "custom"
    assert metafield["key"] == "json_ld"
    assert metafield["type"] == "json"
    assert metafield["ownerId"] == "gid://shopify/Product/1"


def test_push_schema_raises_on_user_errors(mocker):
    mock_post = mocker.patch("requests.post")
    mock_post.return_value.status_code = 200
    mock_post.return_value.json.return_value = {
        "data": {
            "metafieldsSet": {
                "metafields": [],
                "userErrors": [{"field": ["value"], "message": "Invalid JSON", "code": "INVALID"}],
            }
        }
    }

    with pytest.raises(ShopifyUserError):
        push_schema("gid://shopify/Product/1", {}, endpoint="http://test", headers={})
