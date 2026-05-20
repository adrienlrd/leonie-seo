"""Tests for scripts.audit.crawl_shopify."""

import tempfile

from scripts.audit.crawl_shopify import (
    _BLOGS_QUERY,
    _PAGES_QUERY,
    _PRODUCTS_QUERY,
    _URL_REDIRECTS_QUERY,
    fetch_articles,
    fetch_collections,
    fetch_pages,
    fetch_products,
    fetch_shop_metadata,
    fetch_url_redirects,
    init_db,
    save_snapshot,
)


def _products_page(has_next: bool = False, cursor: str | None = None, pid: str = "1") -> dict:
    return {
        "data": {
            "products": {
                "pageInfo": {"hasNextPage": has_next, "endCursor": cursor},
                "edges": [
                    {
                        "node": {
                            "id": f"gid://shopify/Product/{pid}",
                            "title": "Croquettes Chien",
                            "handle": "croquettes-chien",
                            "seo": {"title": "SEO Title", "description": "SEO Desc"},
                            "images": {"edges": []},
                        }
                    }
                ],
            }
        }
    }


def _collections_page() -> dict:
    return {
        "data": {
            "collections": {
                "pageInfo": {"hasNextPage": False, "endCursor": None},
                "edges": [
                    {
                        "node": {
                            "id": "gid://shopify/Collection/1",
                            "title": "Chien",
                            "handle": "chien",
                            "seo": {"title": "Chien SEO", "description": "Desc"},
                        }
                    }
                ],
            }
        }
    }


def _pages_page() -> dict:
    return {
        "data": {
            "pages": {
                "pageInfo": {"hasNextPage": False, "endCursor": None},
                "edges": [{"node": {"id": "gid://shopify/Page/1", "title": "About", "handle": "about"}}],
            }
        }
    }


def _blogs_page() -> dict:
    return {
        "data": {
            "blogs": {
                "pageInfo": {"hasNextPage": False, "endCursor": None},
                "edges": [
                    {
                        "node": {
                            "id": "gid://shopify/Blog/1",
                            "title": "News",
                            "handle": "news",
                            "articles": {
                                "edges": [
                                    {
                                        "node": {
                                            "id": "gid://shopify/Article/1",
                                            "title": "Guide",
                                            "handle": "guide",
                                        }
                                    }
                                ]
                            },
                        }
                    }
                ],
            }
        }
    }


def _redirects_page() -> dict:
    return {
        "data": {
            "urlRedirects": {
                "pageInfo": {"hasNextPage": False, "endCursor": None},
                "edges": [{"node": {"id": "gid://shopify/UrlRedirect/1", "path": "/old", "target": "/new"}}],
            }
        }
    }


def test_fetch_products_returns_nodes(mocker):
    mock = mocker.patch("requests.post")
    mock.return_value.status_code = 200
    mock.return_value.json.return_value = _products_page()

    products = fetch_products(endpoint="http://test", headers={})

    assert len(products) == 1
    assert products[0]["id"] == "gid://shopify/Product/1"


def test_products_query_requests_publication_fields_when_fetching_products() -> None:
    assert "status publishedAt onlineStoreUrl" in _PRODUCTS_QUERY


def test_crawl_l3_queries_include_extended_snapshot_resources() -> None:
    assert "pages(first: 50" in _PAGES_QUERY
    assert "articles(first: 50" in _BLOGS_QUERY
    assert "urlRedirects(first: 50" in _URL_REDIRECTS_QUERY


def test_fetch_products_paginates(mocker):
    page1 = _products_page(has_next=True, cursor="cur1", pid="1")
    page2 = _products_page(has_next=False, pid="2")

    mock = mocker.patch("requests.post")
    mock.return_value.status_code = 200
    mock.return_value.json.side_effect = [page1, page2]

    products = fetch_products(endpoint="http://test", headers={})

    assert len(products) == 2
    assert mock.call_count == 2


def test_fetch_collections_returns_nodes(mocker):
    mock = mocker.patch("requests.post")
    mock.return_value.status_code = 200
    mock.return_value.json.return_value = _collections_page()

    collections = fetch_collections(endpoint="http://test", headers={})

    assert len(collections) == 1
    assert collections[0]["handle"] == "chien"


def test_fetch_pages_returns_nodes(mocker):
    mock = mocker.patch("requests.post")
    mock.return_value.status_code = 200
    mock.return_value.json.return_value = _pages_page()

    pages = fetch_pages(endpoint="http://test", headers={})

    assert pages == [{"id": "gid://shopify/Page/1", "title": "About", "handle": "about"}]


def test_fetch_articles_flattens_blog_articles(mocker):
    mock = mocker.patch("requests.post")
    mock.return_value.status_code = 200
    mock.return_value.json.return_value = _blogs_page()

    articles = fetch_articles(endpoint="http://test", headers={})

    assert articles[0]["id"] == "gid://shopify/Article/1"
    assert articles[0]["blog_handle"] == "news"


def test_fetch_url_redirects_returns_nodes(mocker):
    mock = mocker.patch("requests.post")
    mock.return_value.status_code = 200
    mock.return_value.json.return_value = _redirects_page()

    redirects = fetch_url_redirects(endpoint="http://test", headers={})

    assert redirects == [{"id": "gid://shopify/UrlRedirect/1", "path": "/old", "target": "/new"}]


def test_fetch_shop_metadata_returns_shop_payload(mocker):
    mock = mocker.patch("requests.post")
    mock.return_value.status_code = 200
    mock.return_value.json.return_value = {"data": {"shop": {"myshopifyDomain": "store.myshopify.com"}}}

    metadata = fetch_shop_metadata(endpoint="http://test", headers={})

    assert metadata == {"myshopifyDomain": "store.myshopify.com"}


def test_init_db_creates_tables():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        conn = init_db(tmp.name)
        tables = {
            row[0]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        }
        assert "snapshots" in tables
        assert "seo_changes" in tables
        conn.close()


def test_save_snapshot_inserts_rows():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        conn = init_db(tmp.name)
        resources = [
            {"id": "gid://shopify/Product/1", "title": "A"},
            {"id": "gid://shopify/Product/2", "title": "B"},
        ]
        save_snapshot(conn, "product", resources)

        count = conn.execute("SELECT COUNT(*) FROM snapshots").fetchone()[0]
        assert count == 2
        conn.close()
