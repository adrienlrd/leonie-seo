"""Detect whether the GEO by Organically theme app embed is enabled on the published theme.

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
query AllThemes { themes(first: 30) { edges { node { id name role } } } }
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


def _app_embed_enabled(settings_json: str, diag: dict | None = None) -> bool | None:
    """Return True/False if our app embed is found, else None when undetermined.

    ``diag`` (optional) collects the observed JSON shape so a live None status
    is diagnosable (top-level keys, current type) without dumping the file.
    """
    # Shopify themes traditionally open settings_data.json with a /* ... */
    # comment header before the JSON body — strip it or json.loads fails
    # (this was the root cause of the status staying "unknown" live).
    cleaned = settings_json.lstrip()
    if cleaned.startswith("/*"):
        end = cleaned.find("*/")
        if end != -1:
            cleaned = cleaned[end + 2 :].lstrip()
    try:
        data = json.loads(cleaned)
    except (json.JSONDecodeError, TypeError):
        if diag is not None:
            diag["shape"] = "not json"
        return None
    current = data.get("current")
    if diag is not None:
        diag["shape"] = (
            f"top-level keys: {sorted(data)[:8]}; current type: {type(current).__name__}"
        )
    if isinstance(current, str):
        # "current" can be a preset NAME pointing into "presets" — themes saved
        # from the editor's preset picker use this form. Not resolving it made
        # the status stay "unknown" forever even after the merchant enabled the
        # embed by hand.
        current = (data.get("presets") or {}).get(current)
        if diag is not None and not isinstance(current, dict):
            diag["shape"] += f"; preset names: {sorted(data.get('presets') or {})[:5]}"
    if not isinstance(current, dict):
        return None
    blocks = current.get("blocks")
    if not isinstance(blocks, dict):
        # Settings parsed fine but the theme has no app-embed entries at all —
        # that IS "not enabled", not "unknown" (verified live: a valid theme
        # with zero embeds previously showed as indeterminate forever).
        return False
    for block in blocks.values():
        if not isinstance(block, dict):
            continue
        block_type = str(block.get("type") or "")
        if any(marker in block_type for marker in _EXTENSION_MARKERS):
            if diag is not None:
                # e.g. shopify://apps/<app>/blocks/faq_embed/<uuid> — the LAST
                # segment is the extension uuid Shopify actually deployed.
                diag["embed_uid"] = block_type.rstrip("/").rsplit("/", 1)[-1]
            # disabled defaults to False (i.e. enabled) when the key is absent.
            if not bool(block.get("disabled", False)):
                return True
    # No matching enabled app embed → not enabled (whether absent or disabled).
    return False


def get_theme_extension_status(shop: str, access_token: str) -> dict[str, Any]:
    """Return {available, enabled, detail} for the GEO by Organically theme app embed.

    available=False means we could not read the theme (treat enabled as unknown).
    """
    try:
        # The published theme is fetched by role — a paginated all-themes list
        # can miss it entirely on stores with many theme copies (seen live:
        # 10 UNPUBLISHED copies before the MAIN one).
        main_data = _post(shop, access_token, _MAIN_THEME_QUERY, {})
        main_edges = (((main_data.get("data") or {}).get("themes") or {}).get("edges")) or []
        if not main_edges:
            return {"available": False, "enabled": None, "detail": "no published theme"}
        main_id = main_edges[0]["node"]["id"]

        main_status = _embed_state_for_theme(shop, access_token, main_id)
        if main_status.get("enabled"):
            return {
                "available": True,
                "enabled": True,
                "detail": "ok",
                "embed_uid": main_status.get("embed_uid"),
            }

        # Not enabled on the published theme — check drafts: the theme editor
        # deep link sometimes opens an unpublished copy, so the merchant can
        # genuinely have enabled the embed on the wrong theme. Surfacing WHICH
        # one turns a dead-end "not enabled" into an actionable message.
        themes_data = _post(shop, access_token, _ALL_THEMES_QUERY, {})
        theme_nodes = [
            e["node"]
            for e in ((((themes_data.get("data") or {}).get("themes") or {}).get("edges")) or [])
            if isinstance(e, dict) and e.get("node")
        ]
        for tn in theme_nodes:
            if tn.get("id") == main_id:
                continue
            other = _embed_state_for_theme(shop, access_token, tn["id"])
            if other.get("enabled"):
                name = str(tn.get("name") or tn.get("id") or "?")
                return {
                    "available": True,
                    "enabled": False,
                    "detail": f"enabled on unpublished theme: {name}",
                    "embed_uid": other.get("embed_uid"),
                }
        return {
            "available": True,
            "enabled": main_status.get("enabled"),
            "detail": main_status.get("detail", "ok"),
            "embed_uid": main_status.get("embed_uid"),
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
    diag: dict = {}
    enabled = _app_embed_enabled(content, diag)
    detail = "ok" if enabled is not None else f"settings shape not understood ({diag.get('shape', '?')})"
    out: dict[str, Any] = {"enabled": enabled, "detail": detail}
    if diag.get("embed_uid"):
        out["embed_uid"] = diag["embed_uid"]
    return out
