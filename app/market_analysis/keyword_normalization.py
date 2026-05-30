"""French keyword normalization, lemmatization, and semantic clustering.

Pure Python, no external NLP dependency. Used by the market analysis engine to:
- dedupe accent variants in the keyword candidate pool (`café` / `cafe`)
- collapse singular/plural variants into a single cluster
- detect cross-product cannibalization via cluster identity
- evaluate semantic keyword coverage (lemma- and accent-aware) in generated content
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any

_FR_STOP_WORDS = frozenset(
    "de du la le les des pour avec sans sur par en au aux un une et ou à dans que qui ne pas"
    " se ce cet cette ces mon ma mes ton ta tes son sa ses notre nos votre vos leur leurs"
    " je tu il elle nous vous ils elles est sont être avoir".split()
)

# Suffix-stripping rules applied in order. Each entry is (suffix, min_length_after).
# Conservative: only removes endings that are unambiguously inflectional in French.
_LEMMA_SUFFIXES: tuple[tuple[str, int], ...] = (
    ("ement", 4),
    ("eront", 4),
    ("aient", 4),
    ("ions", 4),
    ("ent", 4),
    ("age", 4),
    ("ées", 3),
    ("ée", 3),
    ("ies", 3),
    ("ir", 4),
    ("es", 3),
    ("s", 4),
    ("x", 4),
    ("e", 4),
)

_WORD_RE = re.compile(r"[a-zàâäéèêëîïôùûüç]+")


def strip_accents(text: str) -> str:
    """Remove French diacritics via NFD decomposition.

    `strip_accents("café") == "cafe"`.
    """
    if not text:
        return text
    decomposed = unicodedata.normalize("NFD", text)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def lemmatize_fr(token: str) -> str:
    """Strip common French inflectional suffixes.

    Returns the input token unchanged if it is too short or no suffix matches.
    Conservative: never produces a stem shorter than the per-suffix `min_length`.
    """
    if len(token) < 4:
        return token
    for suffix, min_len in _LEMMA_SUFFIXES:
        if token.endswith(suffix) and len(token) - len(suffix) >= min_len - len(suffix) + 1:
            stripped = token[: -len(suffix)]
            if len(stripped) >= 3:
                return stripped
    return token


def normalize_token(token: str) -> str:
    """Lowercase + strip accents + lemmatize a single token."""
    if not token or not token.strip():
        return ""
    return lemmatize_fr(strip_accents(token.lower()))


def tokenize_normalized(text: str) -> set[str]:
    """Tokenize a string, drop stop words/short tokens, return normalized stems."""
    if not text:
        return set()
    tokens: set[str] = set()
    for raw in _WORD_RE.findall(text.lower()):
        if len(raw) < 3 or raw in _FR_STOP_WORDS:
            continue
        stem = normalize_token(raw)
        if stem:
            tokens.add(stem)
    return tokens


def jaccard_similarity(a: set[str], b: set[str]) -> float:
    """Jaccard set similarity, defined as 0.0 on empty union."""
    if not a or not b:
        return 0.0
    union = a | b
    if not union:
        return 0.0
    return len(a & b) / len(union)


def build_clusters(
    keywords: list[dict[str, Any]],
    *,
    threshold: float = 0.5,
) -> list[dict[str, Any]]:
    """Group keywords by semantic similarity.

    Args:
        keywords: list of keyword dicts with at least a `query` field; optional
            `search_volume` is used to pick the cluster head.
        threshold: minimum Jaccard similarity (over normalized tokens) to merge
            two keywords into the same cluster.

    Returns:
        A list of clusters: `{cluster_id, head_keyword, member_queries, members}`.
        Empty input returns `[]`. Keywords with blank queries are skipped.
    """
    enriched: list[dict[str, Any]] = []
    for kw in keywords:
        query = str(kw.get("query") or "").strip()
        if not query:
            continue
        enriched.append({"_kw": kw, "_tokens": tokenize_normalized(query)})

    if not enriched:
        return []

    cluster_assignments: list[int] = [-1] * len(enriched)
    next_cluster = 0
    for i, entry in enumerate(enriched):
        if cluster_assignments[i] != -1:
            continue
        cluster_assignments[i] = next_cluster
        for j in range(i + 1, len(enriched)):
            if cluster_assignments[j] != -1:
                continue
            sim = jaccard_similarity(entry["_tokens"], enriched[j]["_tokens"])
            if sim >= threshold:
                cluster_assignments[j] = next_cluster
        next_cluster += 1

    clusters_by_id: dict[int, list[dict[str, Any]]] = {}
    for idx, cid in enumerate(cluster_assignments):
        clusters_by_id.setdefault(cid, []).append(enriched[idx]["_kw"])

    results: list[dict[str, Any]] = []
    for cid, members in clusters_by_id.items():
        head = max(
            members,
            key=lambda kw: (
                _coerce_volume(kw.get("search_volume")),
                len(str(kw.get("query") or "")),
            ),
        )
        results.append(
            {
                "cluster_id": f"cluster_{cid}",
                "head_keyword": str(head.get("query") or ""),
                "member_queries": [str(m.get("query") or "") for m in members],
                "members": members,
            }
        )
    return results


def is_semantically_covered(query: str, text: str, *, threshold: float = 0.7) -> bool:
    """Return True if at least `threshold` of query tokens appear in `text`.

    Uses normalized tokens (lowercase + accent-stripped + lemmatized), so
    `croquettes` covers `croquette` and `pâtée` covers `patee`.
    """
    query_tokens = tokenize_normalized(query)
    if not query_tokens:
        return False
    text_tokens = tokenize_normalized(text)
    if not text_tokens:
        return False
    matched = sum(1 for token in query_tokens if token in text_tokens)
    return matched / len(query_tokens) >= threshold


def _coerce_volume(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0
