"""Google Ads Keyword Planner provider — stub (env-gated, no-op when missing).

The real implementation requires a Google Ads developer token, an OAuth2
refresh token and a customer ID. We expose the env wiring so activation is
just a matter of setting them and shipping the real client.

Activation (future):
    GOOGLE_ADS_DEVELOPER_TOKEN=
    GOOGLE_ADS_CLIENT_ID=
    GOOGLE_ADS_CLIENT_SECRET=
    GOOGLE_ADS_REFRESH_TOKEN=
    GOOGLE_ADS_CUSTOMER_ID=
    GOOGLE_ADS_ENABLED=true

When any of these is missing or `GOOGLE_ADS_ENABLED!=true`, `available`
returns False and the engine silently skips this provider.

TODO paid-provider:
    - install google-ads SDK (only when activated)
    - call KeywordPlanIdeaService.GenerateKeywordHistoricalMetrics
    - normalise the response into KeywordSignal updates
"""

from __future__ import annotations

import logging
import os

from app.market_analysis.providers.types import KeywordSignal

logger = logging.getLogger(__name__)


_REQUIRED_ENV = (
    "GOOGLE_ADS_DEVELOPER_TOKEN",
    "GOOGLE_ADS_CLIENT_ID",
    "GOOGLE_ADS_CLIENT_SECRET",
    "GOOGLE_ADS_REFRESH_TOKEN",
    "GOOGLE_ADS_CUSTOMER_ID",
)


class GoogleAdsKeywordProvider:
    """Stub Google Ads provider — exposes the env contract, never blocks."""

    name = "google_ads"

    def __init__(self) -> None:
        self._enabled = os.getenv("GOOGLE_ADS_ENABLED", "false").strip().lower() == "true"
        self._missing_env = [k for k in _REQUIRED_ENV if not os.getenv(k)]

    @property
    def available(self) -> bool:
        return self._enabled and not self._missing_env

    def enrich(self, signals: list[KeywordSignal], *, shop: str) -> list[KeywordSignal]:  # noqa: ARG002
        if not self.available:
            return signals
        # Real implementation deferred — log once and return signals untouched.
        logger.info(
            "GoogleAdsKeywordProvider enabled but not implemented yet — "
            "signals returned unchanged"
        )
        return signals
