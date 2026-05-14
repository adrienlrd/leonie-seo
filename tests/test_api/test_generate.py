"""Tests for LLM generation API endpoints."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import app

ENV = {
    "SHOPIFY_STORE_DOMAIN": "287c4a-bb.myshopify.com",
    "SHOPIFY_ACCESS_TOKEN": "shpat_test",
    "SHOPIFY_CLIENT_ID": "client_id",
    "SHOPIFY_CLIENT_SECRET": "client_secret",
    "SHOPIFY_SCOPES": "read_products",
    "APP_URL": "https://example.com",
}

SHOP = "287c4a-bb.myshopify.com"


@pytest.fixture()
def client():
    with patch.dict("os.environ", ENV):
        yield TestClient(app)


def test_enqueue_meta_generation_from_snapshot_queues_products(
    client: TestClient,
    tmp_path: Path,
    monkeypatch,
):
    snapshot = {
        "products": [
            {"id": "gid://shopify/Product/1", "title": "Harnais"},
            {"id": "gid://shopify/Product/2", "title": "Bol"},
        ]
    }
    snapshot_path = tmp_path / "shopify_snapshot.json"
    snapshot_path.write_text(json.dumps(snapshot), encoding="utf-8")
    enqueued: list[dict] = []

    def _enqueue(queue, payload, **kwargs):
        enqueued.append({"queue": queue, "payload": payload, **kwargs})
        return kwargs["job_id"]

    monkeypatch.setattr("app.api.generate.enqueue", _enqueue)

    with (
        patch("app.api.deps.get_token", return_value=None),
        patch("app.api.deps._SNAPSHOT_DEFAULT", snapshot_path),
    ):
        resp = client.post(
            f"/api/shops/{SHOP}/generate/meta/from-snapshot",
            json={"limit": 1, "max_workers": 2},
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["queued"] == 1
    assert enqueued[0]["queue"] == "meta_generation"
    assert enqueued[0]["payload"]["products"] == [snapshot["products"][0]]
    assert enqueued[0]["payload"]["max_workers"] == 2
    assert enqueued[0]["shop"] == SHOP


def test_enqueue_meta_generation_from_snapshot_returns_404_without_snapshot(
    client: TestClient,
    tmp_path: Path,
):
    with (
        patch("app.api.deps.get_token", return_value=None),
        patch("app.api.deps._SNAPSHOT_DEFAULT", tmp_path / "missing.json"),
    ):
        resp = client.post(f"/api/shops/{SHOP}/generate/meta/from-snapshot", json={})

    assert resp.status_code == 404
