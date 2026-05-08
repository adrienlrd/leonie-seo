"""Tests for scripts.apply.create_redirects."""

import pytest

from scripts.apply.create_redirects import (
    ShopifyUserError,
    create_redirect,
    validate_redirects,
)

# ── validate_redirects ────────────────────────────────────────────────────────


def test_validate_redirects_valid_rows():
    rows = [{"from_path": "/old", "to_path": "/new"}]
    valid, warnings = validate_redirects(rows)
    assert len(valid) == 1
    assert warnings == []


def test_validate_redirects_skips_missing_slash():
    rows = [{"from_path": "old", "to_path": "/new"}]
    valid, warnings = validate_redirects(rows)
    assert valid == []
    assert any("must start with '/'" in w for w in warnings)


def test_validate_redirects_skips_self_redirect():
    rows = [{"from_path": "/same", "to_path": "/same"}]
    valid, warnings = validate_redirects(rows)
    assert valid == []
    assert any("self-redirect" in w for w in warnings)


def test_validate_redirects_skips_duplicate_from_path():
    rows = [
        {"from_path": "/old", "to_path": "/new1"},
        {"from_path": "/old", "to_path": "/new2"},
    ]
    valid, warnings = validate_redirects(rows)
    assert len(valid) == 1
    assert any("duplicate" in w for w in warnings)


def test_validate_redirects_warns_on_live_handle():
    rows = [{"from_path": "/products/mon-produit", "to_path": "/products/nouveau"}]
    valid, warnings = validate_redirects(rows, existing_handles={"mon-produit"})
    assert len(valid) == 1  # still valid, just warned
    assert any("live handle" in w for w in warnings)


def test_validate_redirects_accepts_https_to_path():
    rows = [{"from_path": "/old", "to_path": "https://www.example.com/new"}]
    valid, warnings = validate_redirects(rows)
    assert len(valid) == 1
    assert warnings == []


def test_validate_redirects_skips_empty_rows():
    rows = [{"from_path": "", "to_path": "/new"}]
    valid, warnings = validate_redirects(rows)
    assert valid == []
    assert any("empty" in w for w in warnings)


# ── create_redirect ───────────────────────────────────────────────────────────


def test_create_redirect_calls_correct_mutation(mocker):
    mock_post = mocker.patch("requests.post")
    mock_post.return_value.status_code = 200
    mock_post.return_value.json.return_value = {
        "data": {
            "urlRedirectCreate": {
                "urlRedirect": {
                    "id": "gid://shopify/UrlRedirect/1",
                    "path": "/old",
                    "target": "/new",
                },
                "userErrors": [],
            }
        }
    }

    create_redirect("/old", "/new", endpoint="http://test", headers={})

    assert mock_post.called
    payload = mock_post.call_args.kwargs["json"]
    assert "urlRedirectCreate" in payload["query"]
    assert payload["variables"]["urlRedirect"]["path"] == "/old"
    assert payload["variables"]["urlRedirect"]["target"] == "/new"


def test_create_redirect_raises_on_user_errors(mocker):
    mock_post = mocker.patch("requests.post")
    mock_post.return_value.status_code = 200
    mock_post.return_value.json.return_value = {
        "data": {
            "urlRedirectCreate": {
                "urlRedirect": None,
                "userErrors": [
                    {"field": ["path"], "message": "Path already exists", "code": "TAKEN"}
                ],
            }
        }
    }

    with pytest.raises(ShopifyUserError):
        create_redirect("/old", "/new", endpoint="http://test", headers={})
