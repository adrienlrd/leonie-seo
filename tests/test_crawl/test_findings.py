"""Tests for Crawl L3 finding aggregation."""

from __future__ import annotations

from app.crawl.findings import (
    findings_from_mini_results,
    findings_from_sitemap_diff,
    summarize_findings,
)
from app.crawl.mini import MiniCrawlResult


def test_findings_from_sitemap_diff_marks_orphan_sitemap_urls() -> None:
    findings = findings_from_sitemap_diff({
        "in_sitemap_not_snapshot": ["https://example.com/orphan"],
        "in_snapshot_not_sitemap": [],
    })

    assert findings[0]["issue_type"] == "sitemap_url_missing_from_snapshot"
    assert findings[0]["source"] == "crawl_l3"


def test_findings_from_mini_results_detects_404_redirect_chain_and_invalid_jsonld() -> None:
    result = MiniCrawlResult(
        url="https://example.com/missing",
        allowed_by_robots=True,
        status_code=404,
        redirect_chain=["https://example.com/a", "https://example.com/b"],
        jsonld_valid=False,
    )

    findings = findings_from_mini_results([result])
    issue_types = {finding["issue_type"] for finding in findings}

    assert {"page_404", "redirect_chain", "invalid_jsonld"} <= issue_types
    assert summarize_findings(findings)["issue_count"] == 3
