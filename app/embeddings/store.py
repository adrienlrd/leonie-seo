"""Embeddings store — upsert and cosine similarity search.

SQLite backend: embedding stored as JSON text, cosine computed in Python.
Postgres backend: embedding stored as pgvector `vector(768)`, cosine via `<=>` operator.
"""

from __future__ import annotations

import json
import math
import os
import sqlite3
from pathlib import Path

from app.db_adapter import DB_PATH


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


def _vec_literal(embedding: list[float]) -> str:
    """Format a float list as a Postgres vector literal '[0.1,0.2,...]'."""
    return "[" + ",".join(str(x) for x in embedding) + "]"


# ---------------------------------------------------------------------------
# SQLite helpers
# ---------------------------------------------------------------------------


def _sqlite_upsert(
    db_path: Path,
    table: str,
    shop: str,
    key_col: str,
    key_val: str,
    title: str | None,
    embedding: list[float],
    model: str,
) -> None:
    with sqlite3.connect(db_path) as conn:
        if title is not None:
            conn.execute(
                f"""INSERT INTO {table} (shop, {key_col}, product_title, embedding, model)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(shop, {key_col}) DO UPDATE SET
                        product_title = excluded.product_title,
                        embedding = excluded.embedding,
                        model = excluded.model""",
                (shop, key_val, title, json.dumps(embedding), model),
            )
        else:
            conn.execute(
                f"""INSERT INTO {table} (shop, {key_col}, embedding, model)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(shop, {key_col}) DO UPDATE SET
                        embedding = excluded.embedding,
                        model = excluded.model""",
                (shop, key_val, json.dumps(embedding), model),
            )


def _sqlite_search(
    db_path: Path,
    table: str,
    shop: str,
    key_col: str,
    query_embedding: list[float],
    top_k: int,
) -> list[dict]:
    has_title = table == "product_embeddings"
    title_col = ", product_title" if has_title else ""

    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            f"SELECT {key_col}{title_col}, embedding FROM {table} WHERE shop = ?",
            (shop,),
        ).fetchall()

    results = []
    for row in rows:
        key_val = row[0]
        title = (row[1] or key_val) if has_title else key_val
        vec = json.loads(row[2] if has_title else row[1])
        sim = _cosine_similarity(query_embedding, vec)
        results.append({key_col: key_val, "title": title, "similarity": round(sim, 4)})
    results.sort(key=lambda r: r["similarity"], reverse=True)
    return results[:top_k]


# ---------------------------------------------------------------------------
# Postgres helpers
# ---------------------------------------------------------------------------


def _pg_upsert(
    database_url: str,
    table: str,
    shop: str,
    key_col: str,
    key_val: str,
    title: str | None,
    embedding: list[float],
    model: str,
) -> None:
    import psycopg2  # noqa: PLC0415

    vec = _vec_literal(embedding)
    with psycopg2.connect(database_url) as conn:
        with conn.cursor() as cur:
            if title is not None:
                cur.execute(
                    f"""INSERT INTO {table} (shop, {key_col}, product_title, embedding, model)
                        VALUES (%s, %s, %s, %s::vector, %s)
                        ON CONFLICT(shop, {key_col}) DO UPDATE SET
                            product_title = EXCLUDED.product_title,
                            embedding = EXCLUDED.embedding,
                            model = EXCLUDED.model""",
                    (shop, key_val, title, vec, model),
                )
            else:
                cur.execute(
                    f"""INSERT INTO {table} (shop, {key_col}, embedding, model)
                        VALUES (%s, %s, %s::vector, %s)
                        ON CONFLICT(shop, {key_col}) DO UPDATE SET
                            embedding = EXCLUDED.embedding,
                            model = EXCLUDED.model""",
                    (shop, key_val, vec, model),
                )
        conn.commit()


def _pg_search(
    database_url: str,
    table: str,
    shop: str,
    key_col: str,
    query_embedding: list[float],
    top_k: int,
) -> list[dict]:
    import psycopg2  # noqa: PLC0415

    vec = _vec_literal(query_embedding)
    with psycopg2.connect(database_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""SELECT {key_col}, product_title,
                           1 - (embedding <=> %s::vector) AS similarity
                    FROM {table}
                    WHERE shop = %s
                    ORDER BY embedding <=> %s::vector
                    LIMIT %s""",
                (vec, shop, vec, top_k),
            )
            rows = cur.fetchall()

    return [
        {
            key_col: r[0],
            "title": r[1] or r[0],
            "similarity": round(float(r[2]), 4),
        }
        for r in rows
    ]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

_DEFAULT_MODEL = "intfloat/multilingual-e5-base"


def upsert_product_embedding(
    shop: str,
    product_id: str,
    product_title: str,
    embedding: list[float],
    *,
    model: str = _DEFAULT_MODEL,
    db_path: Path | None = None,
) -> None:
    """Store or update a product embedding.

    Args:
        shop: Shopify shop domain.
        product_id: Shopify product ID (as string).
        product_title: Product title (stored for display in search results).
        embedding: 768-dimensional float vector.
        model: Model name used to generate the embedding.
        db_path: SQLite path override (tests only).
    """
    database_url = os.getenv("DATABASE_URL") if db_path is None else None
    if database_url:
        _pg_upsert(
            database_url,
            "product_embeddings",
            shop,
            "product_id",
            product_id,
            product_title,
            embedding,
            model,
        )
    else:
        path = db_path or DB_PATH
        _sqlite_upsert(
            path,
            "product_embeddings",
            shop,
            "product_id",
            product_id,
            product_title,
            embedding,
            model,
        )


def upsert_query_embedding(
    shop: str,
    query: str,
    embedding: list[float],
    *,
    model: str = _DEFAULT_MODEL,
    db_path: Path | None = None,
) -> None:
    """Store or update a GSC query embedding.

    Args:
        shop: Shopify shop domain.
        query: GSC search query string.
        embedding: 768-dimensional float vector.
        model: Model name used to generate the embedding.
        db_path: SQLite path override (tests only).
    """
    database_url = os.getenv("DATABASE_URL") if db_path is None else None
    if database_url:
        _pg_upsert(database_url, "query_embeddings", shop, "query", query, None, embedding, model)
    else:
        path = db_path or DB_PATH
        _sqlite_upsert(path, "query_embeddings", shop, "query", query, None, embedding, model)


def search_similar_products(
    shop: str,
    query_embedding: list[float],
    *,
    top_k: int = 5,
    db_path: Path | None = None,
) -> list[dict]:
    """Return the top-k products most similar to a query embedding.

    Args:
        shop: Shopify shop domain.
        query_embedding: Query vector (768 dims, L2-normalised).
        top_k: Number of results to return.
        db_path: SQLite path override (tests only).

    Returns:
        List of dicts with keys: product_id, title, similarity (0–1).
    """
    database_url = os.getenv("DATABASE_URL") if db_path is None else None
    if database_url:
        return _pg_search(
            database_url, "product_embeddings", shop, "product_id", query_embedding, top_k
        )
    path = db_path or DB_PATH
    return _sqlite_search(path, "product_embeddings", shop, "product_id", query_embedding, top_k)


def search_similar_queries(
    shop: str,
    product_embedding: list[float],
    *,
    top_k: int = 10,
    db_path: Path | None = None,
) -> list[dict]:
    """Return the top-k GSC queries most similar to a product embedding.

    Args:
        shop: Shopify shop domain.
        product_embedding: Product vector (768 dims, L2-normalised).
        top_k: Number of results to return.
        db_path: SQLite path override (tests only).
    """
    database_url = os.getenv("DATABASE_URL") if db_path is None else None
    if database_url:
        return _pg_search(database_url, "query_embeddings", shop, "query", product_embedding, top_k)
    path = db_path or DB_PATH
    return _sqlite_search(path, "query_embeddings", shop, "query", product_embedding, top_k)
