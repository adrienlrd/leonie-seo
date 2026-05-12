"""GA4 Data API v1beta client — auth via service account, transport via httpx.

Sync and async report methods are both provided. FastAPI handlers should
prefer ``run_report_async`` (or wrap ``run_report`` in ``asyncio.to_thread``)
to avoid blocking the event loop on the ~200-500 ms GA4 round-trip.
"""

from __future__ import annotations

import os
from typing import Any

import httpx

_GA4_BASE = "https://analyticsdata.googleapis.com/v1beta/properties"
_SCOPES = ["https://www.googleapis.com/auth/analytics.readonly"]


class GA4Error(Exception):
    """Raised on GA4 API or auth errors."""


def _load_credentials(credentials_file: str | None = None):
    """Load service-account credentials from disk without forcing a refresh.

    Returns a ``google.oauth2.service_account.Credentials`` object whose
    ``token`` will be populated by the caller via ``refresh()``.
    """
    try:
        from google.oauth2 import service_account  # noqa: PLC0415
    except ImportError as exc:
        raise GA4Error(
            "google-auth is required. Install it with: pip install google-auth"
        ) from exc

    path = credentials_file or os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    if not path:
        raise GA4Error(
            "Service account credentials not found. "
            "Set GOOGLE_APPLICATION_CREDENTIALS to the path of your JSON key file."
        )

    return service_account.Credentials.from_service_account_file(path, scopes=_SCOPES)


def _get_token(credentials_file: str | None = None) -> str:
    """Obtain a short-lived access token from a service account credentials file.

    Note: callers issuing many requests should prefer ``GA4Client`` which
    caches and refreshes credentials lazily, instead of re-auth'ing each call.

    Args:
        credentials_file: Path to service account JSON. Defaults to
                          GOOGLE_APPLICATION_CREDENTIALS env var.

    Returns:
        OAuth2 Bearer token string.

    Raises:
        GA4Error: If credentials are missing or auth fails.
    """
    try:
        from google.auth.transport.requests import Request  # noqa: PLC0415
    except ImportError as exc:
        raise GA4Error(
            "google-auth is required. Install it with: pip install google-auth"
        ) from exc

    creds = _load_credentials(credentials_file)
    try:
        creds.refresh(Request())
    except Exception as exc:
        raise GA4Error(f"GA4 authentication failed: {exc}") from exc

    return creds.token  # type: ignore[return-value]


class GA4Client:
    """Thin GA4 Data API v1beta client with credential caching.

    The service-account credentials object is loaded once and reused; tokens
    are refreshed only when expired. This avoids the ~200 ms penalty of a
    fresh service-account exchange on every ``run_report`` call.

    Args:
        property_id: GA4 property ID (numeric, e.g. "123456789").
        credentials_file: Path to service account JSON key (optional, falls back to env var).
        token: Pre-obtained Bearer token (tests only — skips service-account auth).
    """

    def __init__(
        self,
        property_id: str,
        *,
        credentials_file: str | None = None,
        token: str | None = None,
    ) -> None:
        self._property_id = property_id
        self._credentials_file = credentials_file
        self._token = token  # pre-injected for tests
        self._creds = None  # google.oauth2.service_account.Credentials — lazy

    def _bearer(self) -> str:
        """Return a valid Bearer token, refreshing credentials only if expired."""
        if self._token:
            return self._token
        if self._creds is None:
            self._creds = _load_credentials(self._credentials_file)
        if self._creds.expired or not self._creds.token:
            try:
                from google.auth.transport.requests import Request  # noqa: PLC0415
            except ImportError as exc:
                raise GA4Error("google-auth is required.") from exc
            try:
                self._creds.refresh(Request())
            except Exception as exc:
                raise GA4Error(f"GA4 authentication failed: {exc}") from exc
        return self._creds.token  # type: ignore[return-value]

    def _auth_headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._bearer()}", "Content-Type": "application/json"}

    def run_report(self, body: dict[str, Any]) -> dict[str, Any]:
        """POST a report request to the GA4 Data API (synchronous).

        Args:
            body: GA4 RunReportRequest dict (dimensions, metrics, dateRanges, etc.)

        Returns:
            Parsed GA4 RunReportResponse dict.

        Raises:
            GA4Error: On HTTP or API errors.
        """
        url = f"{_GA4_BASE}/{self._property_id}:runReport"
        try:
            resp = httpx.post(url, json=body, headers=self._auth_headers(), timeout=30.0)
        except httpx.RequestError as exc:
            raise GA4Error(f"GA4 request failed: {exc}") from exc

        if resp.status_code != 200:
            raise GA4Error(
                f"GA4 API error {resp.status_code}: {resp.text[:300]}"
            )

        return resp.json()

    async def run_report_async(self, body: dict[str, Any]) -> dict[str, Any]:
        """Async version of ``run_report`` — preferred from FastAPI handlers.

        Uses ``httpx.AsyncClient`` so the event loop stays free during the
        GA4 round-trip. Auth headers are computed synchronously (token cache
        is in-process and cheap).
        """
        url = f"{_GA4_BASE}/{self._property_id}:runReport"
        headers = self._auth_headers()
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(url, json=body, headers=headers)
        except httpx.RequestError as exc:
            raise GA4Error(f"GA4 request failed: {exc}") from exc

        if resp.status_code != 200:
            raise GA4Error(f"GA4 API error {resp.status_code}: {resp.text[:300]}")

        return resp.json()


def parse_report(response: dict[str, Any]) -> list[dict[str, Any]]:
    """Parse a GA4 RunReportResponse into a flat list of row dicts.

    Args:
        response: Raw GA4 API response dict.

    Returns:
        List of dicts with dimension and metric values as str keys → typed values.
    """
    dim_headers = [h["name"] for h in response.get("dimensionHeaders", [])]
    met_headers = [h["name"] for h in response.get("metricHeaders", [])]
    rows = []
    for row in response.get("rows", []):
        record: dict[str, Any] = {}
        for i, dv in enumerate(row.get("dimensionValues", [])):
            if i < len(dim_headers):
                record[dim_headers[i]] = dv.get("value", "")
        for i, mv in enumerate(row.get("metricValues", [])):
            if i < len(met_headers):
                name = met_headers[i]
                raw = mv.get("value", "0")
                # Coerce to float for metrics; caller decides int vs float
                try:
                    record[name] = float(raw)
                except ValueError:
                    record[name] = 0.0
        rows.append(record)
    return rows
