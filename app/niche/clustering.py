"""Product clustering via TF-IDF (no external ML dependency)."""

from __future__ import annotations

import math
import re
import unicodedata
from collections import Counter, defaultdict

from app.niche.models import ProductCluster

# French stopwords — extended for e-commerce context
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
    "par",
    "plus",
    "très",
    "bien",
    "aussi",
    "tout",
    "tous",
    "cette",
    "cet",
    # e-commerce noise
    "premium",
    "design",
    "style",
    "qualité",
    "haute",
    "produit",
    "article",
}
from app.nlp.lang_resources import stopwords_all  # noqa: E402

_STOPWORDS = frozenset(_STOPWORDS) | stopwords_all()

_MIN_TERM_LEN = 3
_TOP_KEYWORDS_PER_CLUSTER = 8
_MIN_CLUSTER_SIZE = 1


def _normalize(text: str) -> str:
    """Lowercase, remove accents, keep only letters and spaces."""
    nfkd = unicodedata.normalize("NFKD", text.lower())
    ascii_text = "".join(c for c in nfkd if not unicodedata.combining(c))
    return re.sub(r"[^a-z\s]", " ", ascii_text)


def _tokenize(text: str) -> list[str]:
    tokens = _normalize(text).split()
    return [t for t in tokens if len(t) >= _MIN_TERM_LEN and t not in _STOPWORDS]


def _compute_tfidf(corpus: list[list[str]]) -> list[dict[str, float]]:
    """Return TF-IDF scores for each document in the corpus.

    Args:
        corpus: List of token lists (one per document).

    Returns:
        List of {term: tfidf_score} dicts, one per document.
    """
    n = len(corpus)
    # Document frequency: how many docs contain each term
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
            term_idf = math.log((n + 1) / (df[term] + 1)) + 1  # smoothed IDF
            doc_scores[term] = term_tf * term_idf
        scores.append(doc_scores)

    return scores


def _product_text(product: dict) -> str:
    parts = [
        product.get("title", ""),
        product.get("product_type", ""),
        " ".join(product.get("tags", []) if isinstance(product.get("tags"), list) else []),
    ]
    return " ".join(p for p in parts if p)


def cluster_products(products: list[dict]) -> list[ProductCluster]:
    """Group products into niche clusters using TF-IDF keyword extraction.

    Strategy:
      1. If product_type is populated, use it as the primary cluster key.
      2. Products without product_type are grouped by their dominant TF-IDF term.
      3. Each cluster's display name is its most representative term.

    Args:
        products: Shopify product dicts (title, product_type, tags required).

    Returns:
        List of ProductCluster sorted by size descending.
    """
    if not products:
        return []

    # Build TF-IDF corpus
    texts = [_product_text(p) for p in products]
    corpus = [_tokenize(t) for t in texts]
    tfidf_scores = _compute_tfidf(corpus)

    # Primary grouping: by product_type (normalized)
    groups: dict[str, list[int]] = defaultdict(list)
    for i, product in enumerate(products):
        ptype = _normalize(product.get("product_type", "")).strip()
        if ptype and ptype not in _STOPWORDS:
            groups[ptype].append(i)
        else:
            # Fall back: dominant TF-IDF term
            scores = tfidf_scores[i]
            if scores:
                top_term = max(scores, key=lambda t: scores[t])
                groups[top_term].append(i)
            else:
                groups["autre"].append(i)

    # Build cluster objects
    clusters: list[ProductCluster] = []
    for group_key, indices in groups.items():
        # Aggregate TF-IDF scores across all products in group
        agg: Counter[str] = Counter()
        for idx in indices:
            for term, score in tfidf_scores[idx].items():
                agg[term] += score

        top_keywords = [term for term, _ in agg.most_common(_TOP_KEYWORDS_PER_CLUSTER)]

        # Cluster name: group_key (product_type) or top keyword
        cluster_name = (
            group_key
            if len(group_key) >= _MIN_TERM_LEN
            else (top_keywords[0] if top_keywords else "autre")
        )

        clusters.append(
            ProductCluster(
                name=cluster_name,
                product_ids=[str(products[i].get("id", "")) for i in indices],
                product_titles=[str(products[i].get("title", "")) for i in indices],
                keywords=top_keywords,
            )
        )

    return sorted(clusters, key=lambda c: c.size, reverse=True)
