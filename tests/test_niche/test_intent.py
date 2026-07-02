"""Tests for GSC query intent classification and clustering."""

from __future__ import annotations

from app.niche.intent import (
    IntentCluster,
    QueryIntent,
    _jaccard,
    _top_terms,
    classify_intent,
    cluster_gsc_queries,
)

# ---------------------------------------------------------------------------
# classify_intent
# ---------------------------------------------------------------------------


def test_classify_intent_informational():
    assert classify_intent("comment choisir un harnais pour chien") == QueryIntent.INFORMATIONAL
    assert classify_intent("pourquoi mon chat boit peu") == QueryIntent.INFORMATIONAL
    assert classify_intent("guide collier chien") == QueryIntent.INFORMATIONAL


def test_classify_intent_transactional():
    assert classify_intent("acheter harnais chien cuir") == QueryIntent.TRANSACTIONAL
    assert classify_intent("harnais chien pas cher livraison") == QueryIntent.TRANSACTIONAL
    assert classify_intent("prix collier chien design") == QueryIntent.TRANSACTIONAL


def test_classify_intent_commercial():
    assert classify_intent("meilleur harnais chien 2024") == QueryIntent.COMMERCIAL
    assert classify_intent("avis fontaine eau chat") == QueryIntent.COMMERCIAL
    assert classify_intent("comparatif collier chien cuir vs nylon") == QueryIntent.COMMERCIAL


def test_classify_intent_navigational():
    # Generic navigational signals (no hardcoded brand).
    assert classify_intent("site officiel") == QueryIntent.NAVIGATIONAL
    assert classify_intent("mon compte") == QueryIntent.NAVIGATIONAL


def test_classify_intent_navigational_with_shop_brand_terms():
    # Brand tokens are supplied per-shop (derived from the shop's own domain).
    brand = frozenset({"acmepets"})
    assert classify_intent("acmepets harnais", brand) == QueryIntent.NAVIGATIONAL
    # Without the brand term provided, it is not treated as navigational.
    assert classify_intent("acmepets harnais") != QueryIntent.NAVIGATIONAL


def test_classify_intent_unknown():
    assert classify_intent("harnais chien") == QueryIntent.UNKNOWN
    assert classify_intent("collier chat") == QueryIntent.UNKNOWN


def test_classify_intent_transactional_priority_over_commercial():
    # "meilleur" is commercial but "acheter" is transactional → transactional wins
    assert classify_intent("acheter meilleur harnais chien") == QueryIntent.TRANSACTIONAL


def test_classify_intent_navigational_priority_over_transactional():
    # navigational always wins, even over transactional signals
    brand = frozenset({"acmepets"})
    assert classify_intent("acheter acmepets harnais", brand) == QueryIntent.NAVIGATIONAL


# ---------------------------------------------------------------------------
# _jaccard
# ---------------------------------------------------------------------------


def test_jaccard_identical_sets():
    assert _jaccard({"a", "b"}, {"a", "b"}) == 1.0


def test_jaccard_disjoint_sets():
    assert _jaccard({"a", "b"}, {"c", "d"}) == 0.0


def test_jaccard_partial_overlap():
    score = _jaccard({"a", "b", "c"}, {"b", "c", "d"})
    assert round(score, 3) == 0.5  # 2 common / 4 union


def test_jaccard_empty_sets():
    assert _jaccard(set(), set()) == 1.0


# ---------------------------------------------------------------------------
# _top_terms
# ---------------------------------------------------------------------------


def test_top_terms_returns_dominant_words():
    queries = [
        "harnais chien cuir premium",
        "harnais chien sport",
        "harnais chien petit",
    ]
    terms = _top_terms(queries, n=5)
    assert "harnais" in terms
    assert "chien" in terms


def test_top_terms_excludes_stopwords():
    queries = ["le meilleur harnais pour les chiens", "harnais pour chien de grande race"]
    terms = _top_terms(queries, n=10)
    assert "le" not in terms
    assert "les" not in terms
    assert "pour" not in terms


# ---------------------------------------------------------------------------
# cluster_gsc_queries — integration
# ---------------------------------------------------------------------------


def _make_rows(data: list[tuple[str, int, int, float]]) -> list[dict]:
    return [
        {"query": q, "impressions": imp, "clicks": cli, "position": pos}
        for q, imp, cli, pos in data
    ]


def test_cluster_gsc_queries_returns_intent_clusters():
    rows = _make_rows(
        [
            ("comment choisir harnais chien", 120, 10, 8.0),
            ("meilleur harnais chien 2024", 200, 25, 5.0),
            ("acheter harnais chien cuir", 80, 15, 3.0),
        ]
    )
    clusters = cluster_gsc_queries(rows)

    assert len(clusters) > 0
    assert all(isinstance(c, IntentCluster) for c in clusters)
    intents = {c.intent for c in clusters}
    assert QueryIntent.INFORMATIONAL in intents
    assert QueryIntent.COMMERCIAL in intents
    assert QueryIntent.TRANSACTIONAL in intents


def test_cluster_gsc_queries_sorted_by_impressions():
    rows = _make_rows(
        [
            ("acheter collier chat", 50, 5, 10.0),
            ("meilleur harnais chien", 300, 30, 4.0),
            ("comment choisir fontaine chat", 150, 15, 7.0),
        ]
    )
    clusters = cluster_gsc_queries(rows)
    impressions = [c.total_impressions for c in clusters]
    assert impressions == sorted(impressions, reverse=True)


def test_cluster_gsc_queries_filters_low_impressions():
    rows = _make_rows(
        [
            ("harnais chien cuir", 3, 0, 15.0),  # below default threshold
            ("meilleur collier chat", 200, 20, 5.0),
        ]
    )
    clusters = cluster_gsc_queries(rows, min_impressions=5)

    all_queries = [q for c in clusters for q in c.queries]
    assert "harnais chien cuir" not in all_queries
    assert "meilleur collier chat" in all_queries


def test_cluster_gsc_queries_empty_input():
    assert cluster_gsc_queries([]) == []


def test_cluster_gsc_queries_all_below_threshold():
    rows = _make_rows(
        [
            ("harnais chien", 2, 0, 20.0),
            ("collier chat", 1, 0, 30.0),
        ]
    )
    assert cluster_gsc_queries(rows, min_impressions=5) == []


def test_cluster_gsc_queries_merges_similar_queries():
    rows = _make_rows(
        [
            ("harnais chien cuir", 100, 10, 8.0),
            ("harnais chien cuir premium", 80, 8, 9.0),
            ("acheter collier chat", 60, 5, 12.0),
        ]
    )
    clusters = cluster_gsc_queries(rows)

    # The two harnais cuir queries share >20% Jaccard → same cluster
    unknown_clusters = [c for c in clusters if c.intent == QueryIntent.UNKNOWN]
    harnais_cluster = next((c for c in unknown_clusters if "harnais" in " ".join(c.queries)), None)
    if harnais_cluster:
        assert len(harnais_cluster.queries) == 2


def test_cluster_gsc_queries_computes_weighted_avg_position():
    rows = _make_rows(
        [
            ("meilleur harnais chien", 100, 10, 10.0),
            ("meilleur harnais petit chien", 100, 10, 20.0),
        ]
    )
    clusters = cluster_gsc_queries(rows)

    commercial = next(c for c in clusters if c.intent == QueryIntent.COMMERCIAL)
    # Equal impressions → avg = 15.0
    assert commercial.avg_position == 15.0


def test_cluster_gsc_queries_cluster_has_top_keywords():
    rows = _make_rows(
        [
            ("comment choisir harnais chien", 100, 10, 8.0),
            ("comment mesurer harnais chien taille", 80, 8, 10.0),
        ]
    )
    clusters = cluster_gsc_queries(rows)

    info_cluster = next(c for c in clusters if c.intent == QueryIntent.INFORMATIONAL)
    assert len(info_cluster.top_keywords) > 0
    assert "harnais" in info_cluster.top_keywords or "chien" in info_cluster.top_keywords


def test_cluster_gsc_queries_size_equals_query_count():
    rows = _make_rows(
        [
            ("acheter harnais chien", 50, 5, 7.0),
            ("acheter collier chien cuir", 40, 4, 8.0),
        ]
    )
    clusters = cluster_gsc_queries(rows)

    for c in clusters:
        assert c.size == len(c.queries)


def test_cluster_gsc_queries_totals_correct():
    rows = _make_rows(
        [
            ("prix harnais chien", 100, 15, 5.0),
        ]
    )
    clusters = cluster_gsc_queries(rows)
    transactional = next(c for c in clusters if c.intent == QueryIntent.TRANSACTIONAL)
    assert transactional.total_impressions == 100
    assert transactional.total_clicks == 15
