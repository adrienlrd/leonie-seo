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
    "INTERNAL_API_SECRET": "test-internal-secret",
    # Stay in dev auth mode (LEONIE_REQUIRE_SESSION_TOKEN unset → false).
    # All tests below send X-Leonie-Shop + X-Internal-Secret to authenticate.
}

SHOP = "store.myshopify.com"
_HEADERS_FOR = lambda shop: {  # noqa: E731
    "X-Leonie-Shop": shop,
    "X-Internal-Secret": "test-internal-secret",
}


@pytest.fixture()
def client():
    with patch.dict("os.environ", ENV):
        yield TestClient(app)


# ── POST /api/jobs ────────────────────────────────────────────────────────────


def test_enqueue_known_queue_returns_202(client):
    resp = client.post(
        "/api/jobs",
        json={"queue": "seo_audit"},
        headers=_HEADERS_FOR(SHOP),
    )
    assert resp.status_code == 202
    body = resp.json()
    assert "job_id" in body
    assert body["status"] == "pending"


def test_enqueue_unknown_queue_returns_400(client):
    resp = client.post(
        "/api/jobs",
        json={"queue": "does_not_exist"},
        headers=_HEADERS_FOR(SHOP),
    )
    assert resp.status_code == 400


def test_enqueue_without_auth_in_prod_mode_returns_401(client):
    """In production (LEONIE_REQUIRE_SESSION_TOKEN=true), no auth → 401."""
    with patch.dict("os.environ", {"LEONIE_REQUIRE_SESSION_TOKEN": "true"}):
        resp = client.post("/api/jobs", json={"queue": "seo_audit"})
    # Either 401 (no session token) or 403 (no fallback shop) — both are
    # acceptable "auth missing" responses. The point: no 202.
    assert resp.status_code in (401, 403)


def test_enqueue_wrong_internal_secret_returns_403(client):
    resp = client.post(
        "/api/jobs",
        json={"queue": "seo_audit"},
        headers={"X-Leonie-Shop": SHOP, "X-Internal-Secret": "wrong"},
    )
    assert resp.status_code == 403


def test_enqueue_scopes_to_authenticated_shop(client):
    """The job is always created for the authenticated shop, regardless of body."""
    resp = client.post(
        "/api/jobs",
        json={"queue": "seo_audit"},
        headers=_HEADERS_FOR(SHOP),
    )
    job_id = resp.json()["job_id"]
    detail = client.get(f"/api/jobs/{job_id}", headers=_HEADERS_FOR(SHOP)).json()
    assert detail["shop"] == SHOP


# ── GET /api/jobs/{job_id} ────────────────────────────────────────────────────


def test_get_job_status_returns_job(client):
    enqueue_resp = client.post(
        "/api/jobs",
        json={"queue": "seo_audit"},
        headers=_HEADERS_FOR(SHOP),
    )
    job_id = enqueue_resp.json()["job_id"]

    resp = client.get(f"/api/jobs/{job_id}", headers=_HEADERS_FOR(SHOP))
    assert resp.status_code == 200
    assert resp.json()["id"] == job_id
    assert resp.json()["queue"] == "seo_audit"


def test_get_job_status_unknown_returns_404(client):
    resp = client.get(
        "/api/jobs/00000000-0000-0000-0000-000000000000",
        headers=_HEADERS_FOR(SHOP),
    )
    assert resp.status_code == 404


def test_get_job_other_shop_returns_404(client):
    """A shop B must not be able to read shop A's job (no enumeration)."""
    enq = client.post(
        "/api/jobs",
        json={"queue": "seo_audit"},
        headers=_HEADERS_FOR("shop-a.myshopify.com"),
    )
    job_id = enq.json()["job_id"]

    resp = client.get(
        f"/api/jobs/{job_id}",
        headers=_HEADERS_FOR("shop-b.myshopify.com"),
    )
    assert resp.status_code == 404


# ── GET /api/shops/{shop}/jobs ────────────────────────────────────────────────


def test_list_shop_jobs_returns_jobs_for_shop(client):
    client.post("/api/jobs", json={"queue": "seo_audit"}, headers=_HEADERS_FOR(SHOP))
    client.post(
        "/api/jobs",
        json={"queue": "seo_audit"},
        headers=_HEADERS_FOR("other.myshopify.com"),
    )

    resp = client.get(f"/api/shops/{SHOP}/jobs", headers=_HEADERS_FOR(SHOP))

    assert resp.status_code == 200
    body = resp.json()
    assert body["shop"] == SHOP
    assert body["count"] >= 1
    for job in body["jobs"]:
        assert job["shop"] == SHOP


def test_list_shop_jobs_filters_by_status(client):
    client.post("/api/jobs", json={"queue": "seo_audit"}, headers=_HEADERS_FOR(SHOP))
    resp = client.get(
        f"/api/shops/{SHOP}/jobs?status=pending",
        headers=_HEADERS_FOR(SHOP),
    )
    assert resp.status_code == 200
    for job in resp.json()["jobs"]:
        assert job["status"] == "pending"


def test_list_shop_jobs_rejects_shop_mismatch(client):
    resp = client.get(
        f"/api/shops/{SHOP}/jobs",
        headers=_HEADERS_FOR("other.myshopify.com"),
    )
    assert resp.status_code == 403
