"""Shopify theme-files writer for publishing the AI discovery templates.

Shopify serves /llms.txt, /llms-full.txt and /agents.md natively from theme
templates (``templates/*.liquid``). The only supported way to customise them is
to write those template files on the published (MAIN) theme via the Admin
GraphQL API 2025-01. This writer touches ONLY those template files — never any
other theme asset.

Mutations used: themes(roles:[MAIN]) (read), themeFilesUpsert, themeFilesDelete.
Requires the read_themes + write_themes OAuth scopes.
"""

from __future__ import annotations

import logging
import time

import requests

logger = logging.getLogger(__name__)

_GRAPHQL_PATH = "/admin/api/2025-01/graphql.json"
_TIMEOUT = 30

# Strict allowlist — the ONLY theme files this app may ever create/update/delete.
# Any attempt to touch another file (layout/*, sections/*, snippets/*, assets/*,
# templates/product*, templates/collection*, theme.liquid, …) is refused before
# any network call. This is the hard guarantee that write_themes can never be
# used to modify a merchant's existing theme design or code.
#
# Shopify officially serves /llms.txt, /llms-full.txt and /agents.md from these
# theme templates since 2026-05-28 (templates/agents.md.liquid is the fallback
# for the other two paths):
# https://shopify.dev/changelog/customize-llmstxt-llms-fulltxt-and-agentsmd
ALLOWED_THEME_FILES = frozenset(
    {
        "templates/llms.txt.liquid",
        "templates/llms-full.txt.liquid",
        "templates/agents.md.liquid",
    }
)


def _assert_allowlisted(filenames: list[str]) -> None:
    """Refuse any filename outside the strict AI-template allowlist."""
    blocked = sorted(f for f in filenames if f not in ALLOWED_THEME_FILES)
    if blocked:
        raise ShopifyThemeError(
            "Refused to touch non-allowlisted theme files: "
            f"{blocked}. Only {sorted(ALLOWED_THEME_FILES)} may be written."
        )

_MAIN_THEME = """
query MainTheme {
  themes(roles: [MAIN], first: 1) {
    edges { node { id name } }
  }
}
"""

_THEME_FILES_UPSERT = """
mutation ThemeFilesUpsert($themeId: ID!, $files: [OnlineStoreThemeFilesUpsertFileInput!]!) {
  themeFilesUpsert(themeId: $themeId, files: $files) {
    upsertedThemeFiles { filename }
    userErrors { field message }
  }
}
"""

_THEME_FILES_DELETE = """
mutation ThemeFilesDelete($themeId: ID!, $files: [String!]!) {
  themeFilesDelete(themeId: $themeId, files: $files) {
    deletedThemeFiles { filename }
    userErrors { field message }
  }
}
"""


class ShopifyThemeError(Exception):
    """Raised when a theme-files operation returns userErrors or a hard error."""


class ShopifyThemeScopeError(ShopifyThemeError):
    """Raised when Shopify denies access — the write_themes scope is missing.

    Maps to a "reinstall to grant the new permission" message for the merchant.
    """


class ShopifyThemeWriter:
    """Writes and deletes theme template files on the published theme.

    Args:
        shop: Shopify shop domain (e.g. "shop.myshopify.com").
        access_token: Decrypted OAuth access token with read_themes + write_themes.
        max_retries: Retry attempts on 429 / 5xx GraphQL responses.
    """

    def __init__(self, shop: str, access_token: str, *, max_retries: int = 3) -> None:
        self._endpoint = f"https://{shop}{_GRAPHQL_PATH}"
        self._headers = {
            "X-Shopify-Access-Token": access_token,
            "Content-Type": "application/json",
        }
        self._max_retries = max_retries
        self._session = requests.Session()

    def _post(self, query: str, variables: dict) -> dict:
        for attempt in range(self._max_retries):
            resp = self._session.post(
                self._endpoint,
                headers=self._headers,
                json={"query": query, "variables": variables},
                timeout=_TIMEOUT,
            )
            if resp.status_code == 429:
                wait = min(float(resp.headers.get("Retry-After", 2**attempt)), 30.0)
                logger.warning("Theme API rate limit — retrying in %.1fs", wait)
                time.sleep(wait)
                continue
            if resp.status_code >= 500:
                time.sleep(min(2.0**attempt, 30.0))
                continue
            if resp.status_code in (401, 403):
                raise ShopifyThemeScopeError(
                    f"Shopify rejected the access token (HTTP {resp.status_code}). "
                    "Reinstall the app from Shopify Admin to refresh permissions."
                )
            resp.raise_for_status()
            data = resp.json()
            self._raise_for_top_level_errors(data)
            return data
        raise ShopifyThemeError(f"Max retries exceeded on {self._endpoint}")

    @staticmethod
    def _raise_for_top_level_errors(data: dict) -> None:
        """Surface 200-OK GraphQL errors (scope/auth) as a clear write error."""
        errors = data.get("errors") or []
        if not errors:
            return
        joined = "; ".join(str(e.get("message", e)) for e in errors)
        if "access denied" in joined.lower() or "access" in joined.lower():
            raise ShopifyThemeScopeError(
                f"Shopify denied theme access ({joined}). Reinstall the app from "
                "Shopify Admin to grant the new themes permission."
            )
        raise ShopifyThemeError(f"GraphQL error: {joined}")

    @staticmethod
    def _raise_user_errors(payload: dict, context: str) -> None:
        errors = payload.get("userErrors") or []
        if errors:
            msg = "; ".join(f"{e.get('field')}: {e.get('message')}" for e in errors)
            raise ShopifyThemeError(f"{context}: {msg}")

    def get_published_theme_id(self) -> str:
        """Return the GID of the published (MAIN) theme.

        Raises:
            ShopifyThemeError: If the store has no published theme.
        """
        data = self._post(_MAIN_THEME, {})
        edges = (((data.get("data") or {}).get("themes") or {}).get("edges")) or []
        if not edges:
            raise ShopifyThemeError("No published (MAIN) theme found for this shop.")
        return edges[0]["node"]["id"]

    def upsert_templates(self, theme_id: str, files: dict[str, str]) -> list[str]:
        """Create or update theme template files. Returns the upserted filenames.

        Args:
            theme_id: Published theme GID.
            files: Mapping of ``filename`` → text content (already Liquid-safe).

        Raises:
            ShopifyThemeError: If any filename is outside the strict allowlist.
        """
        _assert_allowlisted(list(files.keys()))
        variables = {
            "themeId": theme_id,
            "files": [
                {"filename": name, "body": {"type": "TEXT", "value": content}}
                for name, content in files.items()
            ],
        }
        data = self._post(_THEME_FILES_UPSERT, variables)
        payload = (data.get("data") or {}).get("themeFilesUpsert") or {}
        self._raise_user_errors(payload, "themeFilesUpsert")
        return [f["filename"] for f in (payload.get("upsertedThemeFiles") or [])]

    def delete_templates(self, theme_id: str, filenames: list[str]) -> list[str]:
        """Delete theme template files. Returns the deleted filenames.

        Raises:
            ShopifyThemeError: If any filename is outside the strict allowlist.
        """
        _assert_allowlisted(filenames)
        variables = {"themeId": theme_id, "files": filenames}
        data = self._post(_THEME_FILES_DELETE, variables)
        payload = (data.get("data") or {}).get("themeFilesDelete") or {}
        self._raise_user_errors(payload, "themeFilesDelete")
        return [f["filename"] for f in (payload.get("deletedThemeFiles") or [])]
