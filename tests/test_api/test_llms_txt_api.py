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


@pytest.fixture(autouse=True)
def _isolated_db(tmp_path: Path, monkeypatch) -> None:
    """Point the default DB at a fresh per-test SQLite file (no cross-test bleed)."""
    from app.db import init_db

    db = tmp_path / "history.db"
    monkeypatch.setattr("app.db_adapter.DB_PATH", db)
    init_db(db)


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


def test_publish_delegates_to_publisher(client, monkeypatch) -> None:
    monkeypatch.setenv("LEONIE_THEME_WRITE_MODE", "review_safe")
    stub = {"skipped": False, "cdn_url": "https://cdn/llms.txt", "public_url": "x"}
    with patch("app.api.llms_txt.publisher.publish", return_value=stub) as pub:
        resp = client.post(f"/api/shops/{SHOP}/llms-txt/publish?confirm=true")
    assert resp.status_code == 200
    assert resp.json() == stub
    assert pub.call_args.args[0] == SHOP
    # The publish is recorded as an explicit merchant action.
    assert pub.call_args.kwargs["user_action"] is True


def test_publish_requires_confirmation(client, monkeypatch) -> None:
    monkeypatch.setenv("LEONIE_THEME_WRITE_MODE", "review_safe")
    with patch("app.api.llms_txt.publisher.publish") as pub:
        resp = client.post(f"/api/shops/{SHOP}/llms-txt/publish")
    assert resp.status_code == 409
    pub.assert_not_called()  # never publishes without explicit confirmation


def test_publish_blocked_when_mode_disabled(client, monkeypatch) -> None:
    monkeypatch.setenv("LEONIE_THEME_WRITE_MODE", "disabled")
    with patch("app.api.llms_txt.publisher.publish") as pub:
        resp = client.post(f"/api/shops/{SHOP}/llms-txt/publish?confirm=true")
    assert resp.status_code == 403
    pub.assert_not_called()


def test_publish_returns_502_on_theme_error(client, monkeypatch) -> None:
    from app.apply.shopify_theme_files import ShopifyThemeError

    monkeypatch.setenv("LEONIE_THEME_WRITE_MODE", "review_safe")
    with patch("app.api.llms_txt.publisher.publish", side_effect=ShopifyThemeError("boom")):
        resp = client.post(f"/api/shops/{SHOP}/llms-txt/publish?confirm=true")
    assert resp.status_code == 502


def test_publish_returns_403_on_scope_error(client, monkeypatch) -> None:
    from app.apply.shopify_theme_files import ShopifyThemeScopeError

    monkeypatch.setenv("LEONIE_THEME_WRITE_MODE", "review_safe")
    with patch(
        "app.api.llms_txt.publisher.publish",
        side_effect=ShopifyThemeScopeError("Reinstall the app to grant themes"),
    ):
        resp = client.post(f"/api/shops/{SHOP}/llms-txt/publish?confirm=true")
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


def test_webhook_tick_skips_when_not_published(monkeypatch) -> None:
    monkeypatch.setenv("INTERNAL_API_SECRET", "s3cret")
    monkeypatch.setattr("app.api.llms_txt.get_token", lambda shop: {"access_token": "t"})
    monkeypatch.setattr(
        "app.api.llms_txt.publisher.should_regenerate",
        lambda shop: (False, "not_published"),
    )
    resp = TestClient(app).post(
        f"/api/shops/{SHOP}/llms-txt/webhook-tick",
        json={"shop": SHOP},
        headers={"X-Internal-Secret": "s3cret"},
    )
    assert resp.status_code == 200
    assert resp.json() == {"regenerated": False, "reason": "not_published"}


def test_webhook_tick_schedules_recrawl_and_republish(monkeypatch) -> None:
    monkeypatch.setenv("INTERNAL_API_SECRET", "s3cret")
    monkeypatch.setenv("LEONIE_THEME_WRITE_MODE", "review_safe")
    monkeypatch.setattr("app.api.llms_txt.get_token", lambda shop: {"access_token": "tok"})
    monkeypatch.setattr(
        "app.api.llms_txt.publisher.should_regenerate", lambda shop: (True, "regenerate")
    )
    captured: dict = {}

    async def fake_regen(shop, token):
        captured["shop"] = shop
        captured["token"] = token

    monkeypatch.setattr("app.api.llms_txt._regenerate_published", fake_regen)

    resp = TestClient(app).post(
        f"/api/shops/{SHOP}/llms-txt/webhook-tick",
        json={"shop": SHOP},
        headers={"X-Internal-Secret": "s3cret"},
    )

    assert resp.status_code == 200
    assert resp.json() == {"regenerated": True, "reason": "scheduled"}
    # Background task ran the re-crawl + republish.
    assert captured == {"shop": SHOP, "token": "tok"}


def test_webhook_tick_does_not_write_when_mode_disabled(monkeypatch) -> None:
    """A catalogue webhook must never write to the theme while disabled."""
    monkeypatch.setenv("INTERNAL_API_SECRET", "s3cret")
    monkeypatch.setenv("LEONIE_THEME_WRITE_MODE", "disabled")
    monkeypatch.setattr("app.api.llms_txt.get_token", lambda shop: {"access_token": "tok"})
    monkeypatch.setattr(
        "app.api.llms_txt.publisher.should_regenerate", lambda shop: (True, "regenerate")
    )

    def _fail_regen(*a, **k):  # pragma: no cover - must never be scheduled
        raise AssertionError("regeneration must not run while disabled")

    monkeypatch.setattr("app.api.llms_txt._regenerate_published", _fail_regen)
    logged: dict = {}
    monkeypatch.setattr(
        "app.api.llms_txt.store.log_theme_write",
        lambda shop, **kw: logged.update({"shop": shop, **kw}),
    )

    resp = TestClient(app).post(
        f"/api/shops/{SHOP}/llms-txt/webhook-tick",
        json={"shop": SHOP},
        headers={"X-Internal-Secret": "s3cret"},
    )

    assert resp.status_code == 200
    assert resp.json() == {"regenerated": False, "reason": "theme_write_disabled"}
    assert logged["action"] == "regeneration_pending"


def test_get_crawler_prefs_returns_defaults(client) -> None:
    resp = client.get(f"/api/shops/{SHOP}/llms-txt/crawler-prefs")
    assert resp.status_code == 200
    body = resp.json()
    assert body["crawler_prefs"]["include_products"] is True
    assert "GPTBot" in body["known_agents"]


def test_put_crawler_prefs_persists_and_normalises(client, tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "raw"))
    resp = client.put(
        f"/api/shops/{SHOP}/llms-txt/crawler-prefs",
        json={
            "include_products": False,
            "include_collections": True,
            "include_pages": True,
            "welcomed_agents": ["GPTBot", "EvilBot"],
        },
    )
    assert resp.status_code == 200
    prefs = resp.json()["crawler_prefs"]
    assert prefs["include_products"] is False
    assert prefs["welcomed_agents"] == ["GPTBot"]  # unknown agent dropped

    # Persisted: a follow-up GET reflects it.
    again = client.get(f"/api/shops/{SHOP}/llms-txt/crawler-prefs").json()
    assert again["crawler_prefs"]["include_products"] is False
