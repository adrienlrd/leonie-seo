"""Tests for AI Search readiness scoring."""

from __future__ import annotations

from app.geo.readiness import score_catalog_readiness, score_product_readiness


def test_score_product_readiness_returns_components_and_recommendations() -> None:
    product = {
        "id": "gid://shopify/Product/1",
        "title": "Harnais chien nylon réglable",
        "handle": "harnais-chien",
        "status": "ACTIVE",
        "seo": {
            "title": "Harnais chien nylon réglable pour promenade",
            "description": "Harnais chien réglable, lavable et confortable pour promenade quotidienne.",
        },
        "description": (
            "Harnais en nylon réglable, lavable et confortable. Fabriqué en France, "
            "compatible petit chien et grand chien. Garantie 30 jours avec livraison rapide."
        ),
        "images": {"edges": [{"node": {"url": "https://example.com/img.jpg"}}]},
        "variants": {"edges": [{"node": {"price": "49.90", "sku": "HAR-001"}}]},
    }

    result = score_product_readiness(product)

    assert 0 <= result["readiness_score"] <= 100
    assert result["components"]["facts"]["score"] > 0
    assert result["components"]["schema"]["score"] > 0
    assert result["level"] in {"excellent", "bon", "partiel", "faible"}
    assert isinstance(result["recommendations"], list)
    assert isinstance(result["reasons"], list)
    assert isinstance(result["recommended_actions"], list)
    assert isinstance(result["niche_alerts"], list)


def test_score_product_readiness_weak_product_scores_lower() -> None:
    weak = {
        "id": "gid://shopify/Product/1",
        "title": "Bol",
        "handle": "bol",
        "description": "",
        "seo": {"title": "", "description": ""},
    }
    strong = {
        "id": "gid://shopify/Product/2",
        "title": "Fontaine chat céramique",
        "handle": "fontaine-chat",
        "status": "ACTIVE",
        "seo": {
            "title": "Fontaine chat céramique silencieuse et lavable",
            "description": "Fontaine pour chat en céramique lavable, garantie et adaptée au quotidien.",
        },
        "description": (
            "Fontaine chat en céramique lavable, silencieuse et compatible avec un usage quotidien. "
            "Dimensions 20 cm, garantie 30 jours, livraison rapide et retours possibles."
        ),
        "images": {"edges": [{"node": {"url": "https://example.com/img.jpg"}}]},
        "variants": {"edges": [{"node": {"price": "69.90", "sku": "FON-001"}}]},
    }

    assert score_product_readiness(weak)["readiness_score"] < score_product_readiness(strong)["readiness_score"]


def test_score_catalog_readiness_sorts_lowest_first() -> None:
    products = [
        {
            "id": "gid://shopify/Product/1",
            "title": "Produit fort",
            "handle": "produit-fort",
            "description": "Produit en coton lavable, dimensions 40 cm, garantie 30 jours.",
            "images": {"edges": [{"node": {"url": "https://example.com/img.jpg"}}]},
            "variants": {"edges": [{"node": {"price": "39.90"}}]},
        },
        {
            "id": "gid://shopify/Product/2",
            "title": "Produit faible",
            "handle": "produit-faible",
            "description": "",
        },
    ]

    result = score_catalog_readiness(products)

    assert result["total"] == 2
    assert result["products"][0]["handle"] == "produit-faible"
    assert "avg_readiness_score" in result["summary"]
    assert "global_score" in result
    assert "global_level" in result
    assert result["global_level"] in {"excellent", "bon", "partiel", "faible"}


def test_score_catalog_readiness_filters_inactive_products_when_scope_is_active() -> None:
    products = [
        {
            "id": "gid://shopify/Product/1",
            "title": "Produit actif",
            "handle": "produit-actif",
            "status": "ACTIVE",
            "onlineStoreUrl": "https://example.com/products/produit-actif",
            "description": "Produit en coton lavable, dimensions 40 cm, garantie 30 jours.",
        },
        {
            "id": "gid://shopify/Product/2",
            "title": "Produit brouillon",
            "handle": "produit-brouillon",
            "status": "DRAFT",
            "onlineStoreUrl": None,
            "description": "",
        },
    ]

    result = score_catalog_readiness(products)

    assert result["total"] == 1
    assert result["scope"]["counts"]["draft"] == 1
    assert result["products"][0]["handle"] == "produit-actif"


def test_score_product_readiness_niche_forbidden_promise_reduces_trust_and_adds_alert() -> None:
    # Product has warranty + origin trust signals so base trust score > 0, letting the malus show
    product = {
        "id": "gid://shopify/Product/1",
        "title": "Complément alimentaire chien",
        "handle": "complement-chien",
        "status": "ACTIVE",
        "description": (
            "Ce produit guérit les maladies de votre chien en 7 jours. "
            "Fabriqué en France, garantie 30 jours, livraison express, retours acceptés."
        ),
    }
    niche_hypothesis = {
        "status": "validated_by_merchant",
        "forbidden_promises": [{"promise": "guérit les maladies", "reason": "health_claim"}],
        "brand_voice": {"do_not_say": []},
        "conversational_intents": [],
    }

    result_without = score_product_readiness(product)
    result_with = score_product_readiness(product, niche_hypothesis=niche_hypothesis)

    assert any(a["type"] == "forbidden_promise" for a in result_with["niche_alerts"])
    # Trust malus applies when base trust > 0; readiness score must not increase
    assert result_with["readiness_score"] <= result_without["readiness_score"]
    if result_without["components"]["trust"]["score"] > 0:
        assert result_with["components"]["trust"]["score"] < result_without["components"]["trust"]["score"]


def test_score_product_readiness_niche_brand_voice_adds_alert_no_score_change() -> None:
    product = {
        "id": "gid://shopify/Product/1",
        "title": "Croquettes chien",
        "handle": "croquettes-chien",
        "status": "ACTIVE",
        "description": "Les meilleures croquettes pas cher du marché.",
    }
    niche_hypothesis = {
        "status": "validated_by_merchant",
        "forbidden_promises": [],
        "brand_voice": {"do_not_say": ["pas cher"]},
        "conversational_intents": [],
    }

    result_without = score_product_readiness(product)
    result_with = score_product_readiness(product, niche_hypothesis=niche_hypothesis)

    assert any(a["type"] == "brand_voice_violation" for a in result_with["niche_alerts"])
    assert result_with["components"]["trust"]["score"] == result_without["components"]["trust"]["score"]


def test_score_product_readiness_niche_not_validated_has_no_effect() -> None:
    product = {
        "id": "gid://shopify/Product/1",
        "title": "Lit chien",
        "handle": "lit-chien",
        "description": "Lit douillet pour chien.",
    }
    niche_hypothesis = {
        "status": "needs_review",
        "forbidden_promises": [{"promise": "lit", "reason": "test"}],
        "brand_voice": {"do_not_say": ["chien"]},
        "conversational_intents": [],
    }

    result = score_product_readiness(product, niche_hypothesis=niche_hypothesis)

    assert result["niche_alerts"] == []


def test_score_product_readiness_crawl_page_404_reduces_seo_score() -> None:
    product = {
        "id": "gid://shopify/Product/1",
        "title": "Collier chien",
        "handle": "collier-chien",
        "status": "ACTIVE",
        "seo": {"title": "Collier chien solide et réglable", "description": "Collier chien en cuir réglable et solide."},
        "description": "Collier en cuir naturel, réglable, dimensions variées.",
    }
    crawl_findings = [
        {"url": "https://shop.myshopify.com/products/collier-chien", "issue_type": "page_404", "severity": "critical", "detail": "404"},
    ]

    result_clean = score_product_readiness(product)
    result_404 = score_product_readiness(product, crawl_findings=crawl_findings)

    assert result_404["components"]["seo"]["score"] < result_clean["components"]["seo"]["score"]
    assert result_404["readiness_score"] < result_clean["readiness_score"]


def test_score_product_readiness_crawl_no_match_has_no_effect() -> None:
    product = {
        "id": "gid://shopify/Product/1",
        "title": "Laisse chien",
        "handle": "laisse-chien",
        "description": "Laisse en nylon.",
    }
    crawl_findings = [
        {"url": "https://shop.myshopify.com/products/collier-chat", "issue_type": "page_404", "severity": "critical", "detail": "404"},
    ]

    result_clean = score_product_readiness(product)
    result_crawl = score_product_readiness(product, crawl_findings=crawl_findings)

    assert result_crawl["components"]["seo"]["score"] == result_clean["components"]["seo"]["score"]


def test_score_catalog_readiness_exposes_crawl_health() -> None:
    products = [
        {
            "id": "gid://shopify/Product/1",
            "title": "Jouet chien",
            "handle": "jouet-chien",
            "status": "ACTIVE",
            "onlineStoreUrl": "https://example.com/products/jouet-chien",
            "description": "Jouet pour chien.",
        },
    ]
    crawl_findings = [
        {"url": "https://example.com/products/jouet-chien", "issue_type": "page_404", "severity": "critical", "detail": "404"},
        {"url": "https://example.com/collections/chiens", "issue_type": "redirect_chain", "severity": "high", "detail": "chain"},
    ]

    result = score_catalog_readiness(products, crawl_findings=crawl_findings)

    assert result["crawl_health"]["available"] is True
    assert result["crawl_health"]["critical"] == 1
    assert result["crawl_health"]["high"] == 1


def test_score_catalog_readiness_crawl_health_unavailable_when_no_findings() -> None:
    products = [
        {
            "id": "gid://shopify/Product/1",
            "title": "Jouet chien",
            "handle": "jouet-chien",
            "status": "ACTIVE",
            "onlineStoreUrl": "https://example.com/products/jouet-chien",
            "description": "Jouet pour chien.",
        },
    ]

    result = score_catalog_readiness(products)

    assert result["crawl_health"]["available"] is False
