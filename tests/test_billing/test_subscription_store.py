"""Tests for billing subscription store."""

from __future__ import annotations

import pytest

from app.billing.subscription_store import (
    get_plan_for_shop,
    get_subscription,
    get_subscription_by_id,
    update_subscription_status,
    upsert_subscription,
)
from app.db import init_db

SHOP = "store.myshopify.com"
SUB_ID = "gid://shopify/AppSubscription/123"


@pytest.fixture()
def db(tmp_path):
    path = tmp_path / "test.db"
    init_db(path)
    return path


def test_upsert_creates_subscription(db):
    upsert_subscription(SHOP, "pro", "active", SUB_ID, db_path=db)
    sub = get_subscription(SHOP, db_path=db)
    assert sub["shop"] == SHOP
    assert sub["plan"] == "pro"
    assert sub["status"] == "active"
    assert sub["subscription_id"] == SUB_ID


def test_upsert_overwrites_existing(db):
    upsert_subscription(SHOP, "pro", "active", SUB_ID, db_path=db)
    upsert_subscription(SHOP, "agency", "active", "gid://shopify/AppSubscription/999", db_path=db)
    sub = get_subscription(SHOP, db_path=db)
    assert sub["plan"] == "agency"
    assert sub["subscription_id"] == "gid://shopify/AppSubscription/999"


def test_get_subscription_returns_none_for_unknown_shop(db):
    assert get_subscription("unknown.myshopify.com", db_path=db) is None


def test_get_subscription_by_id_found(db):
    upsert_subscription(SHOP, "pro", "active", SUB_ID, db_path=db)
    sub = get_subscription_by_id(SUB_ID, db_path=db)
    assert sub is not None
    assert sub["shop"] == SHOP


def test_get_subscription_by_id_not_found(db):
    assert get_subscription_by_id("gid://shopify/AppSubscription/999", db_path=db) is None


def test_update_subscription_status_returns_true(db):
    upsert_subscription(SHOP, "pro", "pending", SUB_ID, db_path=db)
    updated = update_subscription_status(SUB_ID, "active", db_path=db)
    assert updated is True
    sub = get_subscription(SHOP, db_path=db)
    assert sub["status"] == "active"


def test_update_subscription_status_returns_false_for_unknown(db):
    updated = update_subscription_status("gid://shopify/AppSubscription/999", "active", db_path=db)
    assert updated is False


def test_get_plan_for_shop_active_pro(db):
    upsert_subscription(SHOP, "pro", "active", SUB_ID, db_path=db)
    assert get_plan_for_shop(SHOP, db_path=db) == "pro"


def test_get_plan_for_shop_active_agency(db):
    upsert_subscription(SHOP, "agency", "active", SUB_ID, db_path=db)
    assert get_plan_for_shop(SHOP, db_path=db) == "agency"


def test_get_plan_for_shop_pending_returns_free(db):
    upsert_subscription(SHOP, "pro", "pending", SUB_ID, db_path=db)
    assert get_plan_for_shop(SHOP, db_path=db) == "free"


def test_get_plan_for_shop_no_subscription_returns_free(db):
    assert get_plan_for_shop("new-shop.myshopify.com", db_path=db) == "free"


def test_get_plan_for_shop_cancelled_returns_free(db):
    upsert_subscription(SHOP, "pro", "cancelled", SUB_ID, db_path=db)
    assert get_plan_for_shop(SHOP, db_path=db) == "free"
