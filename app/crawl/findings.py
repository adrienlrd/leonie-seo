"""Crawl L3 finding aggregation and persistence."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from app.crawl.mini import MiniCrawlResult
from app.db_adapter import DB_PATH, get_conn


def findings_from_sitemap_diff(diff: dict[str, list[str]]) -> list[dict[str, Any]]:
    """Convert sitemap/snapshot differences into crawl findings."""
    findings: list[dict[str, Any]] = []
    for url in diff.get("in_sitemap_not_snapshot", []):
        findings.append({
            "url": url,
            "issue_type": "sitemap_url_missing_from_snapshot",
            "severity": "medium",
            "detail": "URL appears in sitemap but not in the Shopify snapshot.",
            "source": "crawl_l3",
        })
    for url in diff.get("in_snapshot_not_sitemap", []):
        findings.append({
            "url": url,
            "issue_type": "snapshot_url_missing_from_sitemap",
            "severity": "low",
            "detail": "Shopify snapshot URL was not found in the sitemap.",
            "source": "crawl_l3",
        })
    return findings


def findings_from_mini_results(results: list[MiniCrawlResult]) -> list[dict[str, Any]]:
    """Convert mini-crawl results into normalized findings."""
    findings: list[dict[str, Any]] = []
    for result in results:
        if not result.allowed_by_robots:
            findings.append({
                "url": result.url,
                "issue_type": "blocked_by_robots",
                "severity": "info",
                "detail": "robots.txt disallows this URL for the Léonie crawler.",
                "source": "crawl_l3",
            })
            continue
        if result.error:
            findings.append({
                "url": result.url,
                "issue_type": "crawl_error",
                "severity": "high",
                "detail": result.error,
                "source": "crawl_l3",
            })
            continue
        if result.status_code == 404:
            findings.append({
                "url": result.url,
                "issue_type": "page_404",
                "severity": "critical",
                "detail": "Page returns 404 during Crawl L3 mini-crawl.",
                "source": "crawl_l3",
            })
        elif result.status_code and result.status_code >= 500:
            findings.append({
                "url": result.url,
                "issue_type": "server_error",
                "severity": "critical",
                "detail": f"Page returned HTTP {result.status_code}.",
                "source": "crawl_l3",
            })
        if len(result.redirect_chain) > 1:
            findings.append({
                "url": result.url,
                "issue_type": "redirect_chain",
                "severity": "high",
                "detail": f"Redirect chain has {len(result.redirect_chain)} hops before final URL.",
                "source": "crawl_l3",
            })
        if result.status_code == 200 and not result.canonical:
            findings.append({
                "url": result.url,
                "issue_type": "missing_canonical",
                "severity": "low",
                "detail": "No canonical tag found in rendered HTML.",
                "source": "crawl_l3",
            })
        if not result.jsonld_valid:
            findings.append({
                "url": result.url,
                "issue_type": "invalid_jsonld",
                "severity": "high",
                "detail": "At least one JSON-LD block could not be parsed.",
                "source": "crawl_l3",
            })
    return findings


def summarize_findings(findings: list[dict[str, Any]]) -> dict[str, Any]:
    """Return issue counts by severity."""
    by_severity: dict[str, int] = {}
    for finding in findings:
        severity = str(finding.get("severity") or "info")
        by_severity[severity] = by_severity.get(severity, 0) + 1
    return {
        "issue_count": len(findings),
        "by_severity": by_severity,
    }


def store_crawl_findings(
    shop: str,
    findings: list[dict[str, Any]],
    *,
    db_path=None,
) -> int:
    """Persist Crawl L3 findings in the canonical DB table."""
    if not findings:
        return 0
    path = db_path if db_path is not None else DB_PATH
    now = datetime.now(UTC).isoformat()
    rows = [
        (
            shop,
            now,
            finding.get("source", "crawl_l3"),
            finding.get("url", ""),
            finding.get("issue_type", ""),
            finding.get("severity", "info"),
            finding.get("detail", ""),
            json.dumps(finding.get("metadata", {}), ensure_ascii=False),
        )
        for finding in findings
    ]
    with get_conn(path) as conn:
        for row in rows:
            conn.execute(
                """
                INSERT INTO crawl_findings
                    (shop, created_at, source, url, issue_type, severity, detail, metadata_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                row,
            )
    return len(rows)
