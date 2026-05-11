"""Sentence-transformers encoder — lazy-loaded to avoid startup cost.

Model: intfloat/multilingual-e5-base — 768 dims, ~400 MB, supports FR/EN/DE/NL.
Downloaded on first call and cached in ~/.cache/huggingface/.
"""

from __future__ import annotations

_MODEL_NAME = "intfloat/multilingual-e5-base"
_encoder = None


def _get_encoder():
    global _encoder
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


def encode_texts(texts: list[str]) -> list[list[float]]:
    """Encode a list of texts into normalised embeddings.

    Args:
        texts: Raw text strings to encode (titles, queries, descriptions).

    Returns:
        List of 768-dimensional float vectors, one per input text.
        Vectors are L2-normalised so cosine similarity equals dot product.
    """
    if not texts:
        return []
    # E5 models expect a task prefix for retrieval quality
    prefixed = [f"query: {t}" for t in texts]
    encoder = _get_encoder()
    return encoder.encode(prefixed, normalize_embeddings=True).tolist()


def encode_query(query: str) -> list[float]:
    """Encode a single query string into a normalised embedding."""
    return encode_texts([query])[0]


def encode_passage(text: str) -> list[float]:
    """Encode a passage (product title/description) into a normalised embedding."""
    encoder = _get_encoder()
    return encoder.encode([f"passage: {text}"], normalize_embeddings=True).tolist()[0]
