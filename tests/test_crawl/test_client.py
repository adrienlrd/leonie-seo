"""Tests for technical crawl client helpers."""

from __future__ import annotations

import json

from app.crawl.client import (
    analyze_crawl_csv,
    latest_crawl_status,
    store_crawl_report,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_OVERVIEW_HEADER = (
    "Address,Title 1,Meta Description 1,Status Code,Indexability,Canonical Link Element 1\n"
)


def _overview_csv(*rows: str) -> bytes:
    return (_OVERVIEW_HEADER + "\n".join(rows) + "\n").encode("utf-8")


_REDIRECTS_HEADER = "Address,Redirect URL,Status Code,Redirect Chain Length\n"


def _redirects_csv(*rows: str) -> bytes:
    return (_REDIRECTS_HEADER + "\n".join(rows) + "\n").encode("utf-8")


# ---------------------------------------------------------------------------
# analyze_crawl_csv
# ---------------------------------------------------------------------------


def test_analyze_detects_404_pages() -> None:
    csv_bytes = _overview_csv(
        "https://example.com/missing,Title A,Desc A,404,Non-Indexable,",
        "https://example.com/ok,Title B,Desc B,200,Indexable,https://example.com/ok",
    )
    report = analyze_crawl_csv(csv_bytes)

    issue_types = [i["issue_type"] for i in report["issues"]]
    assert "page_404" in issue_types
    assert report["url_count"] == 2
    assert report["by_severity"].get("critical", 0) >= 1


def test_analyze_detects_duplicate_titles() -> None:
    csv_bytes = _overview_csv(
        "https://example.com/a,Same Title,Desc A,200,Indexable,https://example.com/a",
        "https://example.com/b,Same Title,Desc B,200,Indexable,https://example.com/b",
    )
    report = analyze_crawl_csv(csv_bytes)

    dup_title_issues = [i for i in report["issues"] if i["issue_type"] == "duplicate_title"]
    assert len(dup_title_issues) == 2
    assert report["by_severity"].get("high", 0) >= 2


def test_analyze_detects_duplicate_meta_descriptions() -> None:
    csv_bytes = _overview_csv(
        "https://example.com/a,Title A,Same description,200,Indexable,https://example.com/a",
        "https://example.com/b,Title B,Same description,200,Indexable,https://example.com/b",
    )
    report = analyze_crawl_csv(csv_bytes)

    dup_desc_issues = [i for i in report["issues"] if i["issue_type"] == "duplicate_meta_description"]
    assert len(dup_desc_issues) == 2


def test_analyze_detects_missing_canonical_on_indexable_page() -> None:
    csv_bytes = _overview_csv(
        "https://example.com/page,Title A,Desc A,200,Indexable,",
    )
    report = analyze_crawl_csv(csv_bytes)

    issue_types = [i["issue_type"] for i in report["issues"]]
    assert "missing_canonical" in issue_types


def test_analyze_detects_non_self_canonical() -> None:
    csv_bytes = _overview_csv(
        "https://example.com/page,Title A,Desc A,200,Indexable,https://example.com/other",
    )
    report = analyze_crawl_csv(csv_bytes)

    issue_types = [i["issue_type"] for i in report["issues"]]
    assert "non_self_canonical" in issue_types


def test_analyze_no_canonical_issue_when_self_canonical() -> None:
    csv_bytes = _overview_csv(
        "https://example.com/page,Title A,Desc A,200,Indexable,https://example.com/page",
    )
    report = analyze_crawl_csv(csv_bytes)

    canonical_issues = [
        i for i in report["issues"]
        if i["issue_type"] in {"missing_canonical", "non_self_canonical"}
    ]
    assert canonical_issues == []


def test_analyze_detects_redirect_chains() -> None:
    redirects = _redirects_csv(
        "https://example.com/old,,301,2",
    )
    csv_bytes = _overview_csv(
        "https://example.com/ok,Title A,Desc A,200,Indexable,https://example.com/ok",
    )
    report = analyze_crawl_csv(csv_bytes, redirects_bytes=redirects)

    issue_types = [i["issue_type"] for i in report["issues"]]
    assert "redirect_chain" in issue_types


def test_analyze_detects_302_redirects() -> None:
    redirects = _redirects_csv(
        "https://example.com/temp,https://example.com/dest,302,1",
    )
    csv_bytes = _overview_csv(
        "https://example.com/ok,Title A,Desc A,200,Indexable,https://example.com/ok",
    )
    report = analyze_crawl_csv(csv_bytes, redirects_bytes=redirects)

    issue_types = [i["issue_type"] for i in report["issues"]]
    assert "temporary_redirect_302" in issue_types


def test_analyze_returns_zero_issues_on_clean_crawl() -> None:
    csv_bytes = _overview_csv(
        "https://example.com/a,Title A,Desc A,200,Indexable,https://example.com/a",
        "https://example.com/b,Title B,Desc B,200,Indexable,https://example.com/b",
    )
    report = analyze_crawl_csv(csv_bytes)

    non_canonical = [
        i for i in report["issues"]
        if i["issue_type"] not in {"missing_canonical", "non_self_canonical"}
    ]
    assert non_canonical == []


# ---------------------------------------------------------------------------
# store_crawl_report / latest_crawl_status
# ---------------------------------------------------------------------------


def test_store_and_load_crawl_report(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("app.crawl.client._DATA_DIR", tmp_path)

    report = {
        "url_count": 10,
        "issue_count": 3,
        "by_severity": {"critical": 1, "high": 2},
        "issues": [],
        "analyzed_at": "2026-05-16T10:00:00+00:00",
    }
    latest_path, timestamped_path = store_crawl_report("store.myshopify.com", report)

    assert latest_path.exists()
    assert timestamped_path.exists()
    assert json.loads(latest_path.read_text())["url_count"] == 10
    assert list((tmp_path / "store.myshopify.com").glob("crawl_report_*.json"))


def test_latest_crawl_status_returns_available_false_when_no_report(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("app.crawl.client._DATA_DIR", tmp_path)

    status = latest_crawl_status("store.myshopify.com")

    assert status["available"] is False
    assert status["url_count"] == 0
    assert status["issues"] == []


def test_latest_crawl_status_returns_report(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("app.crawl.client._DATA_DIR", tmp_path)

    report = {
        "url_count": 42,
        "issue_count": 5,
        "by_severity": {"critical": 2},
        "issues": [{"url": "https://example.com/x", "issue_type": "page_404", "severity": "critical", "detail": ""}],
        "analyzed_at": "2026-05-16T10:00:00+00:00",
    }
    store_crawl_report("store.myshopify.com", report)

    status = latest_crawl_status("store.myshopify.com")

    assert status["available"] is True
    assert status["url_count"] == 42
    assert status["issue_count"] == 5
    assert status["imported_at"] is not None
    assert status["issues"][0]["issue_type"] == "page_404"
