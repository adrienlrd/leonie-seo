"""GA4 OAuth2 helpers — user-credential flow (not service account).

Shares the same Google OAuth client config as GSC (GOOGLE_OAUTH_CLIENT_CONFIG
or GOOGLE_OAUTH_CLIENT_PATH). Stores tokens in the shared ``google_tokens``
table with ``include_granted_scopes=true`` so connecting GA4 preserves any
existing GSC scope granted by the user.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import httpx
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow

from app.gsc.token_store import delete_google_token, get_google_token, save_google_token

# include_granted_scopes=true causes Google to return additional scopes already
# granted (e.g. webmasters.readonly from GSC). requests-oauthlib raises a Warning
# when returned scopes differ from requested ones — OAUTHLIB_RELAX_TOKEN_SCOPE
# suppresses that error.
os.environ.setdefault("OAUTHLIB_RELAX_TOKEN_SCOPE", "1")

GA4_SCOPES = ["https://www.googleapis.com/auth/analytics.readonly"]

_GA4_ADMIN_BASE = "https://analyticsadmin.googleapis.com/v1beta"


class GA4OAuthError(RuntimeError):
    """Raised when GA4 OAuth is not configured or credentials are invalid."""


def ga4_oauth_configured() -> bool:
    """Return True when the Google OAuth client is present in the environment."""
    return bool(os.getenv("GOOGLE_OAUTH_CLIENT_CONFIG")) or bool(
        os.getenv("GOOGLE_OAUTH_CLIENT_PATH")
    )


def _redirect_uri() -> str:
    if uri := os.getenv("GOOGLE_GA4_REDIRECT_URI"):
        return uri
    app_url = os.getenv("PYTHON_BACKEND_PUBLIC_URL") or os.getenv("APP_URL")
    if not app_url:
        raise GA4OAuthError("APP_URL is required for GA4 OAuth redirect")
    return f"{app_url.rstrip('/')}/api/google/ga4/callback"


def _flow() -> Flow:
    config_json = os.getenv("GOOGLE_OAUTH_CLIENT_CONFIG")
    if config_json:
        try:
            config = json.loads(config_json)
        except json.JSONDecodeError as exc:
            raise GA4OAuthError("GOOGLE_OAUTH_CLIENT_CONFIG is not valid JSON") from exc
        return Flow.from_client_config(config, scopes=GA4_SCOPES, redirect_uri=_redirect_uri())

    client_path = os.getenv("GOOGLE_OAUTH_CLIENT_PATH")
    if not client_path:
        raise GA4OAuthError("GOOGLE_OAUTH_CLIENT_PATH or GOOGLE_OAUTH_CLIENT_CONFIG is required")
    path = Path(client_path)
    if not path.exists():
        raise GA4OAuthError(f"Google OAuth client file not found: {client_path}")
    return Flow.from_client_secrets_file(str(path), scopes=GA4_SCOPES, redirect_uri=_redirect_uri())


def build_authorization_url(state: str) -> tuple[str, str | None]:
    """Return (authorization_url, code_verifier) for the GA4 consent screen.

    Uses ``include_granted_scopes=true`` so any existing GSC grant is preserved
    in the resulting token.
    """
    flow = _flow()
    url, _ = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
        state=state,
    )
    code_verifier: str | None = getattr(flow, "code_verifier", None) or getattr(
        getattr(flow, "oauth2session", None), "_code_verifier", None
    )
    return url, code_verifier


def exchange_code(code: str, code_verifier: str | None = None) -> Credentials:
    """Exchange an OAuth callback code for GA4 credentials."""
    flow = _flow()
    kwargs: dict[str, str] = {"code": code}
    if code_verifier:
        kwargs["code_verifier"] = code_verifier
    flow.fetch_token(**kwargs)
    return flow.credentials


def save_credentials(shop: str, credentials: Credentials, *, email: str | None = None) -> None:
    """Persist GA4 OAuth credentials for a shop (encrypted)."""
    save_google_token(shop, credentials.to_json(), ",".join(GA4_SCOPES), email=email)


def get_credentials(shop: str) -> Credentials | None:
    """Return valid GA4 credentials for a shop, refreshing if expired."""
    record = get_google_token(shop)
    if record is None:
        return None
    creds = Credentials.from_authorized_user_info(json.loads(record["token_json"]), GA4_SCOPES)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        save_credentials(shop, creds, email=record.get("email"))
    return creds if creds.valid else None


def get_bearer(shop: str) -> str:
    """Return a valid OAuth2 access token for GA4 API calls."""
    creds = get_credentials(shop)
    if creds is None:
        raise GA4OAuthError("GA4 is not connected for this shop")
    return creds.token  # type: ignore[return-value]


def list_properties(shop: str) -> list[dict[str, str]]:
    """Return accessible GA4 properties for the connected Google account.

    Calls the Analytics Admin API ``accountSummaries`` endpoint.

    Args:
        shop: Shopify shop domain.

    Returns:
        List of dicts with ``property_id``, ``property_name``, ``account_name``.

    Raises:
        GA4OAuthError: If not connected or API call fails.
    """
    token = get_bearer(shop)
    resp = httpx.get(
        f"{_GA4_ADMIN_BASE}/accountSummaries",
        headers={"Authorization": f"Bearer {token}"},
        timeout=15.0,
    )
    if resp.status_code == 403:
        detail = resp.text[:400]
        raise GA4OAuthError(
            f"GA4 Admin API 403 — either the API is not enabled in Google Cloud Console "
            f"(APIs & Services → Library → 'Google Analytics Admin API') or the account "
            f"lacks Viewer role on the GA4 property. Raw: {detail}"
        )
    if resp.status_code != 200:
        raise GA4OAuthError(f"GA4 Admin API error {resp.status_code}: {resp.text[:400]}")
    props: list[dict[str, str]] = []
    for account in resp.json().get("accountSummaries", []):
        for prop in account.get("propertySummaries", []):
            props.append(
                {
                    "property_id": prop["property"].split("/")[-1],
                    "property_name": prop.get("displayName", ""),
                    "account_name": account.get("displayName", ""),
                }
            )
    return props


def disconnect(shop: str) -> None:
    """Remove stored GA4 credentials for a shop."""
    delete_google_token(shop)
