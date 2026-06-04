"""Tests for competitor crawl feature extraction."""

from __future__ import annotations

from app.market_analysis.competitor_crawl.extractor import extract_competitor_features


def _html() -> str:
    return """
    <html>
      <head>
        <title>Fontaine chat complète</title>
        <meta name="description" content="Guide complet pour choisir une fontaine chat.">
        <link rel="canonical" href="https://competitor.fr/products/fontaine">
        <script type="application/ld+json">
          {
            "@context": "https://schema.org",
            "@type": "Product",
            "name": "Fontaine",
            "offers": {"@type": "Offer", "price": "29.90"}
          }
        </script>
        <script type="application/ld+json">
          {
            "@context": "https://schema.org",
            "@type": "FAQPage",
            "mainEntity": [
              {"@type": "Question", "name": "Comment nettoyer ?", "acceptedAnswer": {"@type": "Answer", "text": "Avec de l'eau."}}
            ]
          }
        </script>
        <script type="application/ld+json">{"@type": "BreadcrumbList"}</script>
      </head>
      <body>
        <h1>Fontaine chat</h1>
        <p>Une fontaine chat est un accessoire qui aide à organiser un point d'eau dédié dans la maison avec un format simple à comprendre pour les clients.</p>
        <h2>Comment choisir une fontaine chat ?</h2>
        <p>Vérifiez le volume, l'entretien, le bruit, le filtre et la place disponible avant de choisir le modèle adapté au besoin de votre animal.</p>
        <h2>Guide d'achat</h2>
        <h3>Avantages</h3>
        <ul><li>Volume</li><li>Entretien</li></ul>
        <table><tr><th>Critère</th><th>Valeur</th></tr><tr><td>Dimension</td><td>20 cm</td></tr></table>
        <img src="//cdn.shopify.com/a.jpg">
        <img src="/b.jpg" alt="Fontaine chat">
        <a href="/collections/chats">Collection</a>
        <a href="https://external.example/a">External</a>
        <div class="shopify-section">Shopify</div>
      </body>
    </html>
    """


def test_detects_faq_visible_and_schema_when_html_contains_faq_patterns() -> None:
    features = extract_competitor_features(_html(), url="https://competitor.fr/products/fontaine")

    assert features["has_faq_block"] is True
    assert features["faq_question_count"] >= 1
    assert features["has_faq_schema"] is True


def test_detects_product_and_breadcrumb_schema_when_jsonld_contains_types() -> None:
    features = extract_competitor_features(_html(), url="https://competitor.fr/products/fontaine")

    assert features["has_product_schema"] is True
    assert features["has_offer_schema"] is True
    assert features["has_breadcrumb_schema"] is True
    assert features["jsonld_count"] == 3


def test_counts_headings_links_and_words_when_html_has_content() -> None:
    features = extract_competitor_features(_html(), url="https://competitor.fr/products/fontaine")

    assert features["h1_count"] == 1
    assert features["h2_count"] == 2
    assert features["h3_count"] == 1
    assert features["internal_link_count"] == 1
    assert features["external_link_count"] == 1
    assert features["word_count"] > 40


def test_scores_are_bounded_when_content_is_extracted() -> None:
    features = extract_competitor_features(_html(), url="https://competitor.fr/products/fontaine")

    assert 0 <= features["answerability_score"] <= 100
    assert 0 <= features["ai_readability_score"] <= 100
    assert 0 <= features["schema_completeness_score"] <= 100


def test_detects_shopify_when_cdn_or_shopify_marker_exists() -> None:
    features = extract_competitor_features(_html(), url="https://competitor.fr/products/fontaine")

    assert features["is_shopify"] is True
    assert features["shopify_cdn_detected"] is True
    assert features["detected_platform"] == "shopify"
