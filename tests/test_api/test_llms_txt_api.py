"""API tests for the llms.txt generate / publish / status / webhook endpoints."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.api.deps import ShopContext, get_shop_context
from app.main import app

SHOP = "shop.myshopify.com"

_SNAPSHOT = {
    "shop": {"name": "Léonie", "primaryDomain": {"host": "leonie.com"}},
    "products": [
        {
            "id": "1",
            "title": "Harnais chien cuir",
            "handle": "harnais-chien-cuir",
            "description": "Harnais en cuir pleine fleur cousu main en France, garantie 2 ans.",
        }
    ],
    "collections": [],
    "pages": [],
}


@pytest.fixture()
def snapshot_file(tmp_path: Path) -> Path:
    p = tmp_path / "shopify_snapshot.json"
    p.write_text(json.dumps(_SNAPSHOT), encoding="utf-8")
    return p


@pytest.fixture()
def client(snapshot_file: Path):
    def _fake_ctx() -> ShopContext:
        return ShopContext(
            shop=SHOP,
            access_token="token",
            graphql_endpoint=f"https://{SHOP}/admin/api/2025-01/graphql.json",
            graphql_headers={},
            snapshot_path=snapshot_file,
            plan="pro",
        )

    app.dependency_overrides[get_shop_context] = _fake_ctx
    with patch("app.api.llms_txt.load_business_profile", return_value=None):
        yield TestClient(app)
    app.dependency_overrides.pop(get_shop_context, None)


def test_generate_returns_payload_without_publishing(client, tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "raw"))
    resp = client.post(f"/api/shops/{SHOP}/llms-txt/generate")

    assert resp.status_code == 200
    body = resp.json()
    assert body["llms_txt"].startswith("# Léonie")
    assert body["summary"]["dry_run"] is True
    # Persisted to disk for later inspection.
    assert (tmp_path / "raw" / SHOP / "llms_txt.json").exists()


def test_generate_404_without_snapshot(snapshot_file: Path) -> None:
    missing = snapshot_file.parent / "does-not-exist.json"

    def _ctx() -> ShopContext:
        return ShopContext(SHOP, "token", "", {}, missing, "pro")

    app.dependency_overrides[get_shop_context] = _ctx
    try:
        with patch("app.api.llms_txt.load_snapshot_from_file_or_db", return_value=None):
            resp = TestClient(app).post(f"/api/shops/{SHOP}/llms-txt/generate")
    finally:
        app.dependency_overrides.pop(get_shop_context, None)
    assert resp.status_code == 404


def test_publish_delegates_to_publisher(client) -> None:
    stub = {"skipped": False, "cdn_url": "https://cdn/llms.txt", "public_url": "x"}
    with patch("app.api.llms_txt.publisher.publish", return_value=stub) as pub:
        resp = client.post(f"/api/shops/{SHOP}/llms-txt/publish")
    assert resp.status_code == 200
    assert resp.json() == stub
    assert pub.call_args.args[0] == SHOP


def test_publish_returns_502_on_theme_error(client) -> None:
    from app.apply.shopify_theme_files import ShopifyThemeError

    with patch("app.api.llms_txt.publisher.publish", side_effect=ShopifyThemeError("boom")):
        resp = client.post(f"/api/shops/{SHOP}/llms-txt/publish")
    assert resp.status_code == 502


def test_publish_returns_403_on_scope_error(client) -> None:
    from app.apply.shopify_theme_files import ShopifyThemeScopeError

    with patch(
        "app.api.llms_txt.publisher.publish",
        side_effect=ShopifyThemeScopeError("Reinstall the app to grant themes"),
    ):
        resp = client.post(f"/api/shops/{SHOP}/llms-txt/publish")
    assert resp.status_code == 403
    assert "Reinstall" in resp.json()["detail"]


def test_status_reports_unpublished_by_default(client) -> None:
    with patch("app.api.llms_txt.store.get_publication", return_value=None):
        out = client.get(f"/api/shops/{SHOP}/llms-txt/status")
    assert out.status_code == 200
    body = out.json()
    assert body["is_published"] is False
    assert body["public_url"] == f"https://{SHOP}/llms.txt"


def test_webhook_tick_requires_internal_secret() -> None:
    resp = TestClient(app).post(f"/api/shops/{SHOP}/llms-txt/webhook-tick", json={"shop": SHOP})
    assert resp.status_code == 403
