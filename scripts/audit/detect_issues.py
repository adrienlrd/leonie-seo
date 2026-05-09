"""Detect SEO issues from Shopify catalog and Screaming Frog data."""

from typing import Any

import pandas as pd
import yaml

from scripts._paths import SEO_RULES_PATH
from scripts.models import Issue, Severity

_RULES_PATH = SEO_RULES_PATH


def _load_rules(rules_path: str = _RULES_PATH) -> dict[str, Any]:
    with open(rules_path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def detect_meta_title_issues(
    resources: list[dict[str, Any]],
    resource_type: str = "product",
    rules_path: str = _RULES_PATH,
) -> list[Issue]:
    """Detect missing, too-short, too-long, and duplicate meta titles."""
    rules = _load_rules(rules_path)["meta_title"]
    issues: list[Issue] = []
    seen: dict[str, str] = {}  # normalized title → first resource name

    for r in resources:
        rid = r["id"]
        name = r.get("title", rid)
        title = (r.get("seo") or {}).get("title") or ""
        length = len(title.strip())

        if not title.strip():
            issues.append(
                Issue(
                    resource_type=resource_type,
                    resource_id=rid,
                    resource_title=name,
                    issue_type="missing_meta_title",
                    severity=Severity.CRITICAL,
                    current_value=None,
                    detail="Meta title is missing.",
                )
            )
            continue

        if length < rules["too_short"]:
            issues.append(
                Issue(
                    resource_type=resource_type,
                    resource_id=rid,
                    resource_title=name,
                    issue_type="too_short_meta_title",
                    severity=Severity.HIGH,
                    current_value=title,
                    detail=f"Meta title too short: {length} chars (min {rules['too_short']}).",
                )
            )
        elif length > rules["too_long"]:
            issues.append(
                Issue(
                    resource_type=resource_type,
                    resource_id=rid,
                    resource_title=name,
                    issue_type="too_long_meta_title",
                    severity=Severity.MEDIUM,
                    current_value=title,
                    detail=f"Meta title too long: {length} chars (max {rules['too_long']}).",
                )
            )

        normalized = title.strip().lower()
        if normalized in seen:
            issues.append(
                Issue(
                    resource_type=resource_type,
                    resource_id=rid,
                    resource_title=name,
                    issue_type="duplicate_meta_title",
                    severity=Severity.HIGH,
                    current_value=title,
                    detail=f"Duplicate meta title — same as: {seen[normalized]}",
                )
            )
        else:
            seen[normalized] = name

    return issues


def detect_meta_description_issues(
    resources: list[dict[str, Any]],
    resource_type: str = "product",
    rules_path: str = _RULES_PATH,
) -> list[Issue]:
    """Detect missing, too-short, too-long, and duplicate meta descriptions."""
    rules = _load_rules(rules_path)["meta_description"]
    issues: list[Issue] = []
    seen: dict[str, str] = {}

    for r in resources:
        rid = r["id"]
        name = r.get("title", rid)
        desc = (r.get("seo") or {}).get("description") or ""
        length = len(desc.strip())

        if not desc.strip():
            issues.append(
                Issue(
                    resource_type=resource_type,
                    resource_id=rid,
                    resource_title=name,
                    issue_type="missing_meta_description",
                    severity=Severity.HIGH,
                    current_value=None,
                    detail="Meta description is missing.",
                )
            )
            continue

        if length < rules["too_short"]:
            issues.append(
                Issue(
                    resource_type=resource_type,
                    resource_id=rid,
                    resource_title=name,
                    issue_type="too_short_meta_description",
                    severity=Severity.MEDIUM,
                    current_value=desc,
                    detail=f"Meta description too short: {length} chars (min {rules['too_short']}).",
                )
            )
        elif length > rules["too_long"]:
            issues.append(
                Issue(
                    resource_type=resource_type,
                    resource_id=rid,
                    resource_title=name,
                    issue_type="too_long_meta_description",
                    severity=Severity.LOW,
                    current_value=desc,
                    detail=f"Meta description too long: {length} chars (max {rules['too_long']}).",
                )
            )

        normalized = desc.strip().lower()
        if normalized in seen:
            issues.append(
                Issue(
                    resource_type=resource_type,
                    resource_id=rid,
                    resource_title=name,
                    issue_type="duplicate_meta_description",
                    severity=Severity.HIGH,
                    current_value=desc,
                    detail=f"Duplicate meta description — same as: {seen[normalized]}",
                )
            )
        else:
            seen[normalized] = name

    return issues


def detect_alt_text_issues(
    products: list[dict[str, Any]],
    rules_path: str = _RULES_PATH,
) -> list[Issue]:
    """Detect missing or too-long alt text on product images."""
    rules = _load_rules(rules_path)["alt_text"]
    issues: list[Issue] = []

    for product in products:
        pid = product["id"]
        name = product.get("title", pid)
        images = (product.get("images") or {}).get("edges", [])

        for img_edge in images:
            img = img_edge["node"]
            alt = img.get("altText")
            img_id = img.get("id") or img.get("url") or "unknown"

            if alt is None or alt.strip() == "":
                issues.append(
                    Issue(
                        resource_type="image",
                        resource_id=img_id,
                        resource_title=f"{name} — image",
                        issue_type="missing_alt_text",
                        severity=Severity.HIGH,
                        current_value=None,
                        detail=f"Image on '{name}' has no alt text.",
                    )
                )
            elif len(alt) > rules["max_length"]:
                issues.append(
                    Issue(
                        resource_type="image",
                        resource_id=img_id,
                        resource_title=f"{name} — image",
                        issue_type="too_long_alt_text",
                        severity=Severity.LOW,
                        current_value=alt,
                        detail=f"Alt text too long: {len(alt)} chars (max {rules['max_length']}).",
                    )
                )

    return issues


def detect_duplicate_content(products: list[dict[str, Any]]) -> list[Issue]:
    """Flag Shopify's auto-generated /collections/*/products/* duplicate URLs.

    Shopify themes handle this with <link rel="canonical"> automatically.
    Flagged as INFO so the operator can verify the canonical is in place.
    """
    issues: list[Issue] = []
    for product in products:
        pid = product["id"]
        name = product.get("title", pid)
        handle = product.get("handle", "")
        if handle:
            issues.append(
                Issue(
                    resource_type="product",
                    resource_id=pid,
                    resource_title=name,
                    issue_type="shopify_duplicate_url",
                    severity=Severity.INFO,
                    current_value=f"/products/{handle}",
                    detail=(
                        f"Shopify generates /collections/*/products/{handle} alongside "
                        f"/products/{handle}. Verify <link rel='canonical'> is present."
                    ),
                )
            )
    return issues


def detect_redirect_issues(sf_redirects_df: pd.DataFrame | None) -> list[Issue]:
    """Detect redirect chains and 302 temporary redirects from Screaming Frog data."""
    if sf_redirects_df is None or sf_redirects_df.empty:
        return []

    issues: list[Issue] = []

    if "chain_length" in sf_redirects_df.columns:
        chains = sf_redirects_df[
            pd.to_numeric(sf_redirects_df["chain_length"], errors="coerce") > 1
        ]
        for _, row in chains.iterrows():
            from_url = str(row.get("from_url", ""))
            issues.append(
                Issue(
                    resource_type="redirect",
                    resource_id=from_url,
                    resource_title=from_url,
                    issue_type="redirect_chain",
                    severity=Severity.HIGH,
                    current_value=str(row.get("to_url", "")),
                    detail=f"Redirect chain (length {row.get('chain_length', '?')}) — consolidate to a single 301.",
                )
            )

    if "status_code" in sf_redirects_df.columns:
        temp = sf_redirects_df[
            pd.to_numeric(sf_redirects_df["status_code"], errors="coerce") == 302
        ]
        for _, row in temp.iterrows():
            from_url = str(row.get("from_url", ""))
            issues.append(
                Issue(
                    resource_type="redirect",
                    resource_id=from_url,
                    resource_title=from_url,
                    issue_type="temporary_redirect_302",
                    severity=Severity.MEDIUM,
                    current_value=str(row.get("to_url", "")),
                    detail="302 temporary redirect loses PageRank — use 301.",
                )
            )

    return issues


def detect_404_issues(sf_overview_df: pd.DataFrame | None) -> list[Issue]:
    """Detect pages returning 404 from Screaming Frog overview data."""
    if sf_overview_df is None or sf_overview_df.empty:
        return []

    issues: list[Issue] = []

    if "status_code" in sf_overview_df.columns:
        not_found = sf_overview_df[
            pd.to_numeric(sf_overview_df["status_code"], errors="coerce") == 404
        ]
        for _, row in not_found.iterrows():
            url = str(row.get("url", ""))
            issues.append(
                Issue(
                    resource_type="page",
                    resource_id=url,
                    resource_title=url,
                    issue_type="page_404",
                    severity=Severity.CRITICAL,
                    current_value=url,
                    detail="Page returns 404 — remove internal links or add a 301 redirect.",
                )
            )

    return issues
