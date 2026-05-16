"""Tests for PageSpeed configure endpoint and shop_config_store."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import app

SHOP = "287c4a-bb.myshopify.com"

ENV = {
    "SHOPIFY_STORE_DOMAIN": SHOP,
    "SHOPIFY_ACCESS_TOKEN": "shpat_test",
    "SHOPIFY_CLIENT_ID": "client_id",
    "SHOPIFY_CLIENT_SECRET": "client_secret",
    "SHOPIFY_SCOPES": "read_products",
    "APP_URL": "https://example.com",
}


@pytest.fixture()
def client():
    with patch.dict("os.environ", ENV):
        yield TestClient(app)


def test_pagespeed_configure_stores_key(client: TestClient, tmp_path) -> None:
    stored: dict = {}

    def _set(shop: str, key: str, value: str) -> None:
        stored[(shop, key)] = value

    def _get(shop: str, key: str) -> str | None:
        return stored.get((shop, key))

    with (
        patch("app.api.deps.get_token", return_value=None),
        patch("app.api.pagespeed.set_shop_config", side_effect=_set),
        patch("app.api.pagespeed.get_shop_config", side_effect=_get),
    ):
        resp = client.post(
            f"/api/shops/{SHOP}/pagespeed/configure",
            json={"api_key": "AIzaSy_test_key"},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["configured"] is True
    assert data["key_source"] == "db"
    assert stored.get((SHOP, "pagespeed_api_key")) == "AIzaSy_test_key"


def test_pagespeed_configure_rejects_empty_key(client: TestClient) -> None:
    with patch("app.api.deps.get_token", return_value=None):
        resp = client.post(
            f"/api/shops/{SHOP}/pagespeed/configure",
            json={"api_key": ""},
        )
    assert resp.status_code == 422


def test_pagespeed_status_shows_key_source(client: TestClient) -> None:
    with (
        patch("app.api.deps.get_token", return_value=None),
        patch("app.api.pagespeed.get_shop_config", return_value="AIzaSy_from_db"),
        patch.dict("os.environ", {"PAGESPEED_API_KEY": ""}, clear=False),
    ):
        resp = client.get(f"/api/shops/{SHOP}/pagespeed/status")

    assert resp.status_code == 200
    data = resp.json()
    assert data["configured"] is True
    assert data["key_source"] == "db"


def test_pagespeed_status_no_key_still_ok(client: TestClient) -> None:
    import os

    with (
        patch("app.api.deps.get_token", return_value=None),
        patch("app.api.pagespeed.get_shop_config", return_value=None),
        patch.dict("os.environ", ENV),
    ):
        os.environ.pop("PAGESPEED_API_KEY", None)
        resp = client.get(f"/api/shops/{SHOP}/pagespeed/status")

    assert resp.status_code == 200
    data = resp.json()
    assert data["key_source"] is None
