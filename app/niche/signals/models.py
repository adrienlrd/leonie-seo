"""Signal keyword data model."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SignalKeyword:
    """A keyword candidate from an external signal source.

    Attributes:
        keyword: The keyword string (lowercased, stripped).
        source: Origin — "google_suggest" | "trends_top" | "trends_rising" | "reddit".
        volume_estimate: Relative volume (0-100 from Trends, None otherwise).
        context: Free-form context (e.g. subreddit, autocomplete position, timeframe).
        relevance_score: Normalized 0.0-1.0 relevance to the seed keyword.
    """

    keyword: str
    source: str
    volume_estimate: int | None
    context: str
    relevance_score: float

    def __post_init__(self) -> None:
        self.keyword = self.keyword.strip().lower()
        self.relevance_score = round(max(0.0, min(1.0, self.relevance_score)), 3)
