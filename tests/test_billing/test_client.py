"""Tests for Shopify Billing API GraphQL client."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.billing.client import BillingError, cancel_subscription, create_subscription

SHOP = "store.myshopify.com"
TOKEN = "shpat_test"
SUB_GID = "gid://shopify/AppSubscription/42"


def _mock_response(data: dict) -> MagicMock:
    mock = MagicMock()
    mock.raise_for_status.return_value = None
    mock.json.return_value = {"data": data}
    return mock


def test_create_subscription_returns_confirmation_url(monkeypatch):
    mock_post = MagicMock(
        return_value=_mock_response(
            {
                "appSubscriptionCreate": {
                    "userErrors": [],
                    "confirmationUrl": "https://partners.shopify.com/confirm",
                    "appSubscription": {"id": SUB_GID, "status": "PENDING"},
                }
            }
        )
    )
    monkeypatch.setattr("app.billing.client.httpx.post", mock_post)
    result = create_subscription(SHOP, TOKEN, "pro", "https://myapp.com/confirm")
    assert result["confirmation_url"] == "https://partners.shopify.com/confirm"
    assert result["subscription_id"] == SUB_GID


def test_create_subscription_unknown_plan_raises():
    with pytest.raises(BillingError, match="Unknown plan"):
        create_subscription(SHOP, TOKEN, "enterprise", "https://myapp.com/confirm")


def test_create_subscription_user_errors_raises(monkeypatch):
    mock_post = MagicMock(
        return_value=_mock_response(
            {
                "appSubscriptionCreate": {
                    "userErrors": [{"field": "name", "message": "Already exists"}],
                    "confirmationUrl": None,
                    "appSubscription": None,
                }
            }
        )
    )
    monkeypatch.setattr("app.billing.client.httpx.post", mock_post)
    with pytest.raises(BillingError):
        create_subscription(SHOP, TOKEN, "pro", "https://myapp.com/confirm")


def test_cancel_subscription_returns_cancelled(monkeypatch):
    mock_post = MagicMock(
        return_value=_mock_response(
            {
                "appSubscriptionCancel": {
                    "userErrors": [],
                    "appSubscription": {"id": SUB_GID, "status": "CANCELLED"},
                }
            }
        )
    )
    monkeypatch.setattr("app.billing.client.httpx.post", mock_post)
    status = cancel_subscription(SHOP, TOKEN, SUB_GID)
    assert status == "cancelled"


def test_cancel_subscription_user_errors_raises(monkeypatch):
    mock_post = MagicMock(
        return_value=_mock_response(
            {
                "appSubscriptionCancel": {
                    "userErrors": [{"field": "id", "message": "Not found"}],
                    "appSubscription": None,
                }
            }
        )
    )
    monkeypatch.setattr("app.billing.client.httpx.post", mock_post)
    with pytest.raises(BillingError):
        cancel_subscription(SHOP, TOKEN, SUB_GID)


def test_graphql_errors_raises(monkeypatch):
    mock = MagicMock()
    mock.raise_for_status.return_value = None
    mock.json.return_value = {"errors": [{"message": "Unauthorized"}]}
    monkeypatch.setattr("app.billing.client.httpx.post", mock)
    with pytest.raises(BillingError):
        create_subscription(SHOP, TOKEN, "pro", "https://myapp.com/confirm")
