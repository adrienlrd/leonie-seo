"""Tests for Schema.org JSON-LD builders."""

from __future__ import annotations

from app.jsonld.builders import (
    build_collection_jsonld,
    build_organization_jsonld,
    build_product_jsonld,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_SHOP = {
    "name": "Léonie Delacroix",
    "domain": "www.leoniedelacroix.com",
    "currency": "EUR",
    "country_code": "FR",
    "city": "Paris",
    "zip": "75001",
    "email": "contact@leoniedelacroix.com",
    "phone": "+33123456789",
}

_PRODUCT = {
    "id": 123,
    "title": "Harnais Premium Chien",
    "handle": "harnais-premium-chien",
    "body_html": "<p>Harnais <strong>confort</strong> fabriqué en France.</p>",
    "images": [
        {"src": "https://cdn.shopify.com/s/files/harnais.jpg"},
        {"src": "https://cdn.shopify.com/s/files/harnais2.jpg"},
    ],
    "variants": [
        {
            "price": "4999",
            "sku": "HARN-001",
            "inventory_quantity": 10,
            "inventory_management": "shopify",
        }
    ],
}

_COLLECTION = {
    "id": 456,
    "title": "Harnais pour chiens",
    "handle": "harnais-chiens",
    "body_html": "<p>Notre sélection de harnais premium.</p>",
    "image": {"src": "https://cdn.shopify.com/s/files/harnais-col.jpg"},
}


# ---------------------------------------------------------------------------
# build_product_jsonld
# ---------------------------------------------------------------------------


def test_build_product_jsonld_has_context_and_type():
    data = build_product_jsonld(_PRODUCT, _SHOP)
    assert data["@context"] == "https://schema.org/"
    assert data["@type"] == "Product"


def test_build_product_jsonld_name_and_url():
    data = build_product_jsonld(_PRODUCT, _SHOP)
    assert data["name"] == "Harnais Premium Chien"
    assert data["url"] == "https://www.leoniedelacroix.com/products/harnais-premium-chien"


def test_build_product_jsonld_strips_html_description():
    data = build_product_jsonld(_PRODUCT, _SHOP)
    assert "<p>" not in data["description"]
    assert "Harnais" in data["description"]


def test_build_product_jsonld_brand_is_shop_name():
    data = build_product_jsonld(_PRODUCT, _SHOP)
    assert data["brand"]["@type"] == "Brand"
    assert data["brand"]["name"] == "Léonie Delacroix"


def test_build_product_jsonld_offer_price_and_currency():
    data = build_product_jsonld(_PRODUCT, _SHOP)
    offer = data["offers"]
    assert offer["@type"] == "Offer"
    assert offer["priceCurrency"] == "EUR"
    assert offer["price"] == "4999"


def test_build_product_jsonld_in_stock():
    data = build_product_jsonld(_PRODUCT, _SHOP)
    assert data["offers"]["availability"] == "https://schema.org/InStock"


def test_build_product_jsonld_out_of_stock():
    product = {
        **_PRODUCT,
        "variants": [{"price": "4999", "inventory_quantity": 0, "inventory_management": "shopify"}],
    }
    data = build_product_jsonld(product, _SHOP)
    assert data["offers"]["availability"] == "https://schema.org/OutOfStock"


def test_build_product_jsonld_multiple_images():
    data = build_product_jsonld(_PRODUCT, _SHOP)
    assert "image" in data
    assert len(data["image"]) == 2


def test_build_product_jsonld_no_image_omits_key():
    product = {**_PRODUCT, "images": []}
    data = build_product_jsonld(product, _SHOP)
    assert "image" not in data


def test_build_product_jsonld_sku_present():
    data = build_product_jsonld(_PRODUCT, _SHOP)
    assert data["sku"] == "HARN-001"


def test_build_product_jsonld_sku_absent_when_empty():
    product = {**_PRODUCT, "variants": [{"price": "4999", "sku": "", "inventory_quantity": 5}]}
    data = build_product_jsonld(product, _SHOP)
    assert "sku" not in data


def test_build_product_jsonld_breadcrumb_structure():
    data = build_product_jsonld(_PRODUCT, _SHOP)
    bc = data["breadcrumb"]
    assert bc["@type"] == "BreadcrumbList"
    items = bc["itemListElement"]
    assert items[0]["position"] == 1
    assert items[0]["name"] == "Accueil"
    assert items[1]["position"] == 2
    assert items[1]["name"] == "Harnais Premium Chien"


# ---------------------------------------------------------------------------
# build_collection_jsonld
# ---------------------------------------------------------------------------


def test_build_collection_jsonld_has_context_and_type():
    data = build_collection_jsonld(_COLLECTION, _SHOP)
    assert data["@context"] == "https://schema.org/"
    assert data["@type"] == "CollectionPage"


def test_build_collection_jsonld_name_and_url():
    data = build_collection_jsonld(_COLLECTION, _SHOP)
    assert data["name"] == "Harnais pour chiens"
    assert data["url"] == "https://www.leoniedelacroix.com/collections/harnais-chiens"


def test_build_collection_jsonld_breadcrumb():
    data = build_collection_jsonld(_COLLECTION, _SHOP)
    bc = data["breadcrumb"]
    assert bc["@type"] == "BreadcrumbList"
    items = bc["itemListElement"]
    assert len(items) == 2
    assert items[0]["name"] == "Accueil"
    assert items[1]["name"] == "Harnais pour chiens"


def test_build_collection_jsonld_description_stripped():
    data = build_collection_jsonld(_COLLECTION, _SHOP)
    assert "<p>" not in data.get("description", "")


def test_build_collection_jsonld_image():
    data = build_collection_jsonld(_COLLECTION, _SHOP)
    assert data["image"] == "https://cdn.shopify.com/s/files/harnais-col.jpg"


def test_build_collection_jsonld_no_image_omits_key():
    collection = {**_COLLECTION, "image": None}
    data = build_collection_jsonld(collection, _SHOP)
    assert "image" not in data


# ---------------------------------------------------------------------------
# build_organization_jsonld
# ---------------------------------------------------------------------------


def test_build_organization_jsonld_has_context_and_type():
    data = build_organization_jsonld(_SHOP)
    assert data["@context"] == "https://schema.org"
    assert data["@type"] == "Organization"


def test_build_organization_jsonld_name_and_url():
    data = build_organization_jsonld(_SHOP)
    assert data["name"] == "Léonie Delacroix"
    assert data["url"] == "https://www.leoniedelacroix.com"


def test_build_organization_jsonld_email_and_phone():
    data = build_organization_jsonld(_SHOP)
    assert data["email"] == "contact@leoniedelacroix.com"
    assert data["telephone"] == "+33123456789"


def test_build_organization_jsonld_address():
    data = build_organization_jsonld(_SHOP)
    assert data["address"]["@type"] == "PostalAddress"
    assert data["address"]["addressCountry"] == "FR"
    assert data["address"]["addressLocality"] == "Paris"
    assert data["address"]["postalCode"] == "75001"


def test_build_organization_jsonld_no_email_omits_key():
    shop = {k: v for k, v in _SHOP.items() if k != "email"}
    data = build_organization_jsonld(shop)
    assert "email" not in data


def test_build_organization_jsonld_social_links():
    shop = {
        **_SHOP,
        "social": ["https://instagram.com/leoniedelacroix", "https://facebook.com/leoniedelacroix"],
    }
    data = build_organization_jsonld(shop)
    assert "sameAs" in data
    assert len(data["sameAs"]) == 2


def test_build_organization_jsonld_myshopify_domain_fallback():
    shop = {"name": "Test", "myshopify_domain": "test.myshopify.com", "currency": "EUR"}
    data = build_organization_jsonld(shop)
    assert data["url"] == "https://test.myshopify.com"
