"""Tests for per-plan usage quotas and the plan_override access-code path."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.billing.quotas import (
    PLAN_QUOTAS,
    QuotaExceeded,
    auto_analysis_allowed,
    check_product_analysis_quota,
    check_quota,
    get_usage,
    product_analysis_quota,
    product_cap,
    record_product_analysis,
    record_usage,
)
from app.billing.subscription_store import get_plan_for_shop, upsert_subscription
from app.db import init_db
from app.db_adapter import get_conn

SHOP = "store.myshopify.com"


@pytest.fixture()
def db(tmp_path, monkeypatch):
    path = tmp_path / "test.db"
    init_db(path)
    monkeypatch.setattr("app.billing.quotas.DB_PATH", path)
    return path


def test_record_and_get_usage_counts_within_window(db):
    assert get_usage(SHOP, "blog", db_path=db) == 0
    record_usage(SHOP, "blog", db_path=db)
    record_usage(SHOP, "blog", db_path=db)
    assert get_usage(SHOP, "blog", db_path=db) == 2
    assert get_usage(SHOP, "analysis", db_path=db) == 0


def test_get_usage_ignores_events_older_than_window(db):
    old = (datetime.now(UTC) - timedelta(days=29)).isoformat()
    with get_conn(db) as conn:
        conn.execute(
            "INSERT INTO usage_events (shop, kind, created_at) VALUES (?, ?, ?)",
            (SHOP, "blog", old),
        )
    assert get_usage(SHOP, "blog", db_path=db) == 0


def test_check_quota_raises_when_free_blog_quota_reached(db):
    for _ in range(PLAN_QUOTAS["free"]["blog"]):
        record_usage(SHOP, "blog", db_path=db)
    with pytest.raises(QuotaExceeded) as exc_info:
        check_quota(SHOP, "blog", db_path=db)
    payload = exc_info.value.payload()
    assert payload["error"] == "quota_exceeded"
    assert payload["plan"] == "free"
    assert payload["used"] == 3
    assert payload["quota"] == 3
    assert payload["upgrade"] == "pro"


def test_check_quota_passes_under_limit(db):
    record_usage(SHOP, "blog", db_path=db)
    check_quota(SHOP, "blog", db_path=db)


def test_check_quota_free_allows_single_analysis(db):
    check_quota(SHOP, "analysis", db_path=db)
    record_usage(SHOP, "analysis", db_path=db)
    with pytest.raises(QuotaExceeded):
        check_quota(SHOP, "analysis", db_path=db)


def test_check_quota_pro_plan_has_higher_limits(db):
    upsert_subscription(SHOP, "pro", "active", "gid://sub/1", db_path=db)
    for _ in range(4):
        record_usage(SHOP, "analysis", db_path=db)
    check_quota(SHOP, "analysis", db_path=db)
    record_usage(SHOP, "analysis", db_path=db)
    with pytest.raises(QuotaExceeded):
        check_quota(SHOP, "analysis", db_path=db)


def test_check_quota_rejects_unknown_kind(db):
    with pytest.raises(ValueError):
        check_quota(SHOP, "products", db_path=db)


def test_product_cap_per_plan(db):
    assert product_cap(SHOP, db_path=db) == 3
    upsert_subscription(SHOP, "pro", "active", "gid://sub/1", db_path=db)
    assert product_cap(SHOP, db_path=db) == 15
    upsert_subscription(SHOP, "agency", "active", "gid://sub/2", db_path=db)
    assert product_cap(SHOP, db_path=db) == 35


def test_product_analysis_quota_per_plan(db):
    assert product_analysis_quota(SHOP, db_path=db) == 1
    upsert_subscription(SHOP, "pro", "active", "gid://sub/1", db_path=db)
    assert product_analysis_quota(SHOP, db_path=db) == 3
    upsert_subscription(SHOP, "agency", "active", "gid://sub/2", db_path=db)
    assert product_analysis_quota(SHOP, db_path=db) == 5


def test_product_analysis_quota_is_per_product(db):
    # Free plan: one analysis per product; a second on the same product is blocked.
    check_product_analysis_quota(SHOP, "prod-A", db_path=db)
    record_product_analysis(SHOP, "prod-A", db_path=db)
    with pytest.raises(QuotaExceeded) as exc_info:
        check_product_analysis_quota(SHOP, "prod-A", db_path=db)
    assert exc_info.value.payload()["kind"] == "product_analysis"
    # A different product still has its own budget.
    check_product_analysis_quota(SHOP, "prod-B", db_path=db)


def test_auto_analysis_gated_by_plan(db):
    assert auto_analysis_allowed(SHOP, db_path=db) is False
    upsert_subscription(SHOP, "pro", "active", "gid://sub/1", db_path=db)
    assert auto_analysis_allowed(SHOP, db_path=db) is True


def test_plan_override_takes_precedence_over_subscription(db, monkeypatch):
    monkeypatch.setattr(
        "app.shop_config_store.get_shop_config", lambda shop, key: "agency"
    )
    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert get_plan_for_shop(SHOP, db_path=db) == "agency"


def test_plan_override_invalid_value_falls_back_to_subscription(db, monkeypatch):
    monkeypatch.setattr(
        "app.shop_config_store.get_shop_config", lambda shop, key: "not-a-plan"
    )
    assert get_plan_for_shop(SHOP, db_path=db) == "free"
