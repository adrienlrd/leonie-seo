"""Tests for brand name repair when serving stored business profiles."""

from __future__ import annotations

from pathlib import Path

from app.api import business_profile as bp
from app.api.deps import ShopContext


def _ctx() -> ShopContext:
    return ShopContext(
        shop="leonie.myshopify.com",
        access_token="token",
        graphql_endpoint="https://example/graphql",
        graphql_headers={},
        snapshot_path=Path("/tmp/does-not-exist.json"),
    )


def test_repair_brand_name_when_placeholder(monkeypatch):
    monkeypatch.setattr(bp, "_load_snapshot_safe", lambda ctx: {"shop": {"name": "Léonie Delacroix"}})
    repaired = bp._repair_brand_name({"brand_name": "Non spécifié"}, _ctx())
    assert repaired["brand_name"] == "Léonie Delacroix"


def test_repair_brand_name_when_empty(monkeypatch):
    monkeypatch.setattr(bp, "_load_snapshot_safe", lambda ctx: {"shop": {"name": "Léonie Delacroix"}})
    repaired = bp._repair_brand_name({"brand_name": ""}, _ctx())
    assert repaired["brand_name"] == "Léonie Delacroix"


def test_repair_keeps_existing_brand_name(monkeypatch):
    called = False

    def _fail(ctx):
        nonlocal called
        called = True
        return {}

    monkeypatch.setattr(bp, "_load_snapshot_safe", _fail)
    repaired = bp._repair_brand_name({"brand_name": "Léonie Delacroix"}, _ctx())
    assert repaired["brand_name"] == "Léonie Delacroix"
    assert called is False
