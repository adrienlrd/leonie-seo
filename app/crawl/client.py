"""Technical crawl CSV analysis and storage for embedded app workflows."""

from __future__ import annotations

import io
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

_DATA_DIR = Path(__file__).parents[2] / "data" / "raw"


def _timestamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


# ---------------------------------------------------------------------------
# CSV parsing helpers (reuse Screaming Frog column names)
# ---------------------------------------------------------------------------

_OVERVIEW_COLS = {
    "Address": "url",
    "Title 1": "title",
    "Title 1 Length": "title_length",
    "Meta Description 1": "meta_description",
    "Meta Description 1 Length": "meta_description_length",
    "H1-1": "h1",
    "Status Code": "status_code",
    "Indexability": "indexability",
    "Canonical Link Element 1": "canonical",
    "Word Count": "word_count",
}

_REDIRECTS_COLS = {
    "Address": "from_url",
    "Redirect URL": "to_url",
    "Status Code": "status_code",
    "Redirect Chain Length": "chain_length",
}


def _load_df(csv_bytes: bytes, col_mapping: dict[str, str]) -> pd.DataFrame:
    df = pd.read_csv(io.BytesIO(csv_bytes), encoding="utf-8-sig", low_memory=False)
    available = {k: v for k, v in col_mapping.items() if k in df.columns}
    return df[list(available.keys())].rename(columns=available)


# ---------------------------------------------------------------------------
# Issue detectors operating on DataFrames
# ---------------------------------------------------------------------------

def _detect_404s(df: pd.DataFrame) -> list[dict]:
    if "status_code" not in df.columns:
        return []
    not_found = df[pd.to_numeric(df["status_code"], errors="coerce") == 404]
    return [
        {
            "url": str(row["url"]),
            "issue_type": "page_404",
            "severity": "critical",
            "detail": "Page returns 404 — add a 301 redirect or remove internal links.",
        }
        for _, row in not_found.iterrows()
        if pd.notna(row.get("url"))
    ]


def _detect_redirect_chains(df: pd.DataFrame) -> list[dict]:
    if "chain_length" not in df.columns:
        return []
    chains = df[pd.to_numeric(df["chain_length"], errors="coerce") > 1]
    issues = []
    for _, row in chains.iterrows():
        from_url = str(row.get("from_url", ""))
        issues.append(
            {
                "url": from_url,
                "issue_type": "redirect_chain",
                "severity": "high",
                "detail": (
                    f"Redirect chain (length {row.get('chain_length', '?')}) "
                    "— consolidate to a single 301."
                ),
            }
        )
    if "status_code" in df.columns:
        temp = df[pd.to_numeric(df["status_code"], errors="coerce") == 302]
        for _, row in temp.iterrows():
            from_url = str(row.get("from_url", ""))
            if not any(i["url"] == from_url for i in issues):
                issues.append(
                    {
                        "url": from_url,
                        "issue_type": "temporary_redirect_302",
                        "severity": "medium",
                        "detail": "302 temporary redirect — use 301 to preserve PageRank.",
                    }
                )
    return issues


def _detect_duplicate_titles(df: pd.DataFrame) -> list[dict]:
    if "title" not in df.columns:
        return []
    non_empty = df[df["title"].notna() & (df["title"].str.strip() != "")].copy()
    non_empty["_title_norm"] = non_empty["title"].str.strip().str.lower()
    counts = non_empty["_title_norm"].value_counts()
    duplicated = counts[counts > 1].index
    issues = []
    for _, row in non_empty[non_empty["_title_norm"].isin(duplicated)].iterrows():
        issues.append(
            {
                "url": str(row.get("url", "")),
                "issue_type": "duplicate_title",
                "severity": "high",
                "detail": f"Duplicate meta title: «{row['title']}»",
            }
        )
    return issues


def _detect_duplicate_descriptions(df: pd.DataFrame) -> list[dict]:
    if "meta_description" not in df.columns:
        return []
    non_empty = df[
        df["meta_description"].notna() & (df["meta_description"].str.strip() != "")
    ].copy()
    non_empty["_desc_norm"] = non_empty["meta_description"].str.strip().str.lower()
    counts = non_empty["_desc_norm"].value_counts()
    duplicated = counts[counts > 1].index
    issues = []
    for _, row in non_empty[non_empty["_desc_norm"].isin(duplicated)].iterrows():
        issues.append(
            {
                "url": str(row.get("url", "")),
                "issue_type": "duplicate_meta_description",
                "severity": "high",
                "detail": f"Duplicate meta description: «{str(row['meta_description'])[:60]}…»",
            }
        )
    return issues


def _detect_canonical_issues(df: pd.DataFrame) -> list[dict]:
    if "canonical" not in df.columns or "url" not in df.columns:
        return []
    issues = []
    for _, row in df.iterrows():
        url = str(row.get("url", "")).strip().rstrip("/")
        canonical_raw = row.get("canonical")
        canonical = "" if pd.isna(canonical_raw) else str(canonical_raw).strip().rstrip("/")
        if not url:
            continue
        if not canonical:
            indexability = str(row.get("indexability", "")).lower()
            if "indexable" in indexability:
                issues.append(
                    {
                        "url": url,
                        "issue_type": "missing_canonical",
                        "severity": "low",
                        "detail": "No canonical tag found on an indexable page.",
                    }
                )
        elif canonical != url and canonical != "nan":
            issues.append(
                {
                    "url": url,
                    "issue_type": "non_self_canonical",
                    "severity": "info",
                    "detail": f"Canonical points to: {canonical}",
                }
            )
    return issues


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def analyze_crawl_csv(
    overview_bytes: bytes,
    *,
    redirects_bytes: bytes | None = None,
) -> dict[str, Any]:
    """Parse uploaded Screaming Frog CSVs and return a crawl issue report."""
    overview_df = _load_df(overview_bytes, _OVERVIEW_COLS)
    if "status_code" in overview_df.columns:
        overview_df["status_code"] = pd.to_numeric(overview_df["status_code"], errors="coerce")

    redirects_df: pd.DataFrame | None = None
    if redirects_bytes:
        redirects_df = _load_df(redirects_bytes, _REDIRECTS_COLS)

    issues: list[dict] = []
    issues.extend(_detect_404s(overview_df))
    issues.extend(_detect_redirect_chains(redirects_df if redirects_df is not None else pd.DataFrame()))
    issues.extend(_detect_duplicate_titles(overview_df))
    issues.extend(_detect_duplicate_descriptions(overview_df))
    issues.extend(_detect_canonical_issues(overview_df))

    url_count = int(overview_df["url"].nunique()) if "url" in overview_df.columns else 0
    by_severity: dict[str, int] = {}
    for issue in issues:
        by_severity[issue["severity"]] = by_severity.get(issue["severity"], 0) + 1

    return {
        "url_count": url_count,
        "issue_count": len(issues),
        "by_severity": by_severity,
        "issues": issues,
        "analyzed_at": datetime.now(UTC).isoformat(),
    }


def store_crawl_report(shop: str, report: dict[str, Any]) -> tuple[Path, Path]:
    """Persist latest and timestamped crawl report for a shop."""
    shop_dir = _DATA_DIR / shop
    shop_dir.mkdir(parents=True, exist_ok=True)
    latest_path = shop_dir / "crawl_report.json"
    timestamped_path = shop_dir / f"crawl_report_{_timestamp()}.json"
    payload = json.dumps(report, ensure_ascii=False)
    latest_path.write_text(payload, encoding="utf-8")
    timestamped_path.write_text(payload, encoding="utf-8")
    return latest_path, timestamped_path


def latest_crawl_status(shop: str) -> dict[str, Any]:
    """Return the latest crawl status for a shop."""
    latest_path = _DATA_DIR / shop / "crawl_report.json"
    if not latest_path.exists():
        return {
            "available": False,
            "url_count": 0,
            "issue_count": 0,
            "by_severity": {},
            "issues": [],
            "imported_at": None,
        }
    report = json.loads(latest_path.read_text(encoding="utf-8"))
    return {
        "available": True,
        "url_count": report.get("url_count", 0),
        "issue_count": report.get("issue_count", 0),
        "by_severity": report.get("by_severity", {}),
        "issues": report.get("issues", []),
        "imported_at": datetime.fromtimestamp(
            latest_path.stat().st_mtime, UTC
        ).isoformat(),
    }
