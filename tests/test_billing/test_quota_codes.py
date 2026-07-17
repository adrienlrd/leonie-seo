"""Tests for single-use quota reset codes."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.billing.quota_codes import (
    InvalidQuotaCode,
    QuotaCodeAlreadyUsed,
    build_code,
    redeem_quota_code,
)
from app.billing.quotas import get_usage, record_product_analysis, record_usage
from app.db import init_db

SHOP = "test.myshopify.com"
SECRET = "s3cret-formula"


@pytest.fixture()
def db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "test.db"
    init_db(path)
    monkeypatch.setenv("QUOTA_CODE_SECRET", SECRET)
    return path


def test_build_code_is_deterministic_and_well_formed() -> None:
    code = build_code("launch01", SECRET)
    assert code.startswith("GEO-LAUNCH01-")
    assert code == build_code("LAUNCH01", SECRET)
    assert len(code.split("-")[2]) == 8


def test_build_code_rejects_bad_base() -> None:
    with pytest.raises(ValueError):
        build_code("ab", SECRET)


def test_redeem_resets_analysis_usage_only(db: Path) -> None:
    record_usage(SHOP, "analysis", db)
    record_product_analysis(SHOP, "gid://shopify/Product/1", db)
    record_usage(SHOP, "blog", db)

    result = redeem_quota_code(SHOP, build_code("VIP1", SECRET), db_path=db)

    assert result["reset_events"] == 2
    assert get_usage(SHOP, "analysis", db) == 0
    assert get_usage(SHOP, "blog", db) == 1  # blog quota untouched


def test_redeem_is_single_use_even_for_another_shop(db: Path) -> None:
    code = build_code("VIP2", SECRET)
    redeem_quota_code(SHOP, code, db_path=db)
    with pytest.raises(QuotaCodeAlreadyUsed):
        redeem_quota_code("other.myshopify.com", code, db_path=db)


def test_redeem_rejects_wrong_signature(db: Path) -> None:
    with pytest.raises(InvalidQuotaCode):
        redeem_quota_code(SHOP, "GEO-VIP3-DEADBEEF", db_path=db)


def test_redeem_rejects_malformed_code(db: Path) -> None:
    with pytest.raises(InvalidQuotaCode):
        redeem_quota_code(SHOP, "not-a-code", db_path=db)


def test_redeem_disabled_without_secret(db: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("QUOTA_CODE_SECRET", raising=False)
    with pytest.raises(InvalidQuotaCode):
        redeem_quota_code(SHOP, build_code("VIP4", SECRET), db_path=db)


def test_redeem_is_case_insensitive_on_input(db: Path) -> None:
    code = build_code("VIP5", SECRET)
    result = redeem_quota_code(SHOP, code.lower(), db_path=db)
    assert result["reset_events"] == 0


def test_plan_upgrade_detection() -> None:
    from app.billing.quotas import is_plan_upgrade

    assert is_plan_upgrade("free", "pro") is True
    assert is_plan_upgrade("pro", "agency") is True
    assert is_plan_upgrade("free", "agency") is True
    assert is_plan_upgrade("pro", "pro") is False
    assert is_plan_upgrade("agency", "pro") is False


def test_reset_analysis_usage_clears_only_analysis_kinds(db: Path) -> None:
    from app.billing.quotas import reset_analysis_usage

    record_usage(SHOP, "analysis", db)
    record_product_analysis(SHOP, "gid://shopify/Product/9", db)
    record_usage(SHOP, "blog", db)
    assert reset_analysis_usage(SHOP, db) == 2
    assert get_usage(SHOP, "analysis", db) == 0
    assert get_usage(SHOP, "blog", db) == 1
