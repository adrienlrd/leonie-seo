"""Google Search Console OAuth and import helpers."""

from __future__ import annotations

import csv
import json
import os
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build

from app.gsc.token_store import get_google_token, save_google_token
from app.tenant_config import find_tenant_by_shop_domain

GSC_SCOPES = ["https://www.googleapis.com/auth/webmasters.readonly"]
_DATA_DIR = Path(__file__).parents[2] / "data" / "raw"


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


def build_authorization_url(state: str) -> str:
    """Build a Google OAuth consent URL for Search Console."""
    flow = _flow()
    authorization_url, _ = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
        state=state,
    )
    return authorization_url


def exchange_code_for_token(code: str) -> Credentials:
    """Exchange an OAuth callback code for Google credentials."""
    flow = _flow()
    flow.fetch_token(code=code)
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
        credentials.refresh(Request())
        save_credentials(shop, credentials)
    if not credentials.valid:
        raise GSCConnectionError("Google Search Console credentials are invalid")
    return credentials


def build_gsc_service(shop: str) -> Any:
    """Return an authenticated Search Console API service for a shop."""
    return build("searchconsole", "v1", credentials=_credentials_for_shop(shop))


def default_site_url(shop: str) -> str:
    """Return the configured GSC property for a shop."""
    if site_url := os.getenv("GSC_SITE_URL"):
        return site_url
    tenant = find_tenant_by_shop_domain(shop)
    if tenant and tenant.gsc_property:
        return tenant.gsc_property
    return f"https://{shop}"


def _query(service: Any, site_url: str, *, days: int, dimensions: list[str]) -> list[dict]:
    end_date = date.today()
    start_date = end_date - timedelta(days=days)
    body = {
        "startDate": start_date.isoformat(),
        "endDate": end_date.isoformat(),
        "dimensions": dimensions,
        "rowLimit": 25000,
    }
    response = service.searchanalytics().query(siteUrl=site_url, body=body).execute()
    return list(response.get("rows", []))


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


def fetch_and_store_gsc_performance(
    shop: str,
    *,
    days: int = 90,
    site_url: str | None = None,
    service: Any | None = None,
) -> dict:
    """Fetch GSC page and query-page data, then store shop-scoped exports."""
    target = site_url or default_site_url(shop)
    gsc_service = service or build_gsc_service(shop)

    page_rows = _normalise_page_rows(_query(gsc_service, target, days=days, dimensions=["page"]))
    query_page_rows = _normalise_query_page_rows(
        _query(gsc_service, target, days=days, dimensions=["query", "page"])
    )

    shop_dir = _DATA_DIR / shop
    imported_at = datetime.now(UTC).isoformat()
    stamp = imported_at.replace(":", "").replace("-", "").split(".")[0]

    _write_csv(shop_dir / "gsc_performance.csv", page_rows, ["url", "clicks", "impressions", "ctr", "position"])
    _write_csv(
        shop_dir / "gsc_query_page.csv",
        query_page_rows,
        ["query", "url", "clicks", "impressions", "ctr", "position"],
    )
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

    return {
        "shop": shop,
        "site_url": target,
        "days": days,
        "page_rows": len(page_rows),
        "query_page_rows": len(query_page_rows),
        "imported_at": imported_at,
        "json_path": str(json_path),
    }
