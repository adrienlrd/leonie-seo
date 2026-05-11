"""Tests for embeddings store — upsert, cosine similarity, top-k search."""

from __future__ import annotations

import json
import math
import sqlite3
from pathlib import Path

from app.embeddings.store import (
    _cosine_similarity,
    search_similar_products,
    search_similar_queries,
    upsert_product_embedding,
    upsert_query_embedding,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _init_db(db_path: Path) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS product_embeddings (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                shop          TEXT NOT NULL,
                product_id    TEXT NOT NULL,
                product_title TEXT NOT NULL DEFAULT '',
                embedding     TEXT NOT NULL,
                model         TEXT NOT NULL DEFAULT 'intfloat/multilingual-e5-base',
                created_at    TEXT NOT NULL DEFAULT (datetime('now')),
                UNIQUE(shop, product_id)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS query_embeddings (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                shop       TEXT NOT NULL,
                query      TEXT NOT NULL,
                embedding  TEXT NOT NULL,
                model      TEXT NOT NULL DEFAULT 'intfloat/multilingual-e5-base',
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                UNIQUE(shop, query)
            )
        """)


def _vec(n: int, dims: int = 4) -> list[float]:
    """Build a unit vector with 1.0 at position n, rest 0.0."""
    v = [0.0] * dims
    v[n % dims] = 1.0
    return v


# ---------------------------------------------------------------------------
# _cosine_similarity
# ---------------------------------------------------------------------------


def test_cosine_similarity_identical_vectors():
    v = [1.0, 0.0, 0.0]
    assert abs(_cosine_similarity(v, v) - 1.0) < 1e-9


def test_cosine_similarity_orthogonal_vectors():
    a = [1.0, 0.0]
    b = [0.0, 1.0]
    assert abs(_cosine_similarity(a, b)) < 1e-9


def test_cosine_similarity_opposite_vectors():
    a = [1.0, 0.0]
    b = [-1.0, 0.0]
    assert abs(_cosine_similarity(a, b) + 1.0) < 1e-9


def test_cosine_similarity_zero_vector_returns_zero():
    assert _cosine_similarity([0.0, 0.0], [1.0, 0.0]) == 0.0


def test_cosine_similarity_arbitrary_vectors():
    a = [3.0, 4.0]
    b = [4.0, 3.0]
    expected = (3 * 4 + 4 * 3) / (5 * 5)
    assert abs(_cosine_similarity(a, b) - expected) < 1e-9


# ---------------------------------------------------------------------------
# upsert_product_embedding
# ---------------------------------------------------------------------------


def test_upsert_product_embedding_inserts_row(tmp_path):
    db = tmp_path / "test.db"
    _init_db(db)
    upsert_product_embedding("shop.myshopify.com", "123", "Harnais Premium", _vec(0), db_path=db)

    with sqlite3.connect(db) as conn:
        row = conn.execute("SELECT product_id, product_title FROM product_embeddings").fetchone()
    assert row[0] == "123"
    assert row[1] == "Harnais Premium"


def test_upsert_product_embedding_updates_on_conflict(tmp_path):
    db = tmp_path / "test.db"
    _init_db(db)
    upsert_product_embedding("s.myshopify.com", "1", "Old Title", _vec(0), db_path=db)
    upsert_product_embedding("s.myshopify.com", "1", "New Title", _vec(1), db_path=db)

    with sqlite3.connect(db) as conn:
        rows = conn.execute("SELECT COUNT(*) FROM product_embeddings").fetchone()
        row = conn.execute("SELECT product_title FROM product_embeddings").fetchone()
    assert rows[0] == 1
    assert row[0] == "New Title"


def test_upsert_product_embedding_stores_valid_json(tmp_path):
    db = tmp_path / "test.db"
    _init_db(db)
    vec = [0.1, 0.2, 0.3, 0.4]
    upsert_product_embedding("s.myshopify.com", "1", "T", vec, db_path=db)

    with sqlite3.connect(db) as conn:
        raw = conn.execute("SELECT embedding FROM product_embeddings").fetchone()[0]
    loaded = json.loads(raw)
    assert len(loaded) == 4
    assert abs(loaded[0] - 0.1) < 1e-9


# ---------------------------------------------------------------------------
# upsert_query_embedding
# ---------------------------------------------------------------------------


def test_upsert_query_embedding_inserts_row(tmp_path):
    db = tmp_path / "test.db"
    _init_db(db)
    upsert_query_embedding("shop.myshopify.com", "harnais chien", _vec(2), db_path=db)

    with sqlite3.connect(db) as conn:
        row = conn.execute("SELECT query FROM query_embeddings").fetchone()
    assert row[0] == "harnais chien"


# ---------------------------------------------------------------------------
# search_similar_products
# ---------------------------------------------------------------------------


def test_search_similar_products_returns_top_k(tmp_path):
    db = tmp_path / "test.db"
    _init_db(db)
    shop = "s.myshopify.com"
    upsert_product_embedding(shop, "1", "Harnais A", _vec(0), db_path=db)
    upsert_product_embedding(shop, "2", "Harnais B", _vec(1), db_path=db)
    upsert_product_embedding(shop, "3", "Collier C", _vec(2), db_path=db)

    results = search_similar_products(shop, _vec(0), top_k=2, db_path=db)
    assert len(results) == 2
    assert results[0]["product_id"] == "1"
    assert results[0]["similarity"] == 1.0


def test_search_similar_products_isolates_by_shop(tmp_path):
    db = tmp_path / "test.db"
    _init_db(db)
    upsert_product_embedding("shop-a.myshopify.com", "1", "Prod A", _vec(0), db_path=db)
    upsert_product_embedding("shop-b.myshopify.com", "2", "Prod B", _vec(1), db_path=db)

    results = search_similar_products("shop-a.myshopify.com", _vec(0), top_k=5, db_path=db)
    assert len(results) == 1
    assert results[0]["product_id"] == "1"


def test_search_similar_products_empty_store(tmp_path):
    db = tmp_path / "test.db"
    _init_db(db)
    results = search_similar_products("shop.myshopify.com", _vec(0), top_k=5, db_path=db)
    assert results == []


def test_search_similar_products_sorted_by_similarity(tmp_path):
    db = tmp_path / "test.db"
    _init_db(db)
    shop = "s.myshopify.com"
    # product 1: perfectly aligned with query
    upsert_product_embedding(shop, "1", "Perfect", [1.0, 0.0, 0.0, 0.0], db_path=db)
    # product 2: diagonal, sim = 1/sqrt(2) ≈ 0.707
    diag = [1.0, 1.0, 0.0, 0.0]
    norm = math.sqrt(2)
    diag_norm = [x / norm for x in diag]
    upsert_product_embedding(shop, "2", "Partial", diag_norm, db_path=db)
    # product 3: orthogonal, sim = 0
    upsert_product_embedding(shop, "3", "Ortho", [0.0, 0.0, 1.0, 0.0], db_path=db)

    results = search_similar_products(shop, [1.0, 0.0, 0.0, 0.0], top_k=3, db_path=db)
    assert results[0]["product_id"] == "1"
    assert results[1]["product_id"] == "2"
    assert results[2]["similarity"] == 0.0


# ---------------------------------------------------------------------------
# search_similar_queries
# ---------------------------------------------------------------------------


def test_search_similar_queries_returns_matching_queries(tmp_path):
    db = tmp_path / "test.db"
    _init_db(db)
    shop = "s.myshopify.com"
    upsert_query_embedding(shop, "harnais chien", _vec(0), db_path=db)
    upsert_query_embedding(shop, "collier chat", _vec(1), db_path=db)
    upsert_query_embedding(shop, "fontaine eau chat", _vec(2), db_path=db)

    results = search_similar_queries(shop, _vec(0), top_k=2, db_path=db)
    assert len(results) == 2
    assert results[0]["query"] == "harnais chien"
    assert results[0]["similarity"] == 1.0
