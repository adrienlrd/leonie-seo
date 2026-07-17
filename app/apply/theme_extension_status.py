"""Detect whether the Giulio Geo theme app embed is enabled on the published theme.

Reads ``config/settings_data.json`` of the MAIN theme (read_themes scope) and looks
for our app embed block (matched by extension handle/uid) and whether it is enabled.
Best-effort and fail-open: returns ``available=False`` when it cannot be determined.
"""

from __future__ import annotations

import json
import logging
from typing import Any

import requests

logger = logging.getLogger(__name__)

_GRAPHQL_PATH = "/admin/api/2025-01/graphql.json"
_TIMEOUT = 20

# Markers identifying our theme app extension inside settings_data.json app embeds.
_EXTENSION_MARKERS = ("leonie-seo-jsonld", "41c38ef1-2770-74ac-364b-b4cff7f918b20d1602f9", "faq_embed")

_MAIN_THEME_QUERY = """
query MainTheme { themes(roles: [MAIN], first: 1) { edges { node { id } } } }
""".strip()

_ALL_THEMES_QUERY = """
query AllThemes { themes(first: 10) { edges { node { id name role } } } }
""".strip()

_SETTINGS_QUERY = """
query ThemeSettings($id: ID!) {
  theme(id: $id) {
    files(filenames: ["config/settings_data.json"], first: 1) {
      nodes {
        body {
          ... on OnlineStoreThemeFileBodyText { content }
          ... on OnlineStoreThemeFileBodyBase64 { contentBase64 }
        }
      }
    }
  }
}
""".strip()


def _post(shop: str, access_token: str, query: str, variables: dict[str, Any]) -> dict[str, Any]:
    resp = requests.post(
        f"https://{shop}{_GRAPHQL_PATH}",
        headers={"X-Shopify-Access-Token": access_token, "Content-Type": "application/json"},
        json={"query": query, "variables": variables},
        timeout=_TIMEOUT,
    )
    resp.raise_for_status()
    return resp.json()


def _app_embed_enabled(settings_json: str) -> bool | None:
    """Return True/False if our app embed is found, else None when undetermined."""
    try:
        data = json.loads(settings_json)
    except (json.JSONDecodeError, TypeError):
        return None
    current = data.get("current")
    if isinstance(current, str):
        # "current" can be a preset NAME pointing into "presets" — themes saved
        # from the editor's preset picker use this form. Not resolving it made
        # the status stay "unknown" forever even after the merchant enabled the
        # embed by hand.
        current = (data.get("presets") or {}).get(current)
    blocks = (current or {}).get("blocks") if isinstance(current, dict) else None
    if not isinstance(blocks, dict):
        return None
    for block in blocks.values():
        if not isinstance(block, dict):
            continue
        block_type = str(block.get("type") or "")
        if any(marker in block_type for marker in _EXTENSION_MARKERS):
            # disabled defaults to False (i.e. enabled) when the key is absent.
            if not bool(block.get("disabled", False)):
                return True
    # No matching enabled app embed → not enabled (whether absent or disabled).
    return False


def get_theme_extension_status(shop: str, access_token: str) -> dict[str, Any]:
    """Return {available, enabled, detail} for the Giulio Geo theme app embed.

    available=False means we could not read the theme (treat enabled as unknown).
    """
    try:
        themes_data = _post(shop, access_token, _ALL_THEMES_QUERY, {})
        theme_nodes = [
            e["node"]
            for e in ((((themes_data.get("data") or {}).get("themes") or {}).get("edges")) or [])
            if isinstance(e, dict) and e.get("node")
        ]
        if not theme_nodes:
            return {"available": False, "enabled": None, "detail": "no themes readable"}
        main = next((tn for tn in theme_nodes if tn.get("role") == "MAIN"), None)
        if main is None:
            return {"available": False, "enabled": None, "detail": "no published theme"}

        main_status = _embed_state_for_theme(shop, access_token, main["id"])
        if main_status.get("enabled"):
            return {"available": True, "enabled": True, "detail": "ok"}

        # Not enabled on the published theme — check drafts: the theme editor
        # deep link sometimes opens an unpublished copy, so the merchant can
        # genuinely have enabled the embed on the wrong theme. Surfacing WHICH
        # one turns a dead-end "not enabled" into an actionable message.
        for tn in theme_nodes:
            if tn.get("role") == "MAIN":
                continue
            other = _embed_state_for_theme(shop, access_token, tn["id"])
            if other.get("enabled"):
                name = str(tn.get("name") or tn.get("id") or "?")
                return {
                    "available": True,
                    "enabled": False,
                    "detail": f"enabled on unpublished theme: {name}",
                }
        return {
            "available": True,
            "enabled": main_status.get("enabled"),
            "detail": main_status.get("detail", "ok"),
        }
    except requests.RequestException as exc:
        logger.warning("Theme extension status check failed for %s: %s", shop, exc)
        return {"available": False, "enabled": None, "detail": str(exc)}


def _embed_state_for_theme(shop: str, access_token: str, theme_id: str) -> dict[str, Any]:
    """Read one theme's settings_data.json and detect our embed's state there."""
    settings_data = _post(shop, access_token, _SETTINGS_QUERY, {"id": theme_id})
    nodes = (
        (((settings_data.get("data") or {}).get("theme") or {}).get("files") or {}).get("nodes")
    ) or []
    if not nodes:
        return {"enabled": None, "detail": "settings_data.json not found"}
    body = (nodes[0] or {}).get("body") or {}
    content = body.get("content") or ""
    if not content and body.get("contentBase64"):
        # Large settings files come back as the Base64 body type — only
        # requesting the text fragment left content empty, so the status
        # stayed "unknown" forever on themes with big settings_data.json.
        import base64  # noqa: PLC0415

        try:
            content = base64.b64decode(body["contentBase64"]).decode("utf-8")
        except (ValueError, UnicodeDecodeError):
            return {"enabled": None, "detail": "settings body undecodable"}
    if not content:
        return {"enabled": None, "detail": "settings body empty"}
    enabled = _app_embed_enabled(content)
    detail = "ok" if enabled is not None else "no app-embed blocks section found"
    return {"enabled": enabled, "detail": detail}
