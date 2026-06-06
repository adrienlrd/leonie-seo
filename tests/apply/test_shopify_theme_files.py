"""Tests for the Shopify theme-files writer (themeFilesUpsert / themeFilesDelete)."""

from __future__ import annotations

import pathlib

import pytest

from app.apply.shopify_theme_files import (
    ShopifyThemeError,
    ShopifyThemeScopeError,
    ShopifyThemeWriter,
)


class _Resp:
    def __init__(self, json_data: dict, status_code: int = 200) -> None:
        self._json = json_data
        self.status_code = status_code
        self.headers: dict[str, str] = {}

    def json(self) -> dict:
        return self._json

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise AssertionError(f"HTTP {self.status_code}")


def _writer() -> ShopifyThemeWriter:
    return ShopifyThemeWriter("shop.myshopify.com", "token")


def _main_theme_resp(theme_id: str = "gid://shopify/OnlineStoreTheme/1") -> dict:
    return {"data": {"themes": {"edges": [{"node": {"id": theme_id, "name": "Dawn"}}]}}}


def test_get_published_theme_id(mocker):
    writer = _writer()
    mocker.patch.object(writer._session, "post", return_value=_Resp(_main_theme_resp()))
    assert writer.get_published_theme_id() == "gid://shopify/OnlineStoreTheme/1"


def test_get_published_theme_id_raises_when_none(mocker):
    writer = _writer()
    mocker.patch.object(
        writer._session, "post", return_value=_Resp({"data": {"themes": {"edges": []}}})
    )
    with pytest.raises(ShopifyThemeError, match="No published"):
        writer.get_published_theme_id()


def test_upsert_templates_returns_filenames(mocker):
    writer = _writer()
    post = mocker.patch.object(
        writer._session,
        "post",
        return_value=_Resp(
            {
                "data": {
                    "themeFilesUpsert": {
                        "upsertedThemeFiles": [
                            {"filename": "templates/llms.txt.liquid"},
                            {"filename": "templates/agents.md.liquid"},
                        ],
                        "userErrors": [],
                    }
                }
            }
        ),
    )
    result = writer.upsert_templates(
        "gid://shopify/OnlineStoreTheme/1",
        {
            "templates/llms.txt.liquid": "{% raw %}\n# Shop\n{% endraw %}",
            "templates/agents.md.liquid": "{% raw %}\n# Shop\n{% endraw %}",
        },
    )
    assert result == ["templates/llms.txt.liquid", "templates/agents.md.liquid"]
    sent = post.call_args.kwargs["json"]["variables"]
    assert sent["themeId"] == "gid://shopify/OnlineStoreTheme/1"
    assert sent["files"][0]["body"] == {
        "type": "TEXT",
        "value": "{% raw %}\n# Shop\n{% endraw %}",
    }


def test_upsert_raises_on_user_errors(mocker):
    writer = _writer()
    mocker.patch.object(
        writer._session,
        "post",
        return_value=_Resp(
            {
                "data": {
                    "themeFilesUpsert": {
                        "upsertedThemeFiles": [],
                        "userErrors": [{"field": ["files"], "message": "invalid filename"}],
                    }
                }
            }
        ),
    )
    with pytest.raises(ShopifyThemeError, match="themeFilesUpsert"):
        writer.upsert_templates("gid://t/1", {"templates/llms.txt.liquid": "x"})


def test_scope_denied_maps_to_scope_error(mocker):
    writer = _writer()
    mocker.patch.object(
        writer._session,
        "post",
        return_value=_Resp({"errors": [{"message": "Access denied for themeFilesUpsert field."}]}),
    )
    with pytest.raises(ShopifyThemeScopeError, match="Reinstall"):
        writer.upsert_templates("gid://t/1", {"templates/llms.txt.liquid": "x"})


def test_http_401_maps_to_scope_error(mocker):
    writer = _writer()
    mocker.patch.object(writer._session, "post", return_value=_Resp({}, 401))
    with pytest.raises(ShopifyThemeScopeError, match="Reinstall"):
        writer.get_published_theme_id()


def test_delete_templates_returns_filenames(mocker):
    writer = _writer()
    mocker.patch.object(
        writer._session,
        "post",
        return_value=_Resp(
            {
                "data": {
                    "themeFilesDelete": {
                        "deletedThemeFiles": [{"filename": "templates/llms.txt.liquid"}],
                        "userErrors": [],
                    }
                }
            }
        ),
    )
    result = writer.delete_templates("gid://t/1", ["templates/llms.txt.liquid"])
    assert result == ["templates/llms.txt.liquid"]


# --- Strict allowlist: write_themes can ONLY touch the 3 AI template files ---


@pytest.mark.parametrize(
    "filename",
    [
        "layout/theme.liquid",
        "sections/header.liquid",
        "snippets/foo.liquid",
        "assets/app.js",
        "templates/product.liquid",
        "templates/collection.liquid",
        "config/settings_data.json",
    ],
)
def test_upsert_refuses_non_allowlisted_files(mocker, filename):
    writer = _writer()
    post = mocker.patch.object(writer._session, "post")
    with pytest.raises(ShopifyThemeError, match="non-allowlisted"):
        writer.upsert_templates("gid://t/1", {filename: "malicious"})
    post.assert_not_called()  # refused before any network call


def test_upsert_refuses_mixed_allowlisted_and_forbidden(mocker):
    writer = _writer()
    post = mocker.patch.object(writer._session, "post")
    files = {
        "templates/llms.txt.liquid": "{% raw %}ok{% endraw %}",
        "layout/theme.liquid": "malicious",
    }
    with pytest.raises(ShopifyThemeError, match="non-allowlisted"):
        writer.upsert_templates("gid://t/1", files)
    post.assert_not_called()


def test_delete_refuses_non_allowlisted_files(mocker):
    writer = _writer()
    post = mocker.patch.object(writer._session, "post")
    with pytest.raises(ShopifyThemeError, match="non-allowlisted"):
        writer.delete_templates("gid://t/1", ["assets/app.js"])
    post.assert_not_called()


def test_only_writer_module_issues_theme_files_mutations():
    """No code path outside the writer may call themeFilesUpsert/Delete."""
    app_root = pathlib.Path(__file__).resolve().parents[2] / "app"
    offenders: list[str] = []
    for path in app_root.rglob("*.py"):
        if path.name == "shopify_theme_files.py":
            continue
        text = path.read_text(encoding="utf-8")
        if "themeFilesUpsert" in text or "themeFilesDelete" in text:
            offenders.append(str(path.relative_to(app_root)))
    assert offenders == [], f"theme mutations used outside the writer: {offenders}"
