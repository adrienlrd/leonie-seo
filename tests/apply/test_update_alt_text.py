"""Tests for scripts.apply.update_alt_text."""

from scripts.apply.update_alt_text import ShopifyUserError, update_image_alt


def test_update_image_alt_calls_correct_mutation(mocker):
    mock_post = mocker.patch("requests.post")
    mock_post.return_value.status_code = 200
    mock_post.return_value.json.return_value = {
        "data": {
            "productImageUpdate": {
                "image": {"id": "gid://shopify/ProductImage/1", "altText": "New alt"},
                "userErrors": [],
            }
        }
    }

    update_image_alt(
        "gid://shopify/Product/1",
        "gid://shopify/ProductImage/1",
        "New alt",
        endpoint="http://test",
        headers={},
    )

    assert mock_post.called
    payload = mock_post.call_args.kwargs["json"]
    assert "productImageUpdate" in payload["query"]
    assert payload["variables"]["productId"] == "gid://shopify/Product/1"
    assert payload["variables"]["image"]["altText"] == "New alt"


def test_update_image_alt_raises_on_user_errors(mocker):
    mock_post = mocker.patch("requests.post")
    mock_post.return_value.status_code = 200
    mock_post.return_value.json.return_value = {
        "data": {
            "productImageUpdate": {
                "image": None,
                "userErrors": [{"field": ["altText"], "message": "Too long"}],
            }
        }
    }

    import pytest

    with pytest.raises(ShopifyUserError):
        update_image_alt(
            "gid://shopify/Product/1",
            "gid://shopify/ProductImage/1",
            "alt",
            endpoint="http://test",
            headers={},
        )
