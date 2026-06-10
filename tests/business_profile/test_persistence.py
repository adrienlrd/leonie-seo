"""Tests for business profile persistence via the analysis_artifacts DB layer."""

from __future__ import annotations

import importlib
import json
from pathlib import Path

import pytest

from app.db import init_db

SHOP = "persistence.myshopify.com"


@pytest.fixture()
def jobs_mod(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    import app.business_profile.jobs as jobs

    importlib.reload(jobs)
    return jobs


@pytest.fixture()
def db_path(tmp_path: Path) -> Path:
    path = tmp_path / "history.db"
    init_db(path)
    return path


def test_save_business_profile_dual_writes_file_and_db(jobs_mod, db_path: Path) -> None:
    data = {"status": "validated", "business_name": "Acme"}

    jobs_mod.save_business_profile(SHOP, data, db_path=db_path)

    file_path = jobs_mod._DATA_DIR / SHOP / "business_profile.json"
    assert json.loads(file_path.read_text(encoding="utf-8")) == data

    from app.analysis_artifacts import load_artifact

    assert load_artifact(SHOP, "business_profile", db_path=db_path) == data


def test_load_business_profile_falls_back_to_db_when_file_missing(jobs_mod, db_path: Path) -> None:
    data = {"status": "validated", "business_name": "Acme"}
    jobs_mod.save_business_profile(SHOP, data, db_path=db_path)

    file_path = jobs_mod._DATA_DIR / SHOP / "business_profile.json"
    file_path.unlink()

    assert jobs_mod.load_business_profile(SHOP, db_path=db_path) == data


def test_load_business_profile_returns_none_when_neither_exists(jobs_mod, db_path: Path) -> None:
    assert jobs_mod.load_business_profile(SHOP, db_path=db_path) is None
