"""Tests for the per-shop blog authors store."""

from __future__ import annotations

from pathlib import Path

import pytest

import app.blog.authors as authors_mod
from app.blog.authors import delete_author, load_authors, save_author


@pytest.fixture(autouse=True)
def _isolated_data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(authors_mod, "_DATA_DIR", tmp_path)


def test_save_then_load_author(tmp_path: Path) -> None:
    saved = save_author("shop.myshopify.com", {"name": "Léonie", "bio": "Experte", "url": "https://x"}, db_path=tmp_path / "db.sqlite")
    assert saved["id"]
    authors = load_authors("shop.myshopify.com", db_path=tmp_path / "db.sqlite")
    assert len(authors) == 1
    assert authors[0]["name"] == "Léonie"
    assert authors[0]["bio"] == "Experte"


def test_update_existing_author(tmp_path: Path) -> None:
    db = tmp_path / "db.sqlite"
    a = save_author("shop.myshopify.com", {"name": "Léonie", "bio": "v1"}, db_path=db)
    save_author("shop.myshopify.com", {"id": a["id"], "name": "Léonie", "bio": "v2"}, db_path=db)
    authors = load_authors("shop.myshopify.com", db_path=db)
    assert len(authors) == 1
    assert authors[0]["bio"] == "v2"


def test_delete_author(tmp_path: Path) -> None:
    db = tmp_path / "db.sqlite"
    a = save_author("shop.myshopify.com", {"name": "Léonie"}, db_path=db)
    assert delete_author("shop.myshopify.com", a["id"], db_path=db) is True
    assert load_authors("shop.myshopify.com", db_path=db) == []
    assert delete_author("shop.myshopify.com", "missing", db_path=db) is False


def test_name_required() -> None:
    with pytest.raises(ValueError):
        save_author("shop.myshopify.com", {"name": "  "})
