"""Tests for competitor crawl config env resolution."""

from __future__ import annotations

from app.market_analysis.competitor_crawl.config import CompetitorCrawlConfig


def test_from_env_disabled_by_default_when_var_absent(monkeypatch) -> None:
    monkeypatch.delenv("COMPETITOR_CRAWL_ENABLED", raising=False)
    assert CompetitorCrawlConfig.from_env().enabled is False


def test_for_market_analysis_enabled_by_default_when_var_absent(monkeypatch) -> None:
    monkeypatch.delenv("COMPETITOR_CRAWL_ENABLED", raising=False)
    assert CompetitorCrawlConfig.for_market_analysis().enabled is True


def test_for_market_analysis_respects_explicit_disable(monkeypatch) -> None:
    monkeypatch.setenv("COMPETITOR_CRAWL_ENABLED", "false")
    assert CompetitorCrawlConfig.for_market_analysis().enabled is False


def test_for_market_analysis_keeps_env_caps(monkeypatch) -> None:
    monkeypatch.delenv("COMPETITOR_CRAWL_ENABLED", raising=False)
    monkeypatch.setenv("COMPETITOR_CRAWL_MAX_URLS_PER_PRODUCT", "2")
    monkeypatch.setenv("COMPETITOR_CRAWL_MAX_URLS_PER_RUN", "20")
    config = CompetitorCrawlConfig.for_market_analysis()
    assert config.max_urls_per_product == 2
    assert config.max_urls_per_run == 20
