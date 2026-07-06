"""Tests for the full agent-activity JSON export."""

from __future__ import annotations

from pathlib import Path

from app.agent_schedule.export import build_export
from app.db import init_db

SHOP = "export.myshopify.com"


def test_export_has_no_duplicated_events_section(tmp_path: Path) -> None:
    # continuous_improvement "events" and geo_events read the same ledger:
    # the export keeps only geo_events so the file is not doubled.
    db = tmp_path / "history.db"
    init_db(db)

    export = build_export(SHOP, db_path=db)

    assert "events" not in export
    assert export["geo_events"] == []
    assert export["shop"] == SHOP
    assert export["errors"] == []
    assert export["effectiveness"]["shop"] == SHOP
