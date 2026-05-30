"""Tests for FR keyword normalization, lemmatization, and semantic clustering."""

from __future__ import annotations

from app.market_analysis import keyword_normalization as kn


class TestStripAccents:
    def test_strips_french_accents_when_present(self):
        assert kn.strip_accents("café") == "cafe"
        assert kn.strip_accents("éléphant") == "elephant"
        assert kn.strip_accents("naïve") == "naive"
        assert kn.strip_accents("où") == "ou"
        assert kn.strip_accents("français") == "francais"

    def test_returns_input_when_no_accents(self):
        assert kn.strip_accents("dog") == "dog"
        assert kn.strip_accents("") == ""


class TestLemmatizeFr:
    def test_strips_plural_s_when_long_enough(self):
        assert kn.lemmatize_fr("chiens") == "chien"
        # Aggressive feminine-plural strip lands plural and singular on the same stem.
        assert kn.lemmatize_fr("croquettes") == kn.lemmatize_fr("croquette")

    def test_strips_plural_x_when_long_enough(self):
        assert kn.lemmatize_fr("chevaux") == "cheval" or kn.lemmatize_fr("chevaux") == "chevau"
        assert kn.lemmatize_fr("animaux") in {"animal", "animau"}

    def test_keeps_short_words_intact(self):
        assert kn.lemmatize_fr("os") == "os"
        assert kn.lemmatize_fr("le") == "le"

    def test_strips_common_verb_endings(self):
        assert kn.lemmatize_fr("nourrir") == "nourr"
        assert kn.lemmatize_fr("dressage") == "dress"


class TestNormalizeToken:
    def test_combines_lowercase_accent_strip_and_lemma(self):
        assert kn.normalize_token("Croquettes") == "croquett"
        assert kn.normalize_token("Pâtées") in {"patee", "pate", "pat"}

    def test_returns_empty_for_blank(self):
        assert kn.normalize_token("") == ""
        assert kn.normalize_token("   ") == ""


class TestTokenizeNormalized:
    def test_drops_stop_words_and_short_tokens(self):
        tokens = kn.tokenize_normalized("le harnais pour chien")
        assert "le" not in tokens
        assert "pour" not in tokens
        assert any(t.startswith("harna") for t in tokens)
        assert any(t.startswith("chien") for t in tokens)

    def test_accent_variants_normalize_identically(self):
        a = kn.tokenize_normalized("café équitable")
        b = kn.tokenize_normalized("cafe equitable")
        assert a == b


class TestJaccardSimilarity:
    def test_identical_sets_score_one(self):
        assert kn.jaccard_similarity({"a", "b"}, {"a", "b"}) == 1.0

    def test_disjoint_sets_score_zero(self):
        assert kn.jaccard_similarity({"a"}, {"b"}) == 0.0

    def test_partial_overlap_returns_ratio(self):
        # {a,b} ∩ {b,c} = {b}, ∪ = {a,b,c} → 1/3
        assert kn.jaccard_similarity({"a", "b"}, {"b", "c"}) == 1 / 3

    def test_empty_sets_score_zero(self):
        assert kn.jaccard_similarity(set(), set()) == 0.0


class TestBuildClusters:
    def _kw(self, query: str, volume: int = 100, source: str = "dataforseo") -> dict:
        return {"query": query, "search_volume": volume, "data_source": source}

    def test_groups_plural_singular_variants_in_one_cluster(self):
        keywords = [
            self._kw("croquette chien", volume=500),
            self._kw("croquettes chien", volume=800),
            self._kw("harnais chien", volume=300),
        ]
        clusters = kn.build_clusters(keywords, threshold=0.5)
        assert len(clusters) == 2
        croquette_cluster = next(c for c in clusters if "croquette" in c["head_keyword"])
        assert {m["query"] for m in croquette_cluster["members"]} == {
            "croquette chien",
            "croquettes chien",
        }

    def test_groups_accent_variants(self):
        keywords = [
            self._kw("pâtée chien", volume=200),
            self._kw("patee chien", volume=300),
        ]
        clusters = kn.build_clusters(keywords, threshold=0.5)
        assert len(clusters) == 1
        assert clusters[0]["head_keyword"] == "patee chien"

    def test_head_keyword_is_highest_volume_member(self):
        keywords = [
            self._kw("collier chien", volume=200),
            self._kw("collier pour chien", volume=900),
        ]
        clusters = kn.build_clusters(keywords, threshold=0.5)
        assert len(clusters) == 1
        assert clusters[0]["head_keyword"] == "collier pour chien"

    def test_separates_disjoint_topics(self):
        keywords = [
            self._kw("harnais chien"),
            self._kw("litière chat"),
            self._kw("jouet oiseau"),
        ]
        clusters = kn.build_clusters(keywords, threshold=0.5)
        assert len(clusters) == 3

    def test_each_cluster_carries_id_and_member_count(self):
        keywords = [self._kw("a chien"), self._kw("b chat")]
        clusters = kn.build_clusters(keywords)
        assert all("cluster_id" in c for c in clusters)
        assert all(len(c["members"]) >= 1 for c in clusters)
        ids = [c["cluster_id"] for c in clusters]
        assert len(ids) == len(set(ids))

    def test_handles_empty_input(self):
        assert kn.build_clusters([]) == []

    def test_skips_keywords_with_blank_query(self):
        clusters = kn.build_clusters([{"query": "", "search_volume": 0}])
        assert clusters == []


class TestSemanticCoverage:
    def test_covers_when_lemma_matches(self):
        # "croquettes" in text covers "croquette" in query
        assert kn.is_semantically_covered("croquette chien", "Nos croquettes pour chiens sont…")

    def test_covers_when_accents_differ(self):
        assert kn.is_semantically_covered("pâtée naturelle", "Patee naturelle bio")

    def test_does_not_cover_when_topic_differs(self):
        assert not kn.is_semantically_covered("croquette chien", "Litière pour chat parfumée")

    def test_threshold_partial_coverage(self):
        # 1 of 2 query tokens present → below default 0.7 threshold
        assert not kn.is_semantically_covered("harnais cuir chien", "harnais réglable")

    def test_full_coverage_above_threshold(self):
        assert kn.is_semantically_covered(
            "harnais chien", "Notre harnais pour chien est ajustable"
        )

    def test_empty_query_returns_false(self):
        assert not kn.is_semantically_covered("", "anything")
