"""Tests for the analysis_artifacts DB durability layer."""

from __future__ import annotations

import importlib
import json
from pathlib import Path

import pytest

from app.db import init_db


@pytest.fixture()
def jobs_mod(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    import app.market_analysis.jobs as jobs

    importlib.reload(jobs)
    return jobs


@pytest.fixture()
def db_path(tmp_path: Path) -> Path:
    path = tmp_path / "history.db"
    init_db(path)
    return path


SHOP = "persistence.myshopify.com"


def test_save_latest_result_dual_writes_file_and_db(jobs_mod, db_path: Path) -> None:
    data = {"status": "completed", "products": []}

    jobs_mod.save_latest_result(SHOP, data, db_path=db_path)

    file_path = jobs_mod._DATA_DIR / SHOP / "market_analysis_latest.json"
    assert json.loads(file_path.read_text(encoding="utf-8")) == data

    from app.analysis_artifacts import load_artifact

    assert load_artifact(SHOP, "market_analysis_latest", db_path=db_path) == data


def test_load_latest_result_falls_back_to_db_when_file_missing(jobs_mod, db_path: Path) -> None:
    data = {"status": "completed", "products": [{"product_id": "1"}]}
    jobs_mod.save_latest_result(SHOP, data, db_path=db_path)

    file_path = jobs_mod._DATA_DIR / SHOP / "market_analysis_latest.json"
    file_path.unlink()

    assert jobs_mod.load_latest_result(SHOP, db_path=db_path) == data


def test_load_latest_result_prefers_file_when_present(jobs_mod, db_path: Path) -> None:
    db_data = {"status": "completed", "products": [{"product_id": "old"}]}
    jobs_mod.save_latest_result(SHOP, db_data, db_path=db_path)

    file_data = {"status": "completed", "products": [{"product_id": "new"}]}
    file_path = jobs_mod._DATA_DIR / SHOP / "market_analysis_latest.json"
    file_path.write_text(json.dumps(file_data), encoding="utf-8")

    assert jobs_mod.load_latest_result(SHOP, db_path=db_path) == file_data


def test_load_latest_result_returns_none_when_neither_exists(jobs_mod, db_path: Path) -> None:
    assert jobs_mod.load_latest_result(SHOP, db_path=db_path) is None


def test_identifications_round_trip_via_db(jobs_mod, db_path: Path) -> None:
    data = {"gid://shopify/Product/1": "Best seller"}
    jobs_mod.save_identifications(SHOP, data, db_path=db_path)

    file_path = jobs_mod._DATA_DIR / SHOP / "market_analysis_identifications.json"
    file_path.unlink()

    assert jobs_mod.load_identifications(SHOP, db_path=db_path) == data


def test_merchant_facts_round_trip_via_db(jobs_mod, db_path: Path) -> None:
    jobs_mod.save_merchant_facts(SHOP, "gid://shopify/Product/1", {"material": "cotton"}, db_path=db_path)

    file_path = jobs_mod._DATA_DIR / SHOP / "market_analysis_merchant_facts.json"
    file_path.unlink()

    assert jobs_mod.load_merchant_facts(SHOP, db_path=db_path) == {
        "gid://shopify/Product/1": {"material": "cotton"}
    }


def test_save_and_load_artifact_degrade_gracefully_without_init_db(tmp_path: Path) -> None:
    """A DB without the analysis_artifacts table (init_db never ran) must not raise."""
    from app.analysis_artifacts import load_artifact, save_artifact

    missing_db = tmp_path / "no-such-schema.db"

    save_artifact(SHOP, "market_analysis_latest", {"status": "completed"}, db_path=missing_db)

    assert load_artifact(SHOP, "market_analysis_latest", db_path=missing_db) is None


def test_save_artifact_with_non_serializable_data_does_not_raise(db_path: Path) -> None:
    from app.analysis_artifacts import load_artifact, save_artifact

    save_artifact(SHOP, "market_analysis_latest", {"created_at": object()}, db_path=db_path)

    assert load_artifact(SHOP, "market_analysis_latest", db_path=db_path) is None
