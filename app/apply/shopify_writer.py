"""Shopify GraphQL writer with rate-limiting and exponential retry."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass

import requests

logger = logging.getLogger(__name__)

_GRAPHQL_PATH = "/admin/api/2025-01/graphql.json"
_TIMEOUT = 30

_UPDATE_PRODUCT_SEO = """
mutation UpdateProductSEO($input: ProductInput!) {
  productUpdate(input: $input) {
    product { id seo { title description } }
    userErrors { field message }
  }
}
"""

_UPDATE_COLLECTION_SEO = """
mutation UpdateCollectionSEO($input: CollectionInput!) {
  collectionUpdate(collection: $input) {
    collection { id seo { title description } }
    userErrors { field message }
  }
}
"""

_READ_PRODUCT_SEO = """
query ReadProductSEO($id: ID!) {
  product(id: $id) { id seo { title description } }
}
"""

_READ_COLLECTION_SEO = """
query ReadCollectionSEO($id: ID!) {
  collection(id: $id) { id seo { title description } }
}
"""


class ShopifyWriteError(Exception):
    """Raised when a Shopify mutation returns userErrors or a non-retryable HTTP error."""


@dataclass
class ApplyResult:
    """Outcome of a single Shopify SEO mutation.

    Attributes:
        resource_id: Shopify GID of the mutated resource.
        applied: True if the mutation succeeded.
        error: Human-readable error message on failure, None on success.
        attempts: Number of HTTP attempts made (including retries).
        old_title: SEO title BEFORE the mutation (captured for rollback).
                   None when reading the previous state failed or the field
                   was empty on Shopify.
        old_description: SEO description BEFORE the mutation (rollback data).
    """

    resource_id: str
    applied: bool
    error: str | None = None
    attempts: int = 1
    old_title: str | None = None
    old_description: str | None = None


class ShopifyWriter:
    """Applies SEO mutations to Shopify with exponential retry on rate-limits.

    Args:
        shop: Shopify shop domain (e.g. "287c4a-bb.myshopify.com").
        access_token: Decrypted OAuth access token.
        delay: Base seconds to wait between successful mutations (leaky bucket).
        max_retries: Maximum retry attempts on 429 / 5xx responses.
    """

    def __init__(
        self,
        shop: str,
        access_token: str,
        *,
        delay: float = 0.5,
        max_retries: int = 3,
    ) -> None:
        self._endpoint = f"https://{shop}{_GRAPHQL_PATH}"
        self._headers = {
            "X-Shopify-Access-Token": access_token,
            "Content-Type": "application/json",
        }
        self._delay = delay
        self._max_retries = max_retries
        self._session = requests.Session()

    def _post(self, query: str, variables: dict) -> dict:
        """Execute a GraphQL mutation with exponential retry on 429/5xx.

        Returns:
            Parsed JSON response dict.

        Raises:
            ShopifyWriteError: On non-retryable error or max retries exceeded.
        """
        for attempt in range(self._max_retries):
            resp = self._session.post(
                self._endpoint,
                headers=self._headers,
                json={"query": query, "variables": variables},
                timeout=_TIMEOUT,
            )

            if resp.status_code == 429:
                retry_after = float(resp.headers.get("Retry-After", 2**attempt))
                wait = min(retry_after, 30.0)
                logger.warning(
                    "Shopify rate limit — retrying in %.1fs (attempt %d)", wait, attempt + 1
                )
                time.sleep(wait)
                continue

            if resp.status_code >= 500:
                wait = min(2.0**attempt, 30.0)
                logger.warning("Shopify 5xx (%d) — retrying in %.1fs", resp.status_code, wait)
                time.sleep(wait)
                continue

            resp.raise_for_status()
            return resp.json()

        raise ShopifyWriteError(f"Max retries ({self._max_retries}) exceeded on {self._endpoint}")

    def _read_seo(self, gid: str, query: str, root_key: str) -> tuple[str | None, str | None]:
        """Fetch the current seo.title / seo.description from Shopify.

        Returns (None, None) when the read fails — callers should treat
        absent old values as 'unknown, no rollback possible' rather than
        bailing on the apply.
        """
        try:
            data = self._post(query, {"id": gid})
        except (requests.RequestException, ShopifyWriteError) as exc:
            logger.warning("Failed to read prior SEO for %s (rollback disabled): %s", gid, exc)
            return None, None
        resource = (data.get("data") or {}).get(root_key) or {}
        seo = resource.get("seo") or {}
        return seo.get("title"), seo.get("description")

    def read_product_seo(self, product_id: str) -> tuple[str | None, str | None]:
        """Fetch current product SEO fields without writing to Shopify.

        Args:
            product_id: Shopify Product GID.

        Returns:
            Tuple `(seo_title, seo_description)`. Values are None when Shopify
            has no explicit SEO value or when the read fails.
        """
        return self._read_seo(product_id, _READ_PRODUCT_SEO, "product")

    def apply_product_seo(
        self,
        product_id: str,
        title: str | None,
        description: str | None,
    ) -> ApplyResult:
        """Apply a product SEO mutation with retry. Captures the previous SEO
        values BEFORE the mutation so the orchestrator can build rollback rows
        with real old_value data instead of NULL.

        Args:
            product_id: Shopify Product GID.
            title: New meta title (None = leave unchanged).
            description: New meta description (None = leave unchanged).

        Returns:
            ApplyResult with old_title / old_description populated from the
            read-before-write step (when reachable).
        """
        if not title and not description:
            return ApplyResult(resource_id=product_id, applied=False, error="no fields to update")

        # Read current values BEFORE writing — required for rollback.
        old_title, old_desc = self._read_seo(product_id, _READ_PRODUCT_SEO, "product")

        seo: dict[str, str] = {}
        if title:
            seo["title"] = title
        if description:
            seo["description"] = description

        variables = {"input": {"id": product_id, "seo": seo}}

        try:
            data = self._post(_UPDATE_PRODUCT_SEO, variables)
        except (requests.RequestException, ShopifyWriteError) as exc:
            return ApplyResult(
                resource_id=product_id,
                applied=False,
                error=str(exc),
                old_title=old_title,
                old_description=old_desc,
            )

        user_errors = (data.get("data") or {}).get("productUpdate", {}).get("userErrors", [])
        if user_errors:
            msg = "; ".join(f"{e['field']}: {e['message']}" for e in user_errors)
            return ApplyResult(
                resource_id=product_id,
                applied=False,
                error=msg,
                old_title=old_title,
                old_description=old_desc,
            )

        time.sleep(self._delay)
        return ApplyResult(
            resource_id=product_id,
            applied=True,
            old_title=old_title,
            old_description=old_desc,
        )

    def apply_collection_seo(
        self,
        collection_id: str,
        title: str | None,
        description: str | None,
    ) -> ApplyResult:
        """Apply a collection SEO mutation with retry.

        Args:
            collection_id: Shopify Collection GID.
            title: New meta title.
            description: New meta description.
        """
        if not title and not description:
            return ApplyResult(
                resource_id=collection_id, applied=False, error="no fields to update"
            )

        seo: dict[str, str] = {}
        if title:
            seo["title"] = title
        if description:
            seo["description"] = description

        variables = {"input": {"id": collection_id, "seo": seo}}

        try:
            data = self._post(_UPDATE_COLLECTION_SEO, variables)
        except (requests.RequestException, ShopifyWriteError) as exc:
            return ApplyResult(resource_id=collection_id, applied=False, error=str(exc))

        user_errors = (data.get("data") or {}).get("collectionUpdate", {}).get("userErrors", [])
        if user_errors:
            msg = "; ".join(f"{e['field']}: {e['message']}" for e in user_errors)
            return ApplyResult(resource_id=collection_id, applied=False, error=msg)

        time.sleep(self._delay)
        return ApplyResult(resource_id=collection_id, applied=True)
