"""Tests for schema.org JSON-LD generation from confirmed product facts.

JSON-LD is built deterministically from data we know is true (Shopify snapshot
fields + merchant-confirmed facts). The LLM never produces structured data —
schema.org fields are too risky to hallucinate (rich-result penalties).
"""

from __future__ import annotations

from app.market_analysis import schema_builder as sb


def _product(**overrides):
    base = {
        "id": "gid://shopify/Product/42",
        "title": "Croquettes chien sans céréales",
        "handle": "croquettes-chien-sans-cereales",
        "body_html": "<p>Aliment complet pour chien adulte.</p>",
        "variants": [{"price": "39.90", "inventory_quantity": 8}],
        "images": [{"src": "https://cdn.shopify.com/img.jpg"}],
        "vendor": "Léonie",
    }
    base.update(overrides)
    return base


def _fact(key: str, value: str, source: str = "merchant_confirmation") -> dict:
    return {"key": key, "label": key.title(), "value": value, "source": source, "confidence": "confirmed"}


class TestBuildProductSchema:
    def test_minimal_schema_when_only_snapshot_data(self):
        result = sb.build_product_schema(
            product=_product(),
            confirmed_facts=[],
            shop="boutique.myshopify.com",
            meta_description="Croquettes chien premium.",
        )
        assert result["@context"] == "https://schema.org"
        assert result["@type"] == "Product"
        assert result["name"] == "Croquettes chien sans céréales"
        assert result["description"] == "Croquettes chien premium."
        assert result["url"].endswith("/products/croquettes-chien-sans-cereales")
        assert result["image"] == ["https://cdn.shopify.com/img.jpg"]
        assert result["brand"]["@type"] == "Brand"
        assert result["brand"]["name"] == "Léonie"

    def test_offers_include_price_and_availability_from_first_variant(self):
        result = sb.build_product_schema(
            product=_product(),
            confirmed_facts=[],
            shop="boutique.myshopify.com",
            meta_description="",
        )
        offers = result["offers"]
        assert offers["@type"] == "Offer"
        assert offers["price"] == "39.90"
        assert offers["priceCurrency"] == "EUR"
        assert offers["availability"] == "https://schema.org/InStock"

    def test_offers_out_of_stock_when_quantity_zero(self):
        result = sb.build_product_schema(
            product=_product(variants=[{"price": "39.90", "inventory_quantity": 0}]),
            confirmed_facts=[],
            shop="boutique.myshopify.com",
            meta_description="",
        )
        assert result["offers"]["availability"] == "https://schema.org/OutOfStock"

    def test_material_field_added_when_confirmed(self):
        result = sb.build_product_schema(
            product=_product(),
            confirmed_facts=[_fact("materials", "Cuir véritable tannage végétal")],
            shop="boutique.myshopify.com",
            meta_description="",
        )
        assert result["material"] == "Cuir véritable tannage végétal"

    def test_country_of_origin_added_when_confirmed(self):
        result = sb.build_product_schema(
            product=_product(),
            confirmed_facts=[_fact("origins", "France")],
            shop="boutique.myshopify.com",
            meta_description="",
        )
        assert result["countryOfOrigin"] == "France"

    def test_material_field_omitted_when_not_confirmed(self):
        result = sb.build_product_schema(
            product=_product(),
            confirmed_facts=[],
            shop="boutique.myshopify.com",
            meta_description="",
        )
        assert "material" not in result

    def test_does_not_invent_brand_when_vendor_missing(self):
        result = sb.build_product_schema(
            product=_product(vendor=""),
            confirmed_facts=[],
            shop="boutique.myshopify.com",
            meta_description="",
        )
        assert "brand" not in result


class TestBuildFaqSchema:
    def test_empty_faq_returns_none(self):
        assert sb.build_faq_schema([]) is None

    def test_faq_with_two_questions_produces_faq_page(self):
        result = sb.build_faq_schema(
            [
                {"q": "Comment nourrir mon chien ?", "a": "Deux repas par jour."},
                {"q": "Quelle quantité ?", "a": "Selon le poids du chien."},
            ]
        )
        assert result["@context"] == "https://schema.org"
        assert result["@type"] == "FAQPage"
        assert len(result["mainEntity"]) == 2
        first = result["mainEntity"][0]
        assert first["@type"] == "Question"
        assert first["name"] == "Comment nourrir mon chien ?"
        assert first["acceptedAnswer"]["@type"] == "Answer"
        assert first["acceptedAnswer"]["text"] == "Deux repas par jour."

    def test_skips_entries_with_blank_question_or_answer(self):
        result = sb.build_faq_schema(
            [
                {"q": "Valid ?", "a": "Yes."},
                {"q": "", "a": "Answer without question."},
                {"q": "Question without answer ?", "a": ""},
            ]
        )
        assert len(result["mainEntity"]) == 1


class TestBuildBreadcrumbSchema:
    def test_breadcrumb_uses_collection_and_product_title(self):
        result = sb.build_breadcrumb_schema(
            product=_product(),
            shop="boutique.myshopify.com",
            collection_handle="alimentation-chien",
            collection_title="Alimentation chien",
        )
        items = result["itemListElement"]
        assert len(items) == 3
        assert items[0]["position"] == 1
        assert items[0]["name"] in {"Accueil", "Home"}
        assert items[1]["name"] == "Alimentation chien"
        assert items[1]["item"].endswith("/collections/alimentation-chien")
        assert items[2]["name"] == "Croquettes chien sans céréales"
        assert items[2]["item"].endswith("/products/croquettes-chien-sans-cereales")

    def test_breadcrumb_without_collection_returns_home_plus_product(self):
        result = sb.build_breadcrumb_schema(
            product=_product(),
            shop="boutique.myshopify.com",
            collection_handle=None,
            collection_title=None,
        )
        items = result["itemListElement"]
        assert len(items) == 2
        assert items[1]["name"] == "Croquettes chien sans céréales"
