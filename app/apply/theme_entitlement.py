"""Sync the shop-level theme-extension entitlement to Shopify.

The theme app embed (`faq_embed.liquid`) is a paid feature, but a theme block
cannot be removed automatically when a merchant downgrades. To revoke it we write
a shop metafield `leonie.theme_entitled`; the Liquid block suppresses its output
when that flag is explicitly ``false``. Absent flag = fail-open (never downgraded),
so existing paid merchants keep rendering until an explicit downgrade sets false.
"""

from __future__ import annotations

import logging

import requests

from app.oauth.token_store import get_token

logger = logging.getLogger(__name__)

_GRAPHQL_PATH = "/admin/api/2025-01/graphql.json"
_TIMEOUT = 20
_NAMESPACE = "leonie"
_KEY = "theme_entitled"

_SHOP_ID_QUERY = "{ shop { id } }"

_METAFIELDS_SET = """
mutation MetafieldsSet($metafields: [MetafieldsSetInput!]!) {
  metafieldsSet(metafields: $metafields) {
    metafields { id namespace key value }
    userErrors { field message code }
  }
}
"""


def _post(endpoint: str, token: str, query: str, variables: dict | None = None) -> dict:
    resp = requests.post(
        endpoint,
        headers={"X-Shopify-Access-Token": token, "Content-Type": "application/json"},
        json={"query": query, "variables": variables or {}},
        timeout=_TIMEOUT,
    )
    resp.raise_for_status()
    return resp.json()


def set_theme_entitlement(shop: str, entitled: bool) -> bool:
    """Write the shop's theme-extension entitlement flag. Returns True on success.

    Best-effort: logs and returns False on any failure rather than raising, so a
    webhook or redeem flow is never broken by a metafield write hiccup.
    """
    token_record = get_token(shop)
    if not token_record:
        logger.warning("theme_entitlement: no OAuth token for %s", shop)
        return False

    endpoint = f"https://{shop}{_GRAPHQL_PATH}"
    token = token_record["access_token"]

    try:
        shop_data = _post(endpoint, token, _SHOP_ID_QUERY)
        shop_gid = ((shop_data.get("data") or {}).get("shop") or {}).get("id")
        if not shop_gid:
            logger.warning("theme_entitlement: could not resolve shop GID for %s", shop)
            return False

        variables = {
            "metafields": [
                {
                    "ownerId": shop_gid,
                    "namespace": _NAMESPACE,
                    "key": _KEY,
                    "type": "boolean",
                    "value": "true" if entitled else "false",
                }
            ]
        }
        data = _post(endpoint, token, _METAFIELDS_SET, variables)
    except requests.RequestException as exc:
        logger.warning("theme_entitlement: write failed for %s: %s", shop, exc)
        return False

    user_errors = (data.get("data") or {}).get("metafieldsSet", {}).get("userErrors") or []
    if user_errors:
        msg = "; ".join(f"{e.get('field')}: {e.get('message')}" for e in user_errors)
        logger.warning("theme_entitlement: userErrors for %s: %s", shop, msg)
        return False

    logger.info("theme_entitlement: shop=%s entitled=%s", shop, entitled)
    return True
