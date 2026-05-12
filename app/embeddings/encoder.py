"""Sentence-transformers encoder — lazy-loaded to avoid startup cost.

Model: intfloat/multilingual-e5-base — 768 dims, ~400 MB, supports FR/EN/DE/NL.
Downloaded on first call and cached in ~/.cache/huggingface/.

E5 models REQUIRE a task prefix on every input:
- "query: <text>" for short, intent-style retrieval queries (e.g. GSC keyword)
- "passage: <text>" for indexed corpus documents (e.g. product titles)

Mixing prefixes silently degrades cosine recall. The encoder API enforces
the choice via an explicit `mode` argument — there is no default for batch
calls so a buggy caller can't accidentally tag passages as queries.
"""

from __future__ import annotations

import threading
from typing import Literal

_MODEL_NAME = "intfloat/multilingual-e5-base"
_encoder = None
_encoder_lock = threading.Lock()


def _get_encoder():
    """Lazy-load the SentenceTransformer model — thread-safe.

    The lock makes the double-check pattern safe under FastAPI's threaded
    workers / threadpool executors that can call into the encoder
    concurrently on first request.
    """
    global _encoder
    if _encoder is not None:
        return _encoder
    with _encoder_lock:
        if _encoder is None:
            try:
                from sentence_transformers import SentenceTransformer  # noqa: PLC0415
            except ImportError as exc:
                raise ImportError(
                    "sentence-transformers is required for embeddings. "
                    "Install it with: pip install 'leonie-seo[embeddings]'"
                ) from exc
            _encoder = SentenceTransformer(_MODEL_NAME)
    return _encoder


def encode_texts(
    texts: list[str],
    *,
    mode: Literal["query", "passage"],
) -> list[list[float]]:
    """Encode a batch of texts into normalised embeddings with the right E5 prefix.

    Args:
        texts: Raw text strings.
        mode: "query" for short intent-style retrieval queries, "passage" for
              indexed corpus documents (product titles, descriptions, etc.).
              Required — no default — to prevent silent passage/query mix-ups.

    Returns:
        List of 768-dimensional float vectors, one per input text. Vectors are
        L2-normalised so cosine similarity equals the dot product.
    """
    if not texts:
        return []
    prefix = "query: " if mode == "query" else "passage: "
    prefixed = [prefix + t for t in texts]
    encoder = _get_encoder()
    return encoder.encode(prefixed, normalize_embeddings=True).tolist()


def encode_query(query: str) -> list[float]:
    """Encode a single query string into a normalised embedding."""
    return encode_texts([query], mode="query")[0]


def encode_passage(text: str) -> list[float]:
    """Encode a passage (product title/description) into a normalised embedding."""
    return encode_texts([text], mode="passage")[0]
