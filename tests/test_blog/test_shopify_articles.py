"""BlogPublisher: list blogs + create draft article via Admin GraphQL."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.blog.shopify_articles import BlogPublisher


def _response(payload: dict, status: int = 200) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status
    resp.json.return_value = payload
    resp.headers = {}
    return resp


def test_list_blogs_returns_nodes():
    publisher = BlogPublisher("shop.myshopify.com", "shpat_test")
    with patch.object(
        publisher._session,
        "post",
        return_value=_response(
            {
                "data": {
                    "blogs": {
                        "nodes": [
                            {"id": "gid://shopify/Blog/1", "handle": "news", "title": "News"},
                            {"id": "gid://shopify/Blog/2", "handle": "guides", "title": "Guides"},
                        ]
                    }
                }
            }
        ),
    ):
        blogs = publisher.list_blogs()
    assert len(blogs) == 2
    assert blogs[0]["handle"] == "news"


def test_create_draft_article_sends_is_published_false():
    publisher = BlogPublisher("shop.myshopify.com", "shpat_test")
    article_payload = {
        "data": {
            "articleCreate": {
                "article": {
                    "id": "gid://shopify/Article/99",
                    "handle": "fontaine-chat",
                    "title": "Guide fontaine chat",
                    "isPublished": False,
                },
                "userErrors": [],
            }
        }
    }
    with patch.object(publisher._session, "post", return_value=_response(article_payload)) as post:
        created = publisher.create_draft_article(
            blog_id="gid://shopify/Blog/1",
            title="Guide fontaine chat",
            body_html="<p>x</p>",
            summary="résumé",
            author_name="Léonie Delacroix",
        )

    sent = post.call_args.kwargs["json"]["variables"]["article"]
    assert sent["isPublished"] is False  # drafts only — never auto-publish in Sprint 1
    assert sent["author"]["name"] == "Léonie Delacroix"
    assert sent["body"] == "<p>x</p>"
    assert "image" not in sent
    assert created["id"].endswith("/99")


def test_create_draft_article_sends_image_with_alt_text():
    publisher = BlogPublisher("shop.myshopify.com", "shpat_test")
    article_payload = {
        "data": {
            "articleCreate": {
                "article": {
                    "id": "gid://shopify/Article/100",
                    "handle": "guide-croquettes",
                    "title": "Guide croquettes",
                    "isPublished": False,
                },
                "userErrors": [],
            }
        }
    }
    with patch.object(publisher._session, "post", return_value=_response(article_payload)) as post:
        publisher.create_draft_article(
            blog_id="gid://shopify/Blog/1",
            title="Guide croquettes",
            body_html="<p>x</p>",
            image_url="https://cdn.shopify.com/cover.jpg",
            image_alt="Guide croquettes – croquettes sans céréales",
        )

    sent_image = post.call_args.kwargs["json"]["variables"]["article"]["image"]
    assert sent_image == {
        "url": "https://cdn.shopify.com/cover.jpg",
        "altText": "Guide croquettes – croquettes sans céréales",
    }


def test_create_draft_article_omits_alt_text_when_not_provided():
    publisher = BlogPublisher("shop.myshopify.com", "shpat_test")
    article_payload = {
        "data": {
            "articleCreate": {
                "article": {
                    "id": "gid://shopify/Article/101",
                    "handle": "guide-litiere",
                    "title": "Guide litière",
                    "isPublished": False,
                },
                "userErrors": [],
            }
        }
    }
    with patch.object(publisher._session, "post", return_value=_response(article_payload)) as post:
        publisher.create_draft_article(
            blog_id="gid://shopify/Blog/1",
            title="Guide litière",
            body_html="<p>x</p>",
            image_url="https://cdn.shopify.com/cover.jpg",
        )

    sent_image = post.call_args.kwargs["json"]["variables"]["article"]["image"]
    assert sent_image == {"url": "https://cdn.shopify.com/cover.jpg"}
