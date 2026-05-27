"""Tests for the FAQ auto-sync to Shopify metafield."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from app.apply import apply_faq


def _ok_response() -> MagicMock:
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {
        "data": {"metafieldsSet": {"metafields": [{"id": "gid://m/1"}], "userErrors": []}}
    }
    resp.raise_for_status.return_value = None
    return resp


def test_apply_faq_skips_when_empty():
    out = apply_faq.apply_faq_to_shopify("shop.myshopify.com", "gid://shopify/Product/1", [])
    assert out["applied"] is False
    assert out["error"] == "empty FAQ"
    assert out["entry_count"] == 0


def test_apply_faq_skips_when_shop_not_installed():
    with patch.object(apply_faq, "get_token", return_value=None):
        out = apply_faq.apply_faq_to_shopify(
            "shop.myshopify.com",
            "gid://shopify/Product/1",
            [{"q": "Q?", "a": "A."}],
        )
    assert out["applied"] is False
    assert "not installed" in out["error"]


def test_apply_faq_writes_metafield_with_cleaned_entries(tmp_path):
    captured: dict = {}

    def _fake_post(url, headers=None, json=None, timeout=None):  # noqa: A002, ARG001
        captured["url"] = url
        captured["headers"] = headers
        captured["payload"] = json
        return _ok_response()

    with (
        patch.object(apply_faq, "get_token", return_value={"access_token": "shpat_xxx"}),
        patch.object(apply_faq, "requests") as fake_requests,
        patch.object(apply_faq, "_DATA_DIR", tmp_path),
    ):
        fake_requests.post.side_effect = _fake_post
        fake_requests.RequestException = Exception
        out = apply_faq.apply_faq_to_shopify(
            "shop.myshopify.com",
            "gid://shopify/Product/42",
            [
                {"q": "Comment l'utiliser ?", "a": "Branchez-le sur USB."},
                {"q": "", "a": "ignored"},  # dropped by _normalize_faq
                {"q": "Garantie ?", "a": " 2 ans. "},
            ],
        )

    assert out["applied"] is True
    assert out["entry_count"] == 2
    assert out["applied_at"]

    metafield = captured["payload"]["variables"]["metafields"][0]
    assert metafield["namespace"] == "leonie"
    assert metafield["key"] == "faq"
    assert metafield["type"] == "json"
    assert metafield["ownerId"] == "gid://shopify/Product/42"
    parsed = json.loads(metafield["value"])
    assert parsed == [
        {"q": "Comment l'utiliser ?", "a": "Branchez-le sur USB."},
        {"q": "Garantie ?", "a": "2 ans."},
    ]
    assert captured["headers"]["X-Shopify-Access-Token"] == "shpat_xxx"

    snapshot = tmp_path / "shop.myshopify.com" / "applied_faqs" / "gid:__shopify_Product_42.json"
    assert snapshot.exists()


def test_apply_faq_returns_error_on_shopify_user_errors():
    bad = MagicMock()
    bad.status_code = 200
    bad.json.return_value = {
        "data": {
            "metafieldsSet": {
                "metafields": [],
                "userErrors": [{"field": ["value"], "message": "Invalid JSON"}],
            }
        }
    }
    bad.raise_for_status.return_value = None

    with (
        patch.object(apply_faq, "get_token", return_value={"access_token": "shpat_xxx"}),
        patch.object(apply_faq, "requests") as fake_requests,
    ):
        fake_requests.post.return_value = bad
        fake_requests.RequestException = Exception
        out = apply_faq.apply_faq_to_shopify(
            "shop.myshopify.com",
            "gid://shopify/Product/1",
            [{"q": "Q?", "a": "A."}],
        )

    assert out["applied"] is False
    assert "Invalid JSON" in out["error"]
