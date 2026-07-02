"""GSC query intent classification and semantic clustering."""

from __future__ import annotations

import math
import re
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from enum import StrEnum


class QueryIntent(StrEnum):
    INFORMATIONAL = "informational"
    TRANSACTIONAL = "transactional"
    NAVIGATIONAL = "navigational"
    COMMERCIAL = "commercial"
    UNKNOWN = "unknown"


@dataclass
class IntentCluster:
    """A group of GSC queries sharing the same intent and semantic theme.

    Attributes:
        name: Human-readable label (e.g. "transactional — harnais chien").
        intent: Detected user intent category.
        queries: GSC query strings in this cluster.
        total_impressions: Sum of impressions across all queries.
        total_clicks: Sum of clicks across all queries.
        avg_position: Impression-weighted average GSC position.
        top_keywords: Dominant terms across queries (TF-IDF ranked).
        size: Number of queries (== len(queries)).
    """

    name: str
    intent: QueryIntent
    queries: list[str]
    total_impressions: int
    total_clicks: int
    avg_position: float
    top_keywords: list[str]
    size: int = field(init=False)

    def __post_init__(self) -> None:
        self.size = len(self.queries)


# ---------------------------------------------------------------------------
# Intent signal words (French + common English e-commerce terms)
# ---------------------------------------------------------------------------

_INFORMATIONAL_SIGNALS = {
    "comment",
    "pourquoi",
    "quand",
    "combien",
    "qu",
    "quel",
    "quelle",
    "quels",
    "quelles",
    "est-ce",
    "difference",
    "guide",
    "conseils",
    "conseil",
    "tuto",
    "tutoriel",
    "apprendre",
    "comprendre",
    "definition",
    "signification",
    "avantage",
    "avantages",
    "inconvenient",
    "inconvenients",
    "risque",
    "danger",
    "sante",
    "bienfaits",
}

_TRANSACTIONAL_SIGNALS = {
    "acheter",
    "achat",
    "commander",
    "commande",
    "livraison",
    "prix",
    "tarif",
    "cout",
    "promo",
    "promotion",
    "solde",
    "soldes",
    "reduction",
    "remise",
    "discount",
    "pas cher",
    "moins cher",
    "bon marche",
    "offre",
    "devis",
    "boutique",
    "magasin",
    "shop",
    "store",
    "buy",
    "order",
    "panier",
}

_COMMERCIAL_SIGNALS = {
    "meilleur",
    "meilleurs",
    "meilleures",
    "top",
    "avis",
    "test",
    "comparatif",
    "comparaison",
    "comparer",
    "vs",
    "versus",
    "note",
    "notation",
    "evaluation",
    "recommande",
    "recommandation",
    "selection",
    "classement",
    "alternative",
    "alternatives",
    "choix",
    "choisir",
}

_NAVIGATIONAL_SIGNALS = {
    "site",
    "officiel",
    "connexion",
    "compte",
    "login",
    "mon compte",
    "contact",
}

# ---------------------------------------------------------------------------
# French stopwords for TF-IDF within clusters
# ---------------------------------------------------------------------------

_STOPWORDS = {
    "le",
    "la",
    "les",
    "un",
    "une",
    "des",
    "de",
    "du",
    "et",
    "en",
    "pour",
    "par",
    "sur",
    "avec",
    "dans",
    "à",
    "au",
    "aux",
    "se",
    "si",
    "ne",
    "ou",
    "mais",
    "donc",
    "or",
    "ni",
    "car",
    "que",
    "qui",
    "quoi",
    "dont",
    "où",
    "ce",
    "son",
    "sa",
    "ses",
    "mon",
    "ma",
    "mes",
    "ton",
    "ta",
    "tes",
    "nous",
    "vous",
    "ils",
    "elles",
    "je",
    "tu",
    "il",
    "elle",
    "on",
    "plus",
    "très",
    "bien",
    "aussi",
    "tout",
    "tous",
    "cette",
    "cet",
    "pas",
    "est",
}

_MIN_TERM_LEN = 3
_TOP_KEYWORDS_PER_CLUSTER = 8
# Minimum impressions to include a query in clustering
_MIN_IMPRESSIONS = 5
# Minimum Jaccard similarity to merge sub-clusters
_MERGE_THRESHOLD = 0.2


def _normalize(text: str) -> str:
    nfkd = unicodedata.normalize("NFKD", text.lower())
    ascii_text = "".join(c for c in nfkd if not unicodedata.combining(c))
    return re.sub(r"[^a-z\s]", " ", ascii_text)


def _tokenize(text: str) -> list[str]:
    tokens = _normalize(text).split()
    return [t for t in tokens if len(t) >= _MIN_TERM_LEN and t not in _STOPWORDS]


def _classify_intent(query: str, brand_terms: frozenset[str] = frozenset()) -> QueryIntent:
    """Classify a query into an intent category using rule-based signals.

    Priority: NAVIGATIONAL > TRANSACTIONAL > COMMERCIAL > INFORMATIONAL > UNKNOWN.

    Args:
        query: Raw GSC query string.
        brand_terms: Shop-specific brand tokens treated as navigational signals,
            derived generically from the shop's own domain (never hardcoded).

    Returns:
        QueryIntent enum value.
    """
    normalized = _normalize(query)
    words = set(normalized.split())

    if words & (_NAVIGATIONAL_SIGNALS | brand_terms):
        return QueryIntent.NAVIGATIONAL

    # Multi-word transactional signals (e.g. "pas cher", "bon marche")
    if any(sig in normalized for sig in ("pas cher", "bon marche", "moins cher")):
        return QueryIntent.TRANSACTIONAL
    if words & _TRANSACTIONAL_SIGNALS:
        return QueryIntent.TRANSACTIONAL

    # Informational before commercial: interrogatives override comparison signals
    if words & _INFORMATIONAL_SIGNALS:
        return QueryIntent.INFORMATIONAL

    if words & _COMMERCIAL_SIGNALS:
        return QueryIntent.COMMERCIAL

    return QueryIntent.UNKNOWN


def classify_intent(query: str, brand_terms: frozenset[str] = frozenset()) -> QueryIntent:
    """Classify a query into an intent category.

    Args:
        query: Raw search query.
        brand_terms: Shop-specific brand tokens treated as navigational signals.

    Returns:
        QueryIntent enum value.
    """
    return _classify_intent(query, brand_terms)


def _compute_tfidf(corpus: list[list[str]]) -> list[dict[str, float]]:
    n = len(corpus)
    df: Counter[str] = Counter()
    for tokens in corpus:
        df.update(set(tokens))

    scores = []
    for tokens in corpus:
        if not tokens:
            scores.append({})
            continue
        tf = Counter(tokens)
        doc_len = len(tokens)
        doc_scores: dict[str, float] = {}
        for term, count in tf.items():
            term_tf = count / doc_len
            term_idf = math.log((n + 1) / (df[term] + 1)) + 1
            doc_scores[term] = term_tf * term_idf
        scores.append(doc_scores)

    return scores


def _top_terms(queries: list[str], n: int = _TOP_KEYWORDS_PER_CLUSTER) -> list[str]:
    """Return the most distinctive terms across a list of queries."""
    corpus = [_tokenize(q) for q in queries]
    tfidf_scores = _compute_tfidf(corpus)
    term_totals: Counter[str] = Counter()
    for scores in tfidf_scores:
        for term, score in scores.items():
            term_totals[term] += score
    return [term for term, _ in term_totals.most_common(n)]


def _dominant_term(query: str) -> str:
    """Return the highest-IDF single token in the query (used for sub-grouping)."""
    tokens = _tokenize(query)
    return tokens[0] if tokens else ""


def _jaccard(set_a: set[str], set_b: set[str]) -> float:
    if not set_a and not set_b:
        return 1.0
    inter = len(set_a & set_b)
    union = len(set_a | set_b)
    return inter / union if union else 0.0


def _sub_cluster_by_terms(
    rows: list[dict],
    intent: QueryIntent,
) -> list[IntentCluster]:
    """Within an intent bucket, group queries by shared dominant terms.

    Uses a greedy merge: queries that share >= MERGE_THRESHOLD Jaccard
    similarity with the first query of a group are merged into it.

    Args:
        rows: List of GSC row dicts (query, impressions, clicks, position).
        intent: The shared intent for all rows.

    Returns:
        List of IntentCluster, sorted by total_impressions desc.
    """
    groups: list[list[dict]] = []

    for row in rows:
        tokens = set(_tokenize(row["query"]))
        merged = False
        for group in groups:
            rep_tokens = set(_tokenize(group[0]["query"]))
            if _jaccard(tokens, rep_tokens) >= _MERGE_THRESHOLD:
                group.append(row)
                merged = True
                break
        if not merged:
            groups.append([row])

    clusters: list[IntentCluster] = []
    for group in groups:
        queries = [r["query"] for r in group]
        total_imp = sum(r.get("impressions", 0) for r in group)
        total_cli = sum(r.get("clicks", 0) for r in group)
        imp_weights = [r.get("impressions", 0) for r in group]
        positions = [r.get("position", 0.0) for r in group]
        total_w = sum(imp_weights) or 1
        avg_pos = sum(p * w for p, w in zip(positions, imp_weights)) / total_w

        top_kw = _top_terms(queries)
        label = top_kw[0] if top_kw else queries[0][:30]
        name = f"{intent.value} — {label}"

        clusters.append(
            IntentCluster(
                name=name,
                intent=intent,
                queries=queries,
                total_impressions=total_imp,
                total_clicks=total_cli,
                avg_position=round(avg_pos, 1),
                top_keywords=top_kw,
            )
        )

    return sorted(clusters, key=lambda c: c.total_impressions, reverse=True)


def cluster_gsc_queries(
    gsc_queries: list[dict],
    *,
    min_impressions: int = _MIN_IMPRESSIONS,
    brand_terms: frozenset[str] = frozenset(),
) -> list[IntentCluster]:
    """Cluster GSC queries by intent and semantic similarity.

    Queries with fewer than min_impressions are excluded (noise filter).
    Results are sorted by total_impressions desc.

    Args:
        gsc_queries: List of GSC row dicts with keys: query, impressions, clicks, position.
        min_impressions: Minimum impressions threshold (default 5).

    Returns:
        Flat list of IntentCluster sorted by total_impressions desc.
    """
    filtered = [
        r
        for r in gsc_queries
        if isinstance(r.get("query"), str) and r.get("impressions", 0) >= min_impressions
    ]

    if not filtered:
        return []

    # Group by intent first
    by_intent: defaultdict[QueryIntent, list[dict]] = defaultdict(list)
    for row in filtered:
        intent = _classify_intent(row["query"], brand_terms)
        by_intent[intent].append(row)

    all_clusters: list[IntentCluster] = []
    for intent, rows in by_intent.items():
        all_clusters.extend(_sub_cluster_by_terms(rows, intent))

    return sorted(all_clusters, key=lambda c: c.total_impressions, reverse=True)
