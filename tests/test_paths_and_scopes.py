"""Google OAuth scope union + configurable data directory."""

from __future__ import annotations

from app import paths
from app.ga4.oauth import GA4_SCOPES
from app.google_scopes import GOOGLE_OAUTH_SCOPES
from app.gsc.client import GSC_SCOPES

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
