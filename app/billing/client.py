"""Shopify Billing API GraphQL client — appSubscriptionCreate / Cancel."""

from __future__ import annotations

import httpx

_API_VERSION = "2025-01"

# Pricing catalog — Free has no Shopify charge (default plan on install).
# Prices are EUR; when the shop's billing currency is not EUR the Billing API
# only accepts USD, so each plan carries a USD fallback (see _resolve_price).
TRIAL_DAYS = 7

BILLING_PLANS: dict[str, dict] = {
    "pro": {
        "display_name": "GEO Pro",
        "price": "18.99",
        "currency": "EUR",
        "price_usd": "21.99",
        "interval": "EVERY_30_DAYS",
        "features": ["15 products", "5 analyses / 28 days", "20 blogs / 28 days", "Auto-analysis"],
    },
    "agency": {
        "display_name": "GEO Grande boutique",
        "price": "45.00",
        "currency": "EUR",
        "price_usd": "52.00",
        "interval": "EVERY_30_DAYS",
        "features": ["35 products", "10 analyses / 28 days", "40 blogs / 28 days", "Auto-analysis"],
    },
}

_BILLING_PREFERENCES_QUERY = """
query {
  shopBillingPreferences { currency }
}
"""

_CREATE_MUTATION = """
mutation appSubscriptionCreate(
  $name: String!
  $returnUrl: String!
  $trialDays: Int
  $lineItems: [AppSubscriptionLineItemInput!]!
) {
  appSubscriptionCreate(name: $name, returnUrl: $returnUrl, trialDays: $trialDays, lineItems: $lineItems) {
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


def _resolve_price(shop: str, access_token: str, cfg: dict) -> tuple[str, str]:
    """Pick the charge amount/currency for a plan.

    The Billing API only accepts the merchant's billing currency or USD, so we
    charge EUR when the shop bills in EUR and fall back to USD otherwise.
    """
    try:
        data = _graphql(shop, access_token, _BILLING_PREFERENCES_QUERY)
        merchant_currency = (data.get("shopBillingPreferences") or {}).get("currency")
    except (BillingError, httpx.HTTPError):
        merchant_currency = None
    if merchant_currency == cfg["currency"]:
        return cfg["price"], cfg["currency"]
    return cfg["price_usd"], "USD"


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
    amount, currency = _resolve_price(shop, access_token, cfg)
    variables = {
        "name": cfg["display_name"],
        "returnUrl": return_url,
        "trialDays": TRIAL_DAYS,
        "lineItems": [
            {
                "plan": {
                    "appRecurringPricingDetails": {
                        "price": {"amount": amount, "currencyCode": currency},
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
