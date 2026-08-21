"""Tests for single-use quota reset codes."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

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
    # plan grants write plan_override via shop_config_store, which uses its
    # own module-level DB_PATH — point it at the test DB (never the real one).
    monkeypatch.setattr("app.shop_config_store.DB_PATH", path)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    return path


def test_build_code_is_deterministic_and_well_formed() -> None:
    code = build_code("launch01", SECRET)
    assert code.startswith("GEO-LAUNCH01-")
    assert code == build_code("LAUNCH01", SECRET)
    assert len(code.split("-")[2]) == 8


def test_build_code_rejects_bad_base() -> None:
    with pytest.raises(ValueError):
        build_code("ab", SECRET)


def test_redeem_resets_every_usage_kind(db: Path) -> None:
    record_usage(SHOP, "analysis", db)
    record_product_analysis(SHOP, "gid://shopify/Product/1", db)
    record_usage(SHOP, "blog", db)

    result = redeem_quota_code(SHOP, build_code("VIP1", SECRET), db_path=db)

    assert result["reset_events"] == 3
    assert get_usage(SHOP, "analysis", db) == 0
    assert get_usage(SHOP, "blog", db) == 0


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


def test_reset_usage_window_clears_every_kind(db: Path) -> None:
    """Blog counts too: a "quota reset" that spares a counter is a trap."""
    from app.billing.quotas import reset_usage_window

    record_usage(SHOP, "analysis", db)
    record_product_analysis(SHOP, "gid://shopify/Product/9", db)
    record_usage(SHOP, "blog", db)
    assert reset_usage_window(SHOP, db) == 3
    assert get_usage(SHOP, "analysis", db) == 0
    assert get_usage(SHOP, "blog", db) == 0


def test_reset_usage_window_leaves_other_shops_alone(db: Path) -> None:
    from app.billing.quotas import reset_usage_window

    record_usage(SHOP, "analysis", db)
    record_usage("neighbour.myshopify.com", "blog", db)
    assert reset_usage_window(SHOP, db) == 1
    assert get_usage("neighbour.myshopify.com", "blog", db) == 1


def test_plan_grant_codes_switch_plan_and_reset_quotas(db: Path) -> None:
    from app.billing.subscription_store import get_plan_for_shop

    record_usage(SHOP, "analysis", db)
    code = build_code("VIPPRO1", SECRET, "pro")
    assert code.startswith("GEOPRO-")
    with patch("app.apply.theme_entitlement.set_theme_entitlement"):
        result = redeem_quota_code(SHOP, code, db_path=db)
    assert result["granted_plan"] == "pro"
    assert result["reset_events"] == 1  # free→pro upgrade resets usage
    assert get_plan_for_shop(SHOP, db) == "pro"


def test_agency_grant_code_uses_geobig_prefix(db: Path) -> None:
    code = build_code("VIPBIG1", SECRET, "agency")
    assert code.startswith("GEOBIG-")
    with patch("app.apply.theme_entitlement.set_theme_entitlement"):
        result = redeem_quota_code(SHOP, code, db_path=db)
    assert result["granted_plan"] == "agency"


def test_plan_grant_signature_is_plan_bound(db: Path) -> None:
    """A GEO- reset signature must not validate as a GEOPRO- grant."""
    reset_code = build_code("SAME1", SECRET)
    sig = reset_code.split("-")[-1]
    with pytest.raises(InvalidQuotaCode):
        redeem_quota_code(SHOP, f"GEOPRO-SAME1-{sig}", db_path=db)


def test_plan_grant_code_is_single_use(db: Path) -> None:
    code = build_code("VIPPRO2", SECRET, "pro")
    with patch("app.apply.theme_entitlement.set_theme_entitlement"):
        redeem_quota_code(SHOP, code, db_path=db)
        with pytest.raises(QuotaCodeAlreadyUsed):
            redeem_quota_code("other.myshopify.com", code, db_path=db)


def test_a_failed_redeem_releases_the_code(db: Path) -> None:
    """A code spent on a redeem that then failed must stay usable.

    Production burned three codes this way: the row was committed, the quota
    reset raised, and the merchant was left with a code that could never work.
    """
    code = build_code("RETRY1", SECRET)
    with (
        patch("app.billing.quotas.reset_usage_window", side_effect=RuntimeError("boom")),
        pytest.raises(RuntimeError),
    ):
        redeem_quota_code(SHOP, code, db_path=db)

    assert redeem_quota_code(SHOP, code, db_path=db)["reset_events"] == 0


# ── Time-limited plan grants ──────────────────────────────────────────────────


def test_timed_grant_code_carries_its_duration_in_the_prefix() -> None:
    code = build_code("TRIAL01", SECRET, "pro", 30)
    assert code.startswith("GEOPRO30-TRIAL01-")


def test_signature_is_bound_to_the_duration(db: Path) -> None:
    """Editing 30 into 90 must not yield a longer valid grant."""
    code = build_code("TRIAL02", SECRET, "pro", 30)
    forged = code.replace("GEOPRO30-", "GEOPRO90-", 1)
    with pytest.raises(InvalidQuotaCode):
        redeem_quota_code(SHOP, forged, db_path=db)


def test_timed_grant_sets_an_expiry_and_expires(db: Path) -> None:
    from app.billing.subscription_store import get_plan_for_shop
    from app.shop_config_store import get_shop_config, set_shop_config

    code = build_code("TRIAL03", SECRET, "pro", 30)
    with patch("app.apply.theme_entitlement.set_theme_entitlement"):
        result = redeem_quota_code(SHOP, code, db_path=db)

    assert result["expires_at"]
    assert get_plan_for_shop(SHOP, db_path=db) == "pro"

    set_shop_config(SHOP, "plan_override_expires_at", "2020-01-01T00:00:00+00:00")
    assert get_plan_for_shop(SHOP, db_path=db) == "free"
    # The override itself is left in place; only its deadline decides.
    assert get_shop_config(SHOP, "plan_override") == "pro"


def test_indefinite_grant_clears_a_previous_expiry(db: Path) -> None:
    """A code with no duration must not inherit an earlier code's deadline."""
    from app.billing.subscription_store import get_plan_for_shop
    from app.shop_config_store import set_shop_config

    set_shop_config(SHOP, "plan_override_expires_at", "2020-01-01T00:00:00+00:00")
    with patch("app.apply.theme_entitlement.set_theme_entitlement"):
        redeem_quota_code(SHOP, build_code("FOREVER1", SECRET, "pro"), db_path=db)

    assert get_plan_for_shop(SHOP, db_path=db) == "pro"


def test_reset_codes_reject_a_duration() -> None:
    with pytest.raises(ValueError):
        build_code("NODAYS1", SECRET, None, 30)


def test_unreadable_expiry_does_not_revoke_access(db: Path) -> None:
    """A corrupted deadline must not silently cut a merchant off."""
    from app.billing.subscription_store import get_plan_for_shop
    from app.shop_config_store import set_shop_config

    with patch("app.apply.theme_entitlement.set_theme_entitlement"):
        redeem_quota_code(SHOP, build_code("CORRUPT1", SECRET, "pro"), db_path=db)
    set_shop_config(SHOP, "plan_override_expires_at", "not-a-date")

    assert get_plan_for_shop(SHOP, db_path=db) == "pro"
