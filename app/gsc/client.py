"""Google Search Console OAuth and import helpers."""

from __future__ import annotations

import csv
import json
import logging
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import google.auth.exceptions
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build

from app.google_scopes import GOOGLE_OAUTH_SCOPES
from app.gsc.token_store import delete_google_token, get_google_token, save_google_token
from app.paths import data_dir
from app.tenant_config import find_tenant_by_shop_domain

logger = logging.getLogger(__name__)

# Union scopes (GSC + GA4) — the two share one token row per shop, so both flows
# must grant the same scopes to avoid one connection clobbering the other.
GSC_SCOPES = list(GOOGLE_OAUTH_SCOPES)
_DATA_DIR = data_dir()


class GSCConfigurationError(RuntimeError):
    """Raised when Google OAuth is not configured."""


class GSCConnectionError(RuntimeError):
    """Raised when a shop has not connected Google Search Console."""


def google_oauth_configured() -> bool:
    """Return whether Google OAuth can start from current environment."""
    return bool(os.getenv("GOOGLE_OAUTH_CLIENT_CONFIG")) or bool(os.getenv("GOOGLE_OAUTH_CLIENT_PATH"))


def _redirect_uri() -> str:
    if uri := os.getenv("GOOGLE_OAUTH_REDIRECT_URI"):
        return uri
    app_url = os.getenv("PYTHON_BACKEND_PUBLIC_URL") or os.getenv("APP_URL")
    if not app_url:
        raise GSCConfigurationError("GOOGLE_OAUTH_REDIRECT_URI or APP_URL is required")
    return f"{app_url.rstrip('/')}/api/google/gsc/callback"


def _flow() -> Flow:
    config_json = os.getenv("GOOGLE_OAUTH_CLIENT_CONFIG")
    if config_json:
        try:
            config = json.loads(config_json)
        except json.JSONDecodeError as exc:
            raise GSCConfigurationError("GOOGLE_OAUTH_CLIENT_CONFIG is not valid JSON") from exc
        flow = Flow.from_client_config(config, scopes=GSC_SCOPES, redirect_uri=_redirect_uri())
        return flow

    client_path = os.getenv("GOOGLE_OAUTH_CLIENT_PATH")
    if not client_path:
        raise GSCConfigurationError("GOOGLE_OAUTH_CLIENT_PATH is required")
    path = Path(client_path)
    if not path.exists():
        raise GSCConfigurationError(f"Google OAuth client file not found: {client_path}")
    return Flow.from_client_secrets_file(str(path), scopes=GSC_SCOPES, redirect_uri=_redirect_uri())


def build_authorization_url(state: str) -> tuple[str, str | None]:
    """Build a Google OAuth consent URL for Search Console.

    Returns (url, code_verifier). code_verifier is set when the library
    automatically enables PKCE (google_auth_oauthlib >= 1.x). The caller
    must persist it and pass it back to exchange_code_for_token.
    """
    flow = _flow()
    authorization_url, _ = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
        state=state,
    )
    # Capture PKCE verifier if the library generated one automatically.
    code_verifier: str | None = getattr(flow, "code_verifier", None) or getattr(
        getattr(flow, "oauth2session", None), "_code_verifier", None
    )
    return authorization_url, code_verifier


def exchange_code_for_token(code: str, code_verifier: str | None = None) -> Credentials:
    """Exchange an OAuth callback code for Google credentials."""
    flow = _flow()
    kwargs: dict[str, str] = {"code": code}
    if code_verifier:
        kwargs["code_verifier"] = code_verifier
    flow.fetch_token(**kwargs)
    return flow.credentials


def save_credentials(shop: str, credentials: Credentials) -> None:
    """Persist Google credentials for a shop."""
    save_google_token(shop, credentials.to_json(), ",".join(GSC_SCOPES))


def _credentials_for_shop(shop: str) -> Credentials:
    record = get_google_token(shop)
    if record is None:
        raise GSCConnectionError("Google Search Console is not connected for this shop")
    credentials = Credentials.from_authorized_user_info(json.loads(record["token_json"]), GSC_SCOPES)
    if credentials.expired and credentials.refresh_token:
        try:
            credentials.refresh(Request())
            save_credentials(shop, credentials)
        except google.auth.exceptions.RefreshError as exc:
            # Token revoked or permanently expired — clear it so the next call fails
            # immediately (not-connected) instead of looping through a doomed refresh.
            delete_google_token(shop)
            raise GSCConnectionError(
                "Google Search Console authorization has been revoked. "
                "Please reconnect GSC from the app settings."
            ) from exc
    if not credentials.valid:
        raise GSCConnectionError("Google Search Console credentials are invalid")
    return credentials


def build_gsc_service(shop: str) -> Any:
    """Return an authenticated Search Console API service for a shop."""
    return build(
        "searchconsole",
        "v1",
        credentials=_credentials_for_shop(shop),
        cache_discovery=False,  # avoid stale/conflicting disk cache
    )


def default_site_url(shop: str) -> str:
    """Return the configured GSC property for a shop."""
    if site_url := os.getenv("GSC_SITE_URL"):
        return site_url
    tenant = find_tenant_by_shop_domain(shop)
    if tenant and tenant.gsc_property:
        return tenant.gsc_property
    return f"https://{shop}"


_ROW_LIMIT = 25_000  # GSC API maximum per request


def _query_paginated(
    service: Any,
    site_url: str,
    *,
    days: int,
    dimensions: list[str],
    max_rows: int = 100_000,
) -> list[dict]:
    """Fetch all rows for the given dimensions, paginating as needed."""
    end_date = date.today()
    start_date = end_date - timedelta(days=days)
    base_body = {
        "startDate": start_date.isoformat(),
        "endDate": end_date.isoformat(),
        "dimensions": dimensions,
        "rowLimit": _ROW_LIMIT,
    }
    all_rows: list[dict] = []
    start_row = 0
    while len(all_rows) < max_rows:
        body = {**base_body, "startRow": start_row}
        try:
            response = service.searchanalytics().query(siteUrl=site_url, body=body).execute()
        except Exception as exc:
            logger.error("GSC query failed (dims=%s, startRow=%d): %s", dimensions, start_row, exc)
            raise
        rows = list(response.get("rows", []))
        all_rows.extend(rows)
        if len(rows) < _ROW_LIMIT:
            break
        start_row += len(rows)
    return all_rows


def _normalise_page_rows(rows: list[dict]) -> list[dict]:
    return [
        {
            "url": row.get("keys", [""])[0],
            "clicks": row.get("clicks", 0),
            "impressions": row.get("impressions", 0),
            "ctr": row.get("ctr", 0),
            "position": row.get("position", 0),
        }
        for row in rows
    ]


def _normalise_query_page_rows(rows: list[dict]) -> list[dict]:
    normalised = []
    for row in rows:
        keys = row.get("keys", [])
        normalised.append(
            {
                "query": keys[0] if len(keys) > 0 else "",
                "url": keys[1] if len(keys) > 1 else "",
                "clicks": row.get("clicks", 0),
                "impressions": row.get("impressions", 0),
                "ctr": row.get("ctr", 0),
                "position": row.get("position", 0),
            }
        )
    return normalised


def _write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def latest_import_status(shop: str) -> dict:
    """Return freshness metadata for the latest stored GSC import."""
    shop_dir = _DATA_DIR / shop
    candidates = sorted(shop_dir.glob("gsc_*.json"), reverse=True) if shop_dir.exists() else []
    if not candidates:
        return {"available": False, "row_count": 0, "imported_at": None}
    path = candidates[0]
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"available": False, "row_count": 0, "imported_at": None}
    rows = data if isinstance(data, list) else data.get("rows", [])
    imported_at = None if isinstance(data, list) else data.get("imported_at")
    return {
        "available": True,
        "row_count": len(rows),
        "imported_at": imported_at,
        "path": str(path),
    }


def _cleanup_old_gsc_json(shop_dir: Path, keep: int = 5) -> None:
    """Remove oldest gsc_*.json files, keeping the most recent `keep`."""
    files = sorted(shop_dir.glob("gsc_*.json"), reverse=True)
    for old in files[keep:]:
        try:
            old.unlink()
        except OSError:
            pass


def fetch_and_store_gsc_performance(
    shop: str,
    *,
    days: int = 28,
    site_url: str | None = None,
    service: Any | None = None,
    pages_only: bool = False,
) -> dict:
    """Fetch GSC page (and optionally query-page) data, then store shop-scoped exports.

    Args:
        days: Lookback window. 28 days is enough for indexing checks and most analyses.
        pages_only: When True, skip the expensive query×page call. Use this for
            lightweight catalog-refresh scenarios (badge display only).
    """
    target = site_url or default_site_url(shop)
    gsc_service = service or build_gsc_service(shop)

    if pages_only:
        # Single call — fast path for dashboard badge refresh.
        page_rows = _normalise_page_rows(
            _query_paginated(gsc_service, target, days=days, dimensions=["page"])
        )
        query_page_rows: list[dict] = []
    else:
        # Parallel fetch — both queries at once.
        with ThreadPoolExecutor(max_workers=2) as pool:
            page_future = pool.submit(
                _query_paginated, gsc_service, target, days=days, dimensions=["page"]
            )
            qp_future = pool.submit(
                _query_paginated, gsc_service, target, days=days, dimensions=["query", "page"]
            )
            futures = {page_future: "page", qp_future: "query_page"}
            results: dict[str, list[dict]] = {}
            for fut in as_completed(futures):
                results[futures[fut]] = fut.result()
        page_rows = _normalise_page_rows(results["page"])
        query_page_rows = _normalise_query_page_rows(results["query_page"])

    shop_dir = _DATA_DIR / shop
    shop_dir.mkdir(parents=True, exist_ok=True)
    imported_at = datetime.now(UTC).isoformat()

    _write_csv(
        shop_dir / "gsc_performance.csv",
        page_rows,
        ["url", "clicks", "impressions", "ctr", "position"],
    )

    json_path_str = ""
    if not pages_only:
        _write_csv(
            shop_dir / "gsc_query_page.csv",
            query_page_rows,
            ["query", "url", "clicks", "impressions", "ctr", "position"],
        )
        stamp = imported_at.replace(":", "").replace("-", "").split(".")[0]
        json_path = shop_dir / f"gsc_{stamp}.json"
        json_path.write_text(
            json.dumps(
                {
                    "shop": shop,
                    "site_url": target,
                    "days": days,
                    "imported_at": imported_at,
                    "rows": query_page_rows,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        json_path_str = str(json_path)
        _cleanup_old_gsc_json(shop_dir)

    return {
        "shop": shop,
        "site_url": target,
        "days": days,
        "pages_only": pages_only,
        "page_rows": len(page_rows),
        "query_page_rows": len(query_page_rows),
        "imported_at": imported_at,
        "json_path": json_path_str,
    }
