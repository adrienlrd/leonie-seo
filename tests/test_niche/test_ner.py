"""Tests for product entity extraction (NER)."""

from __future__ import annotations

from app.niche.ner import ProductEntities, enrich_product, extract_entities

# ---------------------------------------------------------------------------
# extract_entities — materials
# ---------------------------------------------------------------------------


def test_extracts_cuir():
    e = extract_entities("Harnais en cuir véritable pour chien")
    assert "cuir" in e.materials


def test_extracts_nylon():
    e = extract_entities("Laisse nylon ultra-résistante")
    assert "nylon" in e.materials


def test_extracts_metal_variants():
    e = extract_entities("Boucle en acier inoxydable inox")
    assert "metal" in e.materials


def test_extracts_multiple_materials():
    e = extract_entities("Harnais cuir et nylon avec boucle métal")
    assert "cuir" in e.materials
    assert "nylon" in e.materials
    assert "metal" in e.materials


# ---------------------------------------------------------------------------
# extract_entities — certifications
# ---------------------------------------------------------------------------


def test_extracts_oeko_tex():
    e = extract_entities("Tissu certifié OEKO-TEX Standard 100")
    assert "OEKO-TEX" in e.certifications


def test_extracts_bio():
    e = extract_entities("Coton bio sans produits chimiques")
    assert "bio" in e.certifications


def test_extracts_vegan():
    e = extract_entities("Matière 100% vegan, aucun produit animal")
    assert "vegan" in e.certifications


def test_extracts_fait_main():
    e = extract_entities("Fabriqué artisanalement dans notre atelier")
    assert "fait main" in e.certifications


def test_extracts_recycle():
    e = extract_entities("Confectionné à partir de plastique recyclé")
    assert "recyclé" in e.certifications


# ---------------------------------------------------------------------------
# extract_entities — origins
# ---------------------------------------------------------------------------


def test_extracts_fabrique_en_france():
    e = extract_entities("Fabriqué en France dans notre atelier parisien")
    assert "fabriqué en France" in e.origins


def test_extracts_made_in_france():
    e = extract_entities("Made in France, shipped worldwide")
    assert "fabriqué en France" in e.origins


def test_extracts_europe():
    e = extract_entities("Matières premières d'origine européenne")
    assert "Europe" in e.origins


def test_france_not_matched_by_fabrique_en_france_pattern_exclusively():
    # "France" alone should be captured by the France entry, not fabrique_en_france
    e = extract_entities("Livraison gratuite en France")
    assert "France" in e.origins


# ---------------------------------------------------------------------------
# extract_entities — targets
# ---------------------------------------------------------------------------


def test_extracts_chien():
    e = extract_entities("Harnais pour chien de grande race")
    assert "chien" in e.targets


def test_extracts_chat():
    e = extract_entities("Fontaine à eau pour chat et chaton")
    assert "chat" in e.targets
    assert "chaton" in e.targets


def test_extracts_chiot():
    e = extract_entities("Collier doux adapté aux chiots")
    assert "chiot" in e.targets


def test_extracts_petit_chien():
    e = extract_entities("Taille petite race, parfait petit chien")
    assert "petit chien" in e.targets


def test_target_priority_chiot_before_chien():
    # "chiot" is more specific — both should be found independently
    e = extract_entities("Harnais pour chiot et chien adulte")
    assert "chiot" in e.targets
    assert "chien" in e.targets


# ---------------------------------------------------------------------------
# extract_entities — properties
# ---------------------------------------------------------------------------


def test_extracts_impermeable():
    e = extract_entities("Manteau imperméable pour chien, waterproof")
    assert "imperméable" in e.properties


def test_extracts_reglable():
    e = extract_entities("Harnais réglable, taille ajustable S/M/L")
    assert "réglable" in e.properties


def test_extracts_lavable():
    e = extract_entities("Coussin lavable en machine, séchage rapide")
    assert "lavable" in e.properties


def test_extracts_reflechissant():
    e = extract_entities("Bande réfléchissante pour haute visibilité")
    assert "réfléchissant" in e.properties


# ---------------------------------------------------------------------------
# extract_entities — HTML stripping
# ---------------------------------------------------------------------------


def test_strips_html_tags():
    e = extract_entities("<p>Harnais en <strong>cuir</strong> pour <em>chien</em></p>")
    assert "cuir" in e.materials
    assert "chien" in e.targets


def test_empty_text_returns_empty_entities():
    e = extract_entities("")
    assert e.is_empty


# ---------------------------------------------------------------------------
# ProductEntities.all_keywords
# ---------------------------------------------------------------------------


def test_all_keywords_deduplicates():
    e = ProductEntities(
        materials=["cuir"],
        certifications=["bio"],
        origins=["France"],
        targets=["chien"],
        properties=["réglable"],
    )
    kws = e.all_keywords
    assert len(kws) == len(set(kws))


def test_all_keywords_certifications_first():
    e = ProductEntities(
        materials=["nylon"],
        certifications=["OEKO-TEX"],
        origins=["France"],
        targets=[],
        properties=[],
    )
    kws = e.all_keywords
    assert kws.index("OEKO-TEX") < kws.index("nylon")


def test_is_empty_true_when_no_entities():
    e = ProductEntities()
    assert e.is_empty is True


def test_is_empty_false_when_has_entities():
    e = ProductEntities(materials=["cuir"])
    assert e.is_empty is False


# ---------------------------------------------------------------------------
# enrich_product
# ---------------------------------------------------------------------------


def test_enrich_product_adds_entities_key():
    product = {
        "id": "gid://shopify/Product/1",
        "title": "Harnais cuir pour chien",
        "body_html": "<p>Fabriqué en France, imperméable</p>",
        "product_type": "harnais",
        "tags": ["bio", "fait main"],
    }
    enriched = enrich_product(product)
    assert "_entities" in enriched
    assert "cuir" in enriched["_entities"].materials
    assert "chien" in enriched["_entities"].targets
    assert "fabriqué en France" in enriched["_entities"].origins
    assert "imperméable" in enriched["_entities"].properties


def test_enrich_product_does_not_mutate_original():
    product = {"id": "1", "title": "Harnais", "body_html": "", "product_type": "", "tags": []}
    original_keys = set(product.keys())
    enrich_product(product)
    assert set(product.keys()) == original_keys


def test_enrich_product_handles_string_tags():
    product = {
        "title": "Collier cuir",
        "body_html": "",
        "product_type": "",
        "tags": "cuir,artisanal",
    }
    enriched = enrich_product(product)
    assert "cuir" in enriched["_entities"].materials


def test_enrich_product_merges_all_fields():
    product = {
        "title": "Harnais",
        "body_html": "<p>en nylon</p>",
        "product_type": "accessoire chien",
        "tags": ["réglable"],
    }
    enriched = enrich_product(product)
    assert "nylon" in enriched["_entities"].materials
    assert "chien" in enriched["_entities"].targets
    assert "réglable" in enriched["_entities"].properties
