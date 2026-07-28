"""Google OAuth scope union + configurable data directory."""

from __future__ import annotations

from pathlib import Path

from app import paths
from app.api.geo import _find_gsc_query_page_file
from app.ga4.oauth import GA4_SCOPES
from app.geo.clicks_since_validation import _cache_path
from app.google_scopes import GOOGLE_OAUTH_SCOPES
from app.gsc.client import GSC_SCOPES
from app.impact.report import _find_gsc_file

_WEBMASTERS = "https://www.googleapis.com/auth/webmasters.readonly"
_ANALYTICS = "https://www.googleapis.com/auth/analytics.readonly"


def test_shared_scopes_contain_both_apis():
    assert _WEBMASTERS in GOOGLE_OAUTH_SCOPES
    assert _ANALYTICS in GOOGLE_OAUTH_SCOPES


def test_gsc_and_ga4_request_the_same_union():
    # Both flows share one token row, so both must grant both scopes — otherwise
    # connecting one clobbers the other (the 403 "insufficient scopes" bug).
    assert set(GSC_SCOPES) == set(GOOGLE_OAUTH_SCOPES)
    assert set(GA4_SCOPES) == set(GOOGLE_OAUTH_SCOPES)


def test_data_dir_honors_env(monkeypatch, tmp_path):
    target = tmp_path / "mounted" / "raw"
    monkeypatch.setenv("DATA_DIR", str(target))
    assert paths.data_dir() == target


def test_data_dir_defaults_to_repo_data_raw(monkeypatch):
    monkeypatch.delenv("DATA_DIR", raising=False)
    resolved = paths.data_dir()
    assert resolved.name == "raw"
    assert resolved.parent.name == "data"


def test_no_module_hardcodes_the_raw_data_dir():
    """Every module must resolve the raw-data dir through `data_dir()`.

    Hardcoding `<repo>/data/raw` silently ignores DATA_DIR, so on a deployment
    with a mounted disk the writer and the reader can end up on different
    filesystems — the GSC CSVs were written to the disk and read from the
    ephemeral build directory, so Search Console looked permanently
    disconnected.
    """
    app_root = Path(paths.__file__).parent
    offenders = [
        path.relative_to(app_root.parent)
        for path in app_root.rglob("*.py")
        if path.name != "paths.py" and '"data" / "raw"' in path.read_text(encoding="utf-8")
    ]
    assert offenders == []


def test_per_call_path_resolvers_honor_data_dir(monkeypatch, tmp_path):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    shop = "shop.myshopify.com"
    (tmp_path / shop).mkdir(parents=True)
    (tmp_path / shop / "gsc_performance.csv").write_text("", encoding="utf-8")
    (tmp_path / shop / "gsc_query_page.csv").write_text("", encoding="utf-8")

    assert _find_gsc_file(shop) == tmp_path / shop / "gsc_performance.csv"
    assert _find_gsc_query_page_file(shop) == tmp_path / shop / "gsc_query_page.csv"
    assert _cache_path(shop) == tmp_path / shop / "clicks_since_validation.json"
