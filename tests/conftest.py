"""Fixtures partagées pour tous les tests du projet SEO."""

from pathlib import Path

import pytest

# CLI script suites (scripts/) call get_config(), which now requires an explicit
# tenant. Point them at a test-only sample tenant so they never depend on a real
# merchant config. The embedded app never calls get_config().
_FIXTURE_TENANTS = Path(__file__).parent / "fixtures" / "tenants"
_CLI_TENANT_ID = "leoniedelacroix"
_CLI_TEST_DIRS = ("tests/report/", "tests/audit/", "tests/apply/")


@pytest.fixture(autouse=True)
def _cli_tenant(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch):
    """Provide a sample tenant to CLI-script tests that call get_config()."""
    rel = request.node.path.relative_to(request.config.rootpath).as_posix()
    if any(rel.startswith(d) for d in _CLI_TEST_DIRS):
        from scripts._config import reset_config_cache

        monkeypatch.setenv("TENANT_ID", _CLI_TENANT_ID)
        monkeypatch.setattr("scripts._config._CONFIG_DIR", _FIXTURE_TENANTS)
        reset_config_cache()
        yield
        reset_config_cache()
    else:
        yield

_ARCHIVED_API_TESTS = {
    "tests/test_api/test_alerts.py",
    "tests/test_api/test_alt_text.py",
    "tests/test_api/test_apply.py",
    "tests/test_api/test_audit.py",
    "tests/test_api/test_audit_readiness.py",
    "tests/test_api/test_cannibalization.py",
    "tests/test_api/test_content.py",
    "tests/test_api/test_content_actions.py",
    "tests/test_api/test_descriptions.py",
    "tests/test_api/test_generate.py",
    "tests/test_api/test_hreflang.py",
    "tests/test_api/test_ice.py",
    "tests/test_api/test_internal_links.py",
    "tests/test_api/test_jsonld_status.py",
    "tests/test_api/test_longtail.py",
    "tests/test_api/test_niche_understanding.py",
    "tests/test_api/test_opportunities.py",
    "tests/test_api/test_plans.py",
    "tests/test_api/test_priorities.py",
    "tests/test_api/test_redirects.py",
    "tests/test_api/test_reports.py",
    "tests/test_api/test_rollback.py",
    "tests/test_api/test_safe_apply.py",
    "tests/test_api/test_semantics.py",
}


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Skip tests for API routers intentionally unmounted from app.main."""
    archived = pytest.mark.skip(reason="Archived router is intentionally not mounted in app.main")
    for item in items:
        relative = item.path.relative_to(config.rootpath).as_posix()
        if relative in _ARCHIVED_API_TESTS:
            item.add_marker(archived)


# --- Fixtures Shopify ---


@pytest.fixture
def shopify_products_response() -> dict:
    """Réponse GraphQL simulée pour une liste de produits Shopify."""
    return {
        "data": {
            "products": {
                "pageInfo": {"hasNextPage": False, "endCursor": None},
                "edges": [
                    {
                        "node": {
                            "id": "gid://shopify/Product/1",
                            "title": "Croquettes Chien Senior",
                            "handle": "croquettes-chien-senior",
                            "seo": {
                                "title": "Croquettes Chien Senior | Leoniedelacroix",
                                "description": "Croquettes premium pour chien senior, fabriquées en France.",
                            },
                            "images": {
                                "edges": [
                                    {
                                        "node": {
                                            "id": "gid://shopify/MediaImage/1",
                                            "url": "https://cdn.shopify.com/img1.jpg",
                                            "altText": "Croquettes chien senior sac 2kg",
                                        }
                                    }
                                ]
                            },
                        }
                    },
                    {
                        "node": {
                            "id": "gid://shopify/Product/2",
                            "title": "Croquettes Chat Adulte",
                            "handle": "croquettes-chat-adulte",
                            "seo": {"title": "", "description": ""},
                            "images": {
                                "edges": [
                                    {
                                        "node": {
                                            "id": "gid://shopify/MediaImage/2",
                                            "url": "https://cdn.shopify.com/img2.jpg",
                                            "altText": None,
                                        }
                                    }
                                ]
                            },
                        }
                    },
                ],
            }
        }
    }


@pytest.fixture
def shopify_mutation_success_response() -> dict:
    """Réponse GraphQL simulée pour une mutation réussie."""
    return {
        "data": {
            "productUpdate": {
                "product": {
                    "id": "gid://shopify/Product/1",
                    "seo": {
                        "title": "Nouveau titre SEO",
                        "description": "Nouvelle meta description.",
                    },
                },
                "userErrors": [],
            }
        }
    }


@pytest.fixture
def shopify_mutation_error_response() -> dict:
    """Réponse GraphQL simulée pour une mutation en erreur."""
    return {
        "data": {
            "productUpdate": {
                "product": None,
                "userErrors": [{"field": ["seo", "title"], "message": "Title is too long"}],
            }
        }
    }


# --- Fixtures Google Search Console ---


@pytest.fixture
def gsc_response() -> dict:
    """Réponse API GSC simulée pour une requête de performance."""
    return {
        "rows": [
            {
                "keys": ["/products/croquettes-chien-senior"],
                "clicks": 42,
                "impressions": 850,
                "ctr": 0.0494,
                "position": 14.3,
            },
            {
                "keys": ["/products/croquettes-chat-adulte"],
                "clicks": 5,
                "impressions": 320,
                "ctr": 0.0156,
                "position": 22.1,
            },
        ]
    }


# --- Fixtures PageSpeed ---


@pytest.fixture
def pagespeed_response() -> dict:
    """Réponse API PageSpeed simulée."""
    return {
        "lighthouseResult": {
            "categories": {"performance": {"score": 0.72}},
            "audits": {
                "largest-contentful-paint": {"numericValue": 3200},
                "cumulative-layout-shift": {"numericValue": 0.08},
                "total-blocking-time": {"numericValue": 450},
            },
        }
    }
