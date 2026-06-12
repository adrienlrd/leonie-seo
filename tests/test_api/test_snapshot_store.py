"""Tests for app.api.snapshot_store caching and single-flight dedup."""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from unittest.mock import patch

from app.api.snapshot_store import clear_snapshot_cache, load_snapshot_from_file_or_db

SHOP = "287c4a-bb.myshopify.com"


def _write_snapshot(tmp_path: Path) -> Path:
    path = tmp_path / "shopify_snapshot.json"
    path.write_text(json.dumps({"products": [{"id": "p1"}], "collections": []}), encoding="utf-8")
    return path


def setup_function() -> None:
    clear_snapshot_cache()


def test_load_snapshot_caches_result_within_ttl(tmp_path: Path) -> None:
    path = _write_snapshot(tmp_path)

    with patch("app.api.snapshot_store.json.loads", wraps=json.loads) as mocked_loads:
        first = load_snapshot_from_file_or_db(SHOP, path)
        second = load_snapshot_from_file_or_db(SHOP, path)

    assert first == second
    assert mocked_loads.call_count == 1


def test_concurrent_cold_cache_loads_share_a_single_read(tmp_path: Path) -> None:
    """Several requests missing the cache at once (e.g. the Measure page firing
    parallel /geo/* calls right after a restart) must only read the file once."""
    path = _write_snapshot(tmp_path)
    real_loads = json.loads

    def slow_loads(text: str):
        time.sleep(0.05)
        return real_loads(text)

    with patch("app.api.snapshot_store.json.loads", side_effect=slow_loads) as mocked_loads:
        results: list[dict] = []

        def worker() -> None:
            results.append(load_snapshot_from_file_or_db(SHOP, path))

        threads = [threading.Thread(target=worker) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

    assert mocked_loads.call_count == 1
    assert all(r == results[0] for r in results)
