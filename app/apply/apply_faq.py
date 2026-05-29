"""Auto-sync product FAQ to a Shopify metafield used by the storefront block.

Writes the FAQ proposed by the market-analysis Pass 2 to a JSON metafield
`leonie.faq` on the product. The companion Liquid block (extension
`leonie-seo-jsonld/blocks/faq_block.liquid`) reads that metafield to render
the FAQ on the storefront with FAQPage JSON-LD.
"""

from __future__ import annotations

import json
import logging
import time
from datetime import UTC, datetime
from typing import Any

import requests

from app.oauth.token_store import get_token
from app.paths import data_dir

logger = logging.getLogger(__name__)

_GRAPHQL_PATH = "/admin/api/2025-01/graphql.json"
_TIMEOUT = 30
_METAFIELD_NAMESPACE = "leonie"
_METAFIELD_KEY = "faq"

_METAFIELDS_SET = """
mutation MetafieldsSet($metafields: [MetafieldsSetInput!]!) {
  metafieldsSet(metafields: $metafields) {
    metafields { id namespace key value }
    userErrors { field message code }
  }
}
"""

_DATA_DIR = data_dir()


class FaqApplyError(Exception):
    """Raised when the FAQ metafield write fails."""


def _normalize_faq(faq: list[dict[str, Any]]) -> list[dict[str, str]]:
    """Keep only entries with a non-empty question and answer."""
    out: list[dict[str, str]] = []
    for entry in faq or []:
        if not isinstance(entry, dict):
            continue
        q = str(entry.get("q") or entry.get("question") or "").strip()
        a = str(entry.get("a") or entry.get("answer") or "").strip()
        if q and a:
            out.append({"q": q, "a": a})
    return out


def _snapshot_apply(shop: str, product_id: str, faq: list[dict[str, str]]) -> None:
    """Persist a copy of what was applied for traceability."""
    shop_dir = _DATA_DIR / shop / "applied_faqs"
    shop_dir.mkdir(parents=True, exist_ok=True)
    safe_id = product_id.replace("/", "_")
    (shop_dir / f"{safe_id}.json").write_text(
        json.dumps(
            {"applied_at": datetime.now(UTC).isoformat(), "faq": faq},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def apply_faq_to_shopify(
    shop: str,
    product_id: str,
    faq: list[dict[str, Any]],
) -> dict[str, Any]:
    """Write the FAQ JSON to `leonie.faq` metafield on the product.

    Args:
        shop: Shopify shop domain (e.g. "287c4a-bb.myshopify.com").
        product_id: Shopify Product GID (gid://shopify/Product/123).
        faq: List of {"q", "a"} dicts (extra keys ignored).

    Returns:
        Dict with: applied (bool), error (str|None), entry_count (int),
        applied_at (ISO timestamp on success).
    """
    cleaned = _normalize_faq(faq)
    if not cleaned:
        return {"applied": False, "error": "empty FAQ", "entry_count": 0, "applied_at": None}

    token_record = get_token(shop)
    if not token_record:
        return {
            "applied": False,
            "error": "shop not installed (no OAuth token)",
            "entry_count": len(cleaned),
            "applied_at": None,
        }

    variables = {
        "metafields": [{
            "ownerId": product_id,
            "namespace": _METAFIELD_NAMESPACE,
            "key": _METAFIELD_KEY,
            "type": "json",
            "value": json.dumps(cleaned, ensure_ascii=False),
        }]
    }

    endpoint = f"https://{shop}{_GRAPHQL_PATH}"
    headers = {
        "X-Shopify-Access-Token": token_record["access_token"],
        "Content-Type": "application/json",
    }

    try:
        resp = requests.post(
            endpoint,
            headers=headers,
            json={"query": _METAFIELDS_SET, "variables": variables},
            timeout=_TIMEOUT,
        )
        if resp.status_code == 429:
            retry_after = float(resp.headers.get("Retry-After", 1.0))
            time.sleep(min(retry_after, 5.0))
            resp = requests.post(
                endpoint,
                headers=headers,
                json={"query": _METAFIELDS_SET, "variables": variables},
                timeout=_TIMEOUT,
            )
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as exc:
        logger.warning("FAQ sync failed for %s/%s: %s", shop, product_id, exc)
        return {
            "applied": False,
            "error": str(exc),
            "entry_count": len(cleaned),
            "applied_at": None,
        }

    user_errors = (data.get("data") or {}).get("metafieldsSet", {}).get("userErrors") or []
    if user_errors:
        msg = "; ".join(f"{e.get('field')}: {e.get('message')}" for e in user_errors)
        logger.warning("FAQ sync userErrors for %s/%s: %s", shop, product_id, msg)
        return {
            "applied": False,
            "error": msg,
            "entry_count": len(cleaned),
            "applied_at": None,
        }

    applied_at = datetime.now(UTC).isoformat()
    _snapshot_apply(shop, product_id, cleaned)
    logger.info("FAQ synced to Shopify for %s (%d entries)", product_id, len(cleaned))
    return {
        "applied": True,
        "error": None,
        "entry_count": len(cleaned),
        "applied_at": applied_at,
    }
