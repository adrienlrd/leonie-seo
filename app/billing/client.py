"""Shopify Billing API GraphQL client — appSubscriptionCreate / Cancel."""

from __future__ import annotations

import httpx

_API_VERSION = "2025-01"

# Pricing catalog — Free has no Shopify charge (default plan on install).
BILLING_PLANS: dict[str, dict] = {
    "pro": {
        "display_name": "Giulio Geo Pro",
        "price": "29.00",
        "currency": "USD",
        "interval": "EVERY_30_DAYS",
        "features": ["Audit", "Apply meta/alt", "Reports", "Email alerts", "1 store"],
    },
    "agency": {
        "display_name": "Giulio Geo Agency",
        "price": "99.00",
        "currency": "USD",
        "interval": "EVERY_30_DAYS",
        "features": ["All Pro features", "Unlimited stores", "Priority support"],
    },
}

_CREATE_MUTATION = """
mutation appSubscriptionCreate(
  $name: String!
  $returnUrl: String!
  $lineItems: [AppSubscriptionLineItemInput!]!
) {
  appSubscriptionCreate(name: $name, returnUrl: $returnUrl, lineItems: $lineItems) {
    userErrors { field message }
    confirmationUrl
    appSubscription { id status }
  }
}
"""

_CANCEL_MUTATION = """
mutation appSubscriptionCancel($id: ID!) {
  appSubscriptionCancel(id: $id) {
    userErrors { field message }
    appSubscription { id status }
  }
}
"""

_ACTIVE_SUBSCRIPTIONS_QUERY = """
query {
  currentAppInstallation {
    activeSubscriptions { id name status }
  }
}
"""


class BillingError(Exception):
    """Raised when a Billing API call fails or returns user errors."""


def _graphql(shop: str, token: str, query: str, variables: dict | None = None) -> dict:
    url = f"https://{shop}/admin/api/{_API_VERSION}/graphql.json"
    resp = httpx.post(
        url,
        json={"query": query, "variables": variables or {}},
        headers={"X-Shopify-Access-Token": token, "Content-Type": "application/json"},
        timeout=30,
    )
    resp.raise_for_status()
    payload = resp.json()
    if "errors" in payload:
        raise BillingError(str(payload["errors"]))
    return payload["data"]


def create_subscription(shop: str, access_token: str, plan: str, return_url: str) -> dict[str, str]:
    """Create a recurring app subscription and return confirmation details.

    Args:
        shop: Shopify shop domain.
        access_token: OAuth access token for the shop.
        plan: "pro" or "agency".
        return_url: URL Shopify redirects to after merchant approves.

    Returns:
        Dict with "confirmation_url" and "subscription_id".

    Raises:
        BillingError: If the plan is unknown or Shopify returns errors.
    """
    if plan not in BILLING_PLANS:
        raise BillingError(f"Unknown plan '{plan}'. Must be one of: {list(BILLING_PLANS)}")

    cfg = BILLING_PLANS[plan]
    variables = {
        "name": cfg["display_name"],
        "returnUrl": return_url,
        "lineItems": [
            {
                "plan": {
                    "appRecurringPricingDetails": {
                        "price": {"amount": cfg["price"], "currencyCode": cfg["currency"]},
                        "interval": cfg["interval"],
                    }
                }
            }
        ],
    }
    data = _graphql(shop, access_token, _CREATE_MUTATION, variables)
    result = data["appSubscriptionCreate"]
    if result["userErrors"]:
        raise BillingError(str(result["userErrors"]))

    return {
        "confirmation_url": result["confirmationUrl"],
        "subscription_id": result["appSubscription"]["id"],
    }


def cancel_subscription(shop: str, access_token: str, subscription_id: str) -> str:
    """Cancel an active subscription.

    Returns:
        The new status string (lowercase).

    Raises:
        BillingError: If Shopify returns errors.
    """
    data = _graphql(shop, access_token, _CANCEL_MUTATION, {"id": subscription_id})
    result = data["appSubscriptionCancel"]
    if result["userErrors"]:
        raise BillingError(str(result["userErrors"]))
    return result["appSubscription"]["status"].lower()


def get_active_subscriptions(shop: str, access_token: str) -> list[dict]:
    """Return all active subscriptions for the current app installation."""
    data = _graphql(shop, access_token, _ACTIVE_SUBSCRIPTIONS_QUERY)
    return data["currentAppInstallation"]["activeSubscriptions"]
