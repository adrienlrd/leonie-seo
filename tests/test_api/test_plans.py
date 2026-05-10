"""Tests for app.api.plans — plan resolution and feature gates."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.api.plans import get_active_plan, get_features, plan_summary
from app.main import app
from scripts.license import issue_key

_SECRET = "test-secret-xyz"
_TENANT = "testshop"
_ENV = {
    "SHOPIFY_STORE_DOMAIN": "287c4a-bb.myshopify.com",
    "SHOPIFY_ACCESS_TOKEN": "shpat_test",
    "SHOPIFY_CLIENT_ID": "client_id",
    "SHOPIFY_CLIENT_SECRET": "client_secret",
    "SHOPIFY_SCOPES": "read_products",
    "APP_URL": "https://example.com",
}


# ── get_features ──────────────────────────────────────────────────────────


def test_get_features_free_disables_apply():
    assert get_features("free").can_apply is False


def test_get_features_free_limits_shops_to_one():
    assert get_features("free").max_shops == 1


def test_get_features_pro_enables_apply():
    assert get_features("pro").can_apply is True


def test_get_features_agency_has_unlimited_shops():
    assert get_features("agency").max_shops is None


def test_get_features_unknown_plan_falls_back_to_free():
    assert get_features("unknown").can_apply is False


# ── get_active_plan ───────────────────────────────────────────────────────


def test_get_active_plan_no_key_returns_pro(monkeypatch):
    monkeypatch.delenv("LEONIE_API_KEY", raising=False)
    assert get_active_plan() == "pro"


def test_get_active_plan_pro_key_returns_pro(monkeypatch):
    k = issue_key(_TENANT, 365, _SECRET, plan="pro")
    monkeypatch.setenv("LEONIE_API_KEY", k)
    monkeypatch.setenv("LICENSE_SECRET", _SECRET)
    assert get_active_plan() == "pro"


def test_get_active_plan_agency_key_returns_agency(monkeypatch):
    k = issue_key(_TENANT, 365, _SECRET, plan="agency")
    monkeypatch.setenv("LEONIE_API_KEY", k)
    monkeypatch.setenv("LICENSE_SECRET", _SECRET)
    assert get_active_plan() == "agency"


def test_get_active_plan_free_key_returns_free(monkeypatch):
    k = issue_key(_TENANT, 365, _SECRET, plan="free")
    monkeypatch.setenv("LEONIE_API_KEY", k)
    monkeypatch.setenv("LICENSE_SECRET", _SECRET)
    assert get_active_plan() == "free"


def test_get_active_plan_invalid_key_returns_free(monkeypatch):
    monkeypatch.setenv("LEONIE_API_KEY", "LEO-invalid")
    assert get_active_plan() == "free"


def test_get_active_plan_expired_key_returns_free(monkeypatch):
    k = issue_key(_TENANT, -1, _SECRET, plan="pro")
    monkeypatch.setenv("LEONIE_API_KEY", k)
    assert get_active_plan() == "free"


# ── plan_summary ──────────────────────────────────────────────────────────


def test_plan_summary_includes_plan_name():
    s = plan_summary("pro")
    assert s["plan"] == "pro"


def test_plan_summary_includes_can_apply():
    assert plan_summary("free")["can_apply"] is False
    assert plan_summary("pro")["can_apply"] is True


# ── require_feature API gate ──────────────────────────────────────────────


@pytest.fixture()
def client():
    with patch.dict("os.environ", _ENV):
        yield TestClient(app)


def test_apply_meta_blocked_on_free_plan(client: TestClient):
    with (
        patch("app.api.deps.get_token", return_value=None),
        patch("app.api.deps.get_plan_for_shop", return_value="free"),
    ):
        resp = client.post(
            "/api/shops/287c4a-bb.myshopify.com/apply/meta",
            json=[{"product_id": "gid://shopify/Product/1", "title": "T"}],
        )
    assert resp.status_code == 403
    assert "Pro" in resp.json()["detail"] or "pro" in resp.json()["detail"].lower()


def test_apply_meta_allowed_on_pro_plan(client: TestClient):
    with (
        patch("app.api.deps.get_token", return_value=None),
        patch("app.api.deps.get_plan_for_shop", return_value="pro"),
    ):
        resp = client.post(
            "/api/shops/287c4a-bb.myshopify.com/apply/meta",
            json=[{"product_id": "gid://shopify/Product/1", "title": "T"}],
            params={"dry_run": "true"},
        )
    assert resp.status_code == 200
    assert resp.json()[0]["status"] == "preview"


def test_apply_meta_allowed_on_agency_plan(client: TestClient):
    with (
        patch("app.api.deps.get_token", return_value=None),
        patch("app.api.deps.get_plan_for_shop", return_value="agency"),
    ):
        resp = client.post(
            "/api/shops/287c4a-bb.myshopify.com/apply/meta",
            json=[{"product_id": "gid://shopify/Product/1", "title": "T"}],
            params={"dry_run": "true"},
        )
    assert resp.status_code == 200


def test_shop_status_includes_plan(client: TestClient, tmp_path):
    snap = tmp_path / "snap.json"
    snap.write_text('{"products": [], "collections": []}')
    with (
        patch("app.api.deps.get_token", return_value=None),
        patch("app.api.deps._SNAPSHOT_DEFAULT", snap),
        patch("app.api.deps.get_plan_for_shop", return_value="agency"),
    ):
        resp = client.get("/api/shops/287c4a-bb.myshopify.com/status")
    assert resp.status_code == 200
    body = resp.json()
    assert body["plan"] == "agency"
    assert body["can_apply"] is True
    assert body["max_shops"] is None
