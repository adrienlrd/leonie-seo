"""Tests for the shop theme-extension entitlement sync."""

from __future__ import annotations

from unittest.mock import MagicMock

from app.apply.theme_entitlement import set_theme_entitlement

SHOP = "store.myshopify.com"


def _mock_responses(shop_id="gid://shopify/Shop/1", user_errors=None):
    shop_resp = MagicMock()
    shop_resp.json.return_value = {"data": {"shop": {"id": shop_id}}}
    shop_resp.raise_for_status.return_value = None
    set_resp = MagicMock()
    set_resp.json.return_value = {
        "data": {"metafieldsSet": {"metafields": [{"id": "1"}], "userErrors": user_errors or []}}
    }
    set_resp.raise_for_status.return_value = None
    return [shop_resp, set_resp]


def test_set_theme_entitlement_writes_boolean_metafield(mocker):
    mocker.patch(
        "app.apply.theme_entitlement.get_token", return_value={"access_token": "tok"}
    )
    post = mocker.patch(
        "app.apply.theme_entitlement.requests.post", side_effect=_mock_responses()
    )
    assert set_theme_entitlement(SHOP, False) is True
    # Second call is the metafieldsSet mutation.
    _, kwargs = post.call_args_list[1]
    metafield = kwargs["json"]["variables"]["metafields"][0]
    assert metafield["namespace"] == "leonie"
    assert metafield["key"] == "theme_entitled"
    assert metafield["type"] == "boolean"
    assert metafield["value"] == "false"
    assert metafield["ownerId"] == "gid://shopify/Shop/1"


def test_set_theme_entitlement_true_value(mocker):
    mocker.patch(
        "app.apply.theme_entitlement.get_token", return_value={"access_token": "tok"}
    )
    mocker.patch(
        "app.apply.theme_entitlement.requests.post", side_effect=_mock_responses()
    )
    assert set_theme_entitlement(SHOP, True) is True


def test_set_theme_entitlement_returns_false_without_token(mocker):
    mocker.patch("app.apply.theme_entitlement.get_token", return_value=None)
    post = mocker.patch("app.apply.theme_entitlement.requests.post")
    assert set_theme_entitlement(SHOP, True) is False
    post.assert_not_called()


def test_set_theme_entitlement_returns_false_on_user_errors(mocker):
    mocker.patch(
        "app.apply.theme_entitlement.get_token", return_value={"access_token": "tok"}
    )
    mocker.patch(
        "app.apply.theme_entitlement.requests.post",
        side_effect=_mock_responses(user_errors=[{"field": "ownerId", "message": "denied"}]),
    )
    assert set_theme_entitlement(SHOP, True) is False
