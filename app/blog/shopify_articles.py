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
    article { id handle title isPublished blog { handle } }
    userErrors { field message }
  }
}
""".strip()

_UPDATE_ARTICLE_MUTATION = """
mutation UpdateArticle($id: ID!, $article: ArticleUpdateInput!) {
  articleUpdate(id: $id, article: $article) {
    article { id handle title isPublished blog { handle } }
    userErrors { field message }
  }
}
""".strip()

_CREATE_BLOG_MUTATION = """
mutation CreateBlog($blog: BlogInput!) {
  blogCreate(blog: $blog) {
    blog { id handle title }
    userErrors { field message }
  }
}
""".strip()


def _raise_for_graphql_errors(payload: dict[str, Any], context: str) -> None:
    """Surface top-level GraphQL errors (scope/auth/field) as a clear write error.

    Shopify returns 200 with ``{"errors": [...]}`` when a query references a missing
    field or the token lacks the required access scope — those won't trip
    raise_for_status. Bubbling them up here lets the merchant see the real cause
    (typically: the new ``write_content`` scope was added but the merchant has not
    reinstalled the app yet).
    """
    errors = payload.get("errors") or []
    if errors:
        joined = "; ".join(
            str(e.get("message", e)) for e in errors if isinstance(e, dict)
        ) or str(errors)
        if "Access denied" in joined or "access" in joined.lower():
            raise ShopifyWriteError(
                f"{context} access denied by Shopify ({joined}). "
                "Reinstall the app from Shopify Admin to grant the new write_content scope."
            )
        raise ShopifyWriteError(f"{context} GraphQL errors → {joined}")


class BlogPublisher:
    """Publish blog articles (default: draft) to a merchant's Shopify store."""

    def __init__(
        self,
        shop: str,
        access_token: str,
        *,
        delay: float = 0.5,
        max_retries: int = 2,
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

    def ensure_default_blog(self, *, title: str = "Blog") -> str:
        """Return the first blog's id, creating one when the store has none.

        Most fresh Shopify stores ship without any blog, so the publish flow would
        otherwise dead-end on the destination picker. Creating a default container
        keeps the experience one-click for the merchant.
        """
        existing = self.list_blogs(limit=1)
        if existing and existing[0].get("id"):
            return str(existing[0]["id"])
        data = self._post(_CREATE_BLOG_MUTATION, {"blog": {"title": title}})
        _raise_for_graphql_errors(data, "blogCreate")
        payload = ((data.get("data") or {}).get("blogCreate")) or {}
        errors = payload.get("userErrors") or []
        if errors:
            joined = "; ".join(
                f"{e.get('field')}: {e.get('message')}" for e in errors if isinstance(e, dict)
            )
            raise ShopifyWriteError(f"blogCreate userErrors → {joined}")
        created = payload.get("blog") or {}
        if not created.get("id"):
            raise ShopifyWriteError(
                "blogCreate returned no blog. Likely cause: the merchant has not "
                "re-consented to the new Shopify scope `write_content`."
            )
        return str(created["id"])

    def list_blogs(self, *, limit: int = 25) -> list[dict[str, Any]]:
        """Return the merchant's blogs so the editor can pick a destination."""
        data = self._post(_LIST_BLOGS_QUERY, {"n": max(1, min(limit, 250))})
        _raise_for_graphql_errors(data, "blogs")
        nodes = (((data.get("data") or {}).get("blogs") or {}).get("nodes")) or []
        return [
            {"id": n.get("id"), "handle": n.get("handle"), "title": n.get("title")}
            for n in nodes
            if isinstance(n, dict) and n.get("id")
        ]

    @staticmethod
    def _build_article_input(
        *,
        blog_id: str | None,
        title: str,
        body_html: str,
        summary: str,
        tags: list[str] | None,
        author_name: str,
        image_url: str | None,
        image_alt: str | None,
        meta_description: str,
        published: bool,
    ) -> dict[str, Any]:
        article: dict[str, Any] = {
            "title": title,
            "body": body_html,
            "isPublished": bool(published),
        }
        if blog_id:
            article["blogId"] = blog_id
        if summary:
            article["summary"] = summary
        if tags:
            article["tags"] = list(tags)
        article["author"] = {"name": author_name or "Author"}
        if image_url:
            image: dict[str, Any] = {"url": image_url}
            if image_alt:
                image["altText"] = image_alt
            article["image"] = image
        # Article SEO meta description is stored in the global.description_tag
        # metafield — the storefront theme renders it as <meta name="description">.
        if meta_description.strip():
            article["metafields"] = [
                {
                    "namespace": "global",
                    "key": "description_tag",
                    "type": "single_line_text_field",
                    "value": meta_description.strip()[:320],
                }
            ]
        return article

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
        image_alt: str | None = None,
        meta_description: str = "",
        published: bool = False,
    ) -> dict[str, Any]:
        """Create the article. Default ``isPublished=false`` (draft) so the merchant
        reviews first; pass ``published=True`` to put it live (visible) immediately."""
        article = self._build_article_input(
            blog_id=blog_id,
            title=title,
            body_html=body_html,
            summary=summary,
            tags=tags,
            author_name=author_name,
            image_url=image_url,
            image_alt=image_alt,
            meta_description=meta_description,
            published=published,
        )
        data = self._post(_CREATE_ARTICLE_MUTATION, {"article": article})
        _raise_for_graphql_errors(data, "articleCreate")
        payload = ((data.get("data") or {}).get("articleCreate")) or {}
        user_errors = payload.get("userErrors") or []
        if user_errors:
            joined = "; ".join(
                f"{e.get('field')}: {e.get('message')}" for e in user_errors if isinstance(e, dict)
            )
            raise ShopifyWriteError(f"articleCreate userErrors → {joined}")
        created = payload.get("article") or {}
        if not created.get("id"):
            raise ShopifyWriteError(
                "articleCreate returned no article. Likely cause: the merchant has not "
                "re-consented to the new Shopify scope `write_content` — reinstalling the "
                "app from Shopify Admin should fix it."
            )
        time.sleep(self._delay)
        return created

    def update_article(
        self,
        *,
        article_id: str,
        title: str,
        body_html: str,
        summary: str = "",
        tags: list[str] | None = None,
        author_name: str = "",
        image_url: str | None = None,
        image_alt: str | None = None,
        meta_description: str = "",
        published: bool = False,
    ) -> dict[str, Any]:
        """Update an existing Shopify article in place (re-publish edits the same post)."""
        article = self._build_article_input(
            blog_id=None,  # blog is fixed once the article exists
            title=title,
            body_html=body_html,
            summary=summary,
            tags=tags,
            author_name=author_name,
            image_url=image_url,
            image_alt=image_alt,
            meta_description=meta_description,
            published=published,
        )
        data = self._post(_UPDATE_ARTICLE_MUTATION, {"id": article_id, "article": article})
        _raise_for_graphql_errors(data, "articleUpdate")
        payload = ((data.get("data") or {}).get("articleUpdate")) or {}
        user_errors = payload.get("userErrors") or []
        if user_errors:
            joined = "; ".join(
                f"{e.get('field')}: {e.get('message')}" for e in user_errors if isinstance(e, dict)
            )
            raise ShopifyWriteError(f"articleUpdate userErrors → {joined}")
        updated = payload.get("article") or {}
        if not updated.get("id"):
            raise ShopifyWriteError("articleUpdate returned no article.")
        time.sleep(self._delay)
        return updated
