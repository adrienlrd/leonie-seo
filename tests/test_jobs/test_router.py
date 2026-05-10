"""Tests for job queue API endpoints."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import app

ENV = {
    "SHOPIFY_CLIENT_ID": "client_id",
    "SHOPIFY_CLIENT_SECRET": "test_secret",
    "SHOPIFY_SCOPES": "read_products",
    "APP_URL": "https://example.com",
}

SHOP = "store.myshopify.com"


@pytest.fixture()
def client():
    with patch.dict("os.environ", ENV):
        yield TestClient(app)


# ── POST /api/jobs ────────────────────────────────────────────────────────────


def test_enqueue_known_queue_returns_202(client):
    resp = client.post("/api/jobs", json={"queue": "seo_audit", "shop": SHOP})
    assert resp.status_code == 202
    body = resp.json()
    assert "job_id" in body
    assert body["status"] == "pending"


def test_enqueue_unknown_queue_returns_400(client):
    resp = client.post("/api/jobs", json={"queue": "does_not_exist"})
    assert resp.status_code == 400


# ── GET /api/jobs/{job_id} ────────────────────────────────────────────────────


def test_get_job_status_returns_job(client):
    enqueue_resp = client.post("/api/jobs", json={"queue": "seo_audit"})
    job_id = enqueue_resp.json()["job_id"]

    resp = client.get(f"/api/jobs/{job_id}")
    assert resp.status_code == 200
    assert resp.json()["id"] == job_id
    assert resp.json()["queue"] == "seo_audit"


def test_get_job_status_unknown_returns_404(client):
    resp = client.get("/api/jobs/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404


# ── GET /api/shops/{shop}/jobs ────────────────────────────────────────────────


def test_list_shop_jobs_returns_jobs_for_shop(client):
    client.post("/api/jobs", json={"queue": "seo_audit", "shop": SHOP})
    client.post("/api/jobs", json={"queue": "seo_audit", "shop": "other.myshopify.com"})

    resp = client.get(f"/api/shops/{SHOP}/jobs")
    assert resp.status_code == 200
    body = resp.json()
    assert body["shop"] == SHOP
    # At least the one we just created
    assert body["count"] >= 1
    for job in body["jobs"]:
        assert job["shop"] == SHOP


def test_list_shop_jobs_filters_by_status(client):
    client.post("/api/jobs", json={"queue": "seo_audit", "shop": SHOP})
    resp = client.get(f"/api/shops/{SHOP}/jobs?status=pending")
    assert resp.status_code == 200
    for job in resp.json()["jobs"]:
        assert job["status"] == "pending"
