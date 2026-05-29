"""Create blog articles as drafts on Shopify via Admin GraphQL.

Mirrors ``app.apply.shopify_writer.ShopifyWriter`` (same retry/backoff pattern,
same GraphQL endpoint) so the rate-limit handling stays consistent across the
app. Default to draft (``isPublished=false``) — the merchant publishes from
Shopify admin once they have reviewed.
"""

from __future__ import annotations

import logging
import time
from typing import Any

import requests

from app.apply.shopify_writer import ShopifyWriteError

logger = logging.getLogger(__name__)

_GRAPHQL_PATH = "/admin/api/2025-01/graphql.json"
_TIMEOUT = 30

_LIST_BLOGS_QUERY = """
query ListBlogs($n: Int!) {
  blogs(first: $n) {
    nodes { id handle title }
  }
}
""".strip()

_CREATE_ARTICLE_MUTATION = """
mutation CreateArticle($article: ArticleCreateInput!) {
  articleCreate(article: $article) {
    article { id handle title isPublished }
    userErrors { field message }
  }
}
""".strip()


class BlogPublisher:
    """Publish blog articles (default: draft) to a merchant's Shopify store."""

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

    def _post(self, query: str, variables: dict[str, Any]) -> dict[str, Any]:
        """GraphQL POST with exponential backoff on 429 / 5xx. Mirrors ShopifyWriter."""
        for attempt in range(self._max_retries):
            resp = self._session.post(
                self._endpoint,
                headers=self._headers,
                json={"query": query, "variables": variables},
                timeout=_TIMEOUT,
            )
            if resp.status_code == 429:
                wait = min(float(resp.headers.get("Retry-After", 2**attempt)), 30.0)
                logger.warning("Shopify rate limit — retrying in %.1fs", wait)
                time.sleep(wait)
                continue
            if resp.status_code >= 500:
                wait = min(2.0**attempt, 30.0)
                logger.warning("Shopify 5xx (%d) — retrying in %.1fs", resp.status_code, wait)
                time.sleep(wait)
                continue
            resp.raise_for_status()
            return resp.json()
        raise ShopifyWriteError(
            f"Max retries ({self._max_retries}) exceeded on {self._endpoint}"
        )

    def list_blogs(self, *, limit: int = 25) -> list[dict[str, Any]]:
        """Return the merchant's blogs so the editor can pick a destination."""
        data = self._post(_LIST_BLOGS_QUERY, {"n": max(1, min(limit, 250))})
        nodes = (((data.get("data") or {}).get("blogs") or {}).get("nodes")) or []
        return [
            {"id": n.get("id"), "handle": n.get("handle"), "title": n.get("title")}
            for n in nodes
            if isinstance(n, dict) and n.get("id")
        ]

    def create_draft_article(
        self,
        *,
        blog_id: str,
        title: str,
        body_html: str,
        summary: str = "",
        tags: list[str] | None = None,
        author_name: str = "",
        image_url: str | None = None,
    ) -> dict[str, Any]:
        """Create the article as ``isPublished=false`` (draft) so the merchant reviews first."""
        article: dict[str, Any] = {
            "blogId": blog_id,
            "title": title,
            "body": body_html,
            "isPublished": False,
        }
        if summary:
            article["summary"] = summary
        if tags:
            article["tags"] = list(tags)
        if author_name:
            article["author"] = {"name": author_name}
        if image_url:
            article["image"] = {"url": image_url}

        data = self._post(_CREATE_ARTICLE_MUTATION, {"article": article})
        payload = ((data.get("data") or {}).get("articleCreate")) or {}
        user_errors = payload.get("userErrors") or []
        if user_errors:
            raise ShopifyWriteError(f"articleCreate userErrors: {user_errors}")
        created = payload.get("article") or {}
        if not created.get("id"):
            raise ShopifyWriteError(f"articleCreate returned no article: {data}")
        time.sleep(self._delay)
        return created
