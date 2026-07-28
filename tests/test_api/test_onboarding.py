"""API tests for the onboarding status / step endpoints."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.api.deps import ShopContext, get_shop_context
from app.main import app

SHOP = "shop.myshopify.com"

_VALIDATED = {"status": "validated"}
_DRAFT = {"status": "draft"}


@pytest.fixture(autouse=True)
def _isolated_db(tmp_path: Path, monkeypatch) -> None:
    from app.db import init_db

    db = tmp_path / "history.db"
    monkeypatch.setattr("app.db_adapter.DB_PATH", db)
    # shop_config_store binds DB_PATH at import time, so patching the adapter
    # alone would leave it writing to the real data/history.db.
    monkeypatch.setattr("app.shop_config_store.DB_PATH", db)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    init_db(db)


@pytest.fixture()
def client(tmp_path: Path):
    def _fake_ctx() -> ShopContext:
        return ShopContext(
            shop=SHOP,
            access_token="token",
            graphql_endpoint=f"https://{SHOP}/admin/api/2025-01/graphql.json",
            graphql_headers={},
            snapshot_path=tmp_path / "shopify_snapshot.json",
            plan="free",
        )

    app.dependency_overrides[get_shop_context] = _fake_ctx
    yield TestClient(app)
    app.dependency_overrides.pop(get_shop_context, None)


def _state(client, *, profile, analysis):
    with (
        patch("app.api.onboarding.load_business_profile", return_value=profile),
        patch("app.api.onboarding.load_latest_result", return_value=analysis),
    ):
        resp = client.get(f"/api/shops/{SHOP}/onboarding/status")
    assert resp.status_code == 200
    return resp.json()


def test_status_is_complete_when_profile_validated_and_analysis_exists(client) -> None:
    assert _state(client, profile=_VALIDATED, analysis={"products": []})["complete"] is True


def test_status_is_incomplete_when_analysis_is_missing(client) -> None:
    """The dashboard used to check the profile alone — that drift is the bug."""
    assert _state(client, profile=_VALIDATED, analysis=None)["complete"] is False


def test_status_is_incomplete_when_profile_is_not_validated(client) -> None:
    assert _state(client, profile=_DRAFT, analysis={"products": []})["complete"] is False


@pytest.mark.parametrize(
    ("profile", "expected"),
    [(None, 1), (_DRAFT, 2), (_VALIDATED, 3)],
)
def test_step_floor_is_derived_from_the_business_profile(client, profile, expected) -> None:
    assert _state(client, profile=profile, analysis=None)["step"] == expected


def test_persisted_step_wins_over_the_derived_floor(client) -> None:
    client.put(f"/api/shops/{SHOP}/onboarding/step", json={"step": 5})

    assert _state(client, profile=_VALIDATED, analysis=None)["step"] == 5


def test_step_never_moves_backwards(client) -> None:
    client.put(f"/api/shops/{SHOP}/onboarding/step", json={"step": 5})
    resp = client.put(f"/api/shops/{SHOP}/onboarding/step", json={"step": 2})

    assert resp.json()["step"] == 5


def test_step_is_clamped_to_the_known_range(client) -> None:
    assert client.put(f"/api/shops/{SHOP}/onboarding/step", json={"step": 99}).json()["step"] == 6
