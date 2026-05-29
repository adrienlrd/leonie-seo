"""Per-shop blog draft store: list/get/save/delete on the persistent data disk."""

from __future__ import annotations

from app.blog import store


def test_save_creates_id_and_persists(monkeypatch, tmp_path):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    saved = store.save_draft(
        "shop.myshopify.com",
        {
            "product_id": "gid://shopify/Product/1",
            "product_title": "Fontaine Smart",
            "blog_title": "Guide fontaine chat",
            "intro": "...",
            "sections": [],
        },
    )
    assert saved["id"]
    assert saved["status"] == "draft"
    assert saved["created_at"]
    fetched = store.get_draft("shop.myshopify.com", saved["id"])
    assert fetched and fetched["blog_title"] == "Guide fontaine chat"


def test_list_orders_by_updated_at_desc(monkeypatch, tmp_path):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    a = store.save_draft("s", {"product_title": "A", "blog_title": "A", "sections": []})
    b = store.save_draft("s", {"product_title": "B", "blog_title": "B", "sections": []})
    drafts = store.list_drafts("s")
    assert drafts[0]["id"] == b["id"]
    assert drafts[1]["id"] == a["id"]


def test_delete_removes_draft(monkeypatch, tmp_path):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    saved = store.save_draft("s", {"product_title": "x", "blog_title": "x", "sections": []})
    assert store.delete_draft("s", saved["id"]) is True
    assert store.get_draft("s", saved["id"]) is None
    assert store.delete_draft("s", "missing") is False
