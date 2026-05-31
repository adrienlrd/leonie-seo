"""Tests for the internal shop-token sync endpoint."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

SHOP = "287c4a-bb.myshopify.com"
PATH = f"/api/shops/{SHOP}/internal/token"


def test_sync_requires_internal_secret() -> None:
    resp = TestClient(app).post(PATH, json={"access_token": "shpat_x"})
    assert resp.status_code == 403


def test_sync_saves_token(monkeypatch) -> None:
    monkeypatch.setenv("INTERNAL_API_SECRET", "s3cret")
    captured: dict = {}
    monkeypatch.setattr(
        "app.api.shops.save_token",
        lambda shop, access_token, scope: captured.update(
            shop=shop, token=access_token, scope=scope
        ),
    )

    resp = TestClient(app).post(
        PATH,
        json={"access_token": "shpat_fresh", "scope": "read_themes,write_themes"},
        headers={"X-Internal-Secret": "s3cret"},
    )

    assert resp.status_code == 200
    assert resp.json() == {"saved": True}
    assert captured == {
        "shop": SHOP,
        "token": "shpat_fresh",
        "scope": "read_themes,write_themes",
    }


def test_sync_rejects_bad_shop(monkeypatch) -> None:
    monkeypatch.setenv("INTERNAL_API_SECRET", "s3cret")
    resp = TestClient(app).post(
        "/api/shops/not-a-shop/internal/token",
        json={"access_token": "x"},
        headers={"X-Internal-Secret": "s3cret"},
    )
    assert resp.status_code == 400
