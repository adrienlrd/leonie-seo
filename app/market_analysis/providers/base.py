"""Abstract base for keyword data providers."""

from __future__ import annotations

from typing import Protocol

from app.market_analysis.providers.types import KeywordSignal


class KeywordDataProvider(Protocol):
    """Protocol every keyword data source must implement.

    A provider must:
      - report its availability via `available` (cheap: env-var check, no network)
      - implement `enrich(signals)` to mutate the list in place (or return a new list)
      - never raise on a remote failure — log and return signals unchanged
    """

    name: str

    @property
    def available(self) -> bool:
        """True when the provider can serve requests (creds set + enabled)."""
        ...

    def enrich(self, signals: list[KeywordSignal], *, shop: str) -> list[KeywordSignal]:
        """Enrich the signals with this provider's data. Must not raise."""
        ...
