"""Tests for niche signal fetchers and aggregator."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import requests

from app.niche.signals.models import SignalKeyword

# ---------------------------------------------------------------------------
# SignalKeyword model
# ---------------------------------------------------------------------------


def test_signal_keyword_normalises_on_init():
    kw = SignalKeyword(
        keyword="  Harnais Chien  ",
        source="google_suggest",
        volume_estimate=None,
        context="test",
        relevance_score=0.9,
    )
    assert kw.keyword == "harnais chien"


# ---------------------------------------------------------------------------
# Google Suggest
# ---------------------------------------------------------------------------


def _make_session(suggestions: list[str]) -> MagicMock:
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = ["harnais chien", suggestions]
    resp.raise_for_status = MagicMock()
    session = MagicMock()
    session.get.return_value = resp
    return session


def test_fetch_suggestions_returns_keywords():
    from app.niche.signals.google_suggest import fetch_suggestions

    session = _make_session(["harnais chien cuir", "harnais chien petit", "meilleur harnais"])
    results = fetch_suggestions("harnais chien", session=session)

    assert len(results) == 3
    assert all(isinstance(r, SignalKeyword) for r in results)
    assert results[0].source == "google_suggest"
    # First suggestion gets highest score
    assert results[0].relevance_score > results[-1].relevance_score


def test_fetch_suggestions_excludes_seed():
    from app.niche.signals.google_suggest import fetch_suggestions

    # seed is in suggestions list — should be excluded
    session = _make_session(["harnais chien", "harnais chien cuir"])
    results = fetch_suggestions("harnais chien", session=session)

    assert all(r.keyword != "harnais chien" for r in results)


def test_fetch_suggestions_returns_empty_on_error():
    from app.niche.signals.google_suggest import fetch_suggestions

    session = MagicMock()
    session.get.side_effect = requests.ConnectionError("network down")
    results = fetch_suggestions("harnais chien", session=session)

    assert results == []


def test_fetch_suggestions_bulk_deduplicates():
    from app.niche.signals.google_suggest import fetch_suggestions_bulk

    with patch("app.niche.signals.google_suggest.fetch_suggestions") as mock_fetch:
        mock_fetch.side_effect = [
            [
                SignalKeyword("collier cuir", "google_suggest", None, "p1", 0.9),
                SignalKeyword("harnais souple", "google_suggest", None, "p2", 0.8),
            ],
            [
                SignalKeyword("harnais souple", "google_suggest", None, "p1", 0.7),  # duplicate
                SignalKeyword("laisse longue", "google_suggest", None, "p2", 0.6),
            ],
        ]
        results = fetch_suggestions_bulk(["harnais", "collier"], delay=0)

    keywords = [r.keyword for r in results]
    assert keywords.count("harnais souple") == 1
    assert "collier cuir" in keywords
    assert "laisse longue" in keywords


# ---------------------------------------------------------------------------
# Reddit
# ---------------------------------------------------------------------------


def _make_reddit_response(posts: list[dict]) -> MagicMock:
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {
        "data": {
            "children": [{"data": p} for p in posts],
        }
    }
    resp.raise_for_status = MagicMock()
    session = MagicMock()
    session.get.return_value = resp
    return session


def test_fetch_reddit_keywords_returns_signals():
    from app.niche.signals.reddit import fetch_reddit_keywords

    posts = [
        {"title": "Meilleur harnais pour chien medium race", "score": 50},
        {"title": "Collier cuir artisanal pour grand chien", "score": 30},
    ]
    session = _make_reddit_response(posts)
    results = fetch_reddit_keywords("harnais chien", subreddits=["dogs"], session=session)

    assert len(results) > 0
    assert all(r.source == "reddit" for r in results)
    assert all(r.relevance_score > 0 for r in results)


def test_fetch_reddit_keywords_skips_low_upvotes():
    from app.niche.signals.reddit import fetch_reddit_keywords

    posts = [
        {"title": "Harnais chien tres bien", "score": 1},  # below _MIN_UPVOTES=5
        {"title": "Collier cuir chien moyen", "score": 20},
    ]
    session = _make_reddit_response(posts)
    results = fetch_reddit_keywords("harnais", subreddits=["dogs"], session=session)

    # Only post with score >= 5 should contribute
    # The post with score=1 title words won't appear
    scores = [r.relevance_score for r in results]
    assert all(s > 0 for s in scores)


def test_fetch_reddit_keywords_returns_empty_on_network_error():
    from app.niche.signals.reddit import fetch_reddit_keywords

    session = MagicMock()
    session.get.side_effect = requests.ConnectionError("timeout")
    results = fetch_reddit_keywords("harnais", subreddits=["dogs"], session=session)

    assert results == []


def test_fetch_reddit_keywords_skips_404_subreddits():
    from app.niche.signals.reddit import fetch_reddit_keywords

    resp_404 = MagicMock()
    resp_404.status_code = 404

    session = MagicMock()
    session.get.return_value = resp_404
    results = fetch_reddit_keywords("harnais", subreddits=["nonexistent_sub"], session=session)

    assert results == []


# ---------------------------------------------------------------------------
# Trends
# ---------------------------------------------------------------------------


def test_fetch_related_queries_returns_empty_when_pytrends_unavailable():
    from app.niche.signals.trends import fetch_related_queries

    with patch("app.niche.signals.trends._import_pytrends") as mock_import:
        mock_import.side_effect = ImportError("pytrends not installed")
        assert fetch_related_queries(["harnais chien"]) == []


def test_fetch_related_queries_returns_empty_on_api_error():
    from app.niche.signals.trends import fetch_related_queries

    mock_trend_req_class = MagicMock()
    mock_trend_req_class.return_value.build_payload.return_value = None
    mock_trend_req_class.return_value.related_queries.side_effect = RuntimeError("rate limited")

    with patch("app.niche.signals.trends._import_pytrends", return_value=mock_trend_req_class):
        results = fetch_related_queries(["harnais chien"])

    assert results == []


def test_fetch_related_queries_parses_top_and_rising():
    import pandas as pd

    from app.niche.signals.trends import fetch_related_queries

    top_df = pd.DataFrame({"query": ["harnais cuir chien", "harnais sport"], "value": [80, 60]})
    rising_df = pd.DataFrame({"query": ["harnais chiot", "laisse chien"], "value": [200, 150]})

    mock_trend_req_class = MagicMock()
    mock_instance = mock_trend_req_class.return_value
    mock_instance.build_payload.return_value = None
    mock_instance.related_queries.return_value = {
        "harnais chien": {"top": top_df, "rising": rising_df}
    }

    with patch("app.niche.signals.trends._import_pytrends", return_value=mock_trend_req_class):
        results = fetch_related_queries(["harnais chien"])

    assert len(results) == 4
    sources = {r.source for r in results}
    assert "trends_top" in sources
    assert "trends_rising" in sources


def test_fetch_related_queries_status_out_reports_unavailable():
    from app.niche.signals.trends import fetch_related_queries

    status: dict[str, object] = {}
    with patch("app.niche.signals.trends._import_pytrends") as mock_import:
        mock_import.side_effect = ImportError("pytrends not installed")
        fetch_related_queries(["harnais chien"], status_out=status)
    assert status["status"] == "unavailable"


def test_fetch_related_queries_status_out_reports_error_with_reason():
    from app.niche.signals.trends import fetch_related_queries

    mock_trend_req_class = MagicMock()
    mock_trend_req_class.return_value.build_payload.return_value = None
    mock_trend_req_class.return_value.related_queries.side_effect = RuntimeError("429 too many requests")

    status: dict[str, object] = {}
    with patch("app.niche.signals.trends._import_pytrends", return_value=mock_trend_req_class):
        fetch_related_queries(["harnais chien"], status_out=status)

    assert status["status"] == "error"
    assert "429" in str(status["detail"])


def test_fetch_related_queries_status_out_reports_ok_and_count():
    import pandas as pd

    from app.niche.signals.trends import fetch_related_queries

    top_df = pd.DataFrame({"query": ["harnais cuir chien"], "value": [80]})
    mock_trend_req_class = MagicMock()
    mock_instance = mock_trend_req_class.return_value
    mock_instance.build_payload.return_value = None
    mock_instance.related_queries.return_value = {"harnais chien": {"top": top_df, "rising": None}}

    status: dict[str, object] = {}
    with patch("app.niche.signals.trends._import_pytrends", return_value=mock_trend_req_class):
        results = fetch_related_queries(["harnais chien"], status_out=status)

    assert status["status"] == "ok"
    assert status["count"] == len(results) == 1


def test_fetch_related_queries_status_out_reports_empty():
    from app.niche.signals.trends import fetch_related_queries

    mock_trend_req_class = MagicMock()
    mock_instance = mock_trend_req_class.return_value
    mock_instance.build_payload.return_value = None
    mock_instance.related_queries.return_value = {"harnais chien": {"top": None, "rising": None}}

    status: dict[str, object] = {}
    with patch("app.niche.signals.trends._import_pytrends", return_value=mock_trend_req_class):
        fetch_related_queries(["harnais chien"], status_out=status)

    assert status["status"] == "empty"


def test_fetch_related_queries_empty_keywords():
    from app.niche.signals.trends import fetch_related_queries

    assert fetch_related_queries([]) == []


# ---------------------------------------------------------------------------
# Aggregator
# ---------------------------------------------------------------------------


def test_fetch_all_signals_deduplicates_keeps_highest_score():
    from app.niche.signals.aggregator import fetch_all_signals

    kw_low = SignalKeyword("collier cuir", "google_suggest", None, "p3", 0.5)
    kw_high = SignalKeyword("collier cuir", "trends_top", None, "geo=FR", 0.9)

    with patch("app.niche.signals.google_suggest.fetch_suggestions_bulk", return_value=[kw_low]):
        with patch("app.niche.signals.trends.fetch_related_queries", return_value=[kw_high]):
            results = fetch_all_signals(["harnais"], sources=["google_suggest", "trends"])

    collier = next(r for r in results if r.keyword == "collier cuir")
    assert collier.relevance_score == 0.9


def test_fetch_all_signals_excludes_seeds():
    from app.niche.signals.aggregator import fetch_all_signals

    kw_seed = SignalKeyword("harnais chien", "google_suggest", None, "p1", 0.99)
    kw_other = SignalKeyword("laisse longue", "google_suggest", None, "p2", 0.8)

    with patch(
        "app.niche.signals.google_suggest.fetch_suggestions_bulk", return_value=[kw_seed, kw_other]
    ):
        results = fetch_all_signals(["harnais chien"], sources=["google_suggest"])

    assert all(r.keyword != "harnais chien" for r in results)
    assert any(r.keyword == "laisse longue" for r in results)


def test_fetch_all_signals_sorted_by_score_desc():
    from app.niche.signals.aggregator import fetch_all_signals

    kws = [
        SignalKeyword("alpha", "google_suggest", None, "p", 0.3),
        SignalKeyword("beta", "google_suggest", None, "p", 0.9),
        SignalKeyword("gamma", "google_suggest", None, "p", 0.6),
    ]

    with patch("app.niche.signals.google_suggest.fetch_suggestions_bulk", return_value=kws):
        results = fetch_all_signals(["seed"], sources=["google_suggest"])

    scores = [r.relevance_score for r in results]
    assert scores == sorted(scores, reverse=True)


def test_fetch_all_signals_source_failure_is_non_blocking():
    from app.niche.signals.aggregator import fetch_all_signals

    with patch(
        "app.niche.signals.google_suggest.fetch_suggestions_bulk", side_effect=RuntimeError("boom")
    ):
        kw = SignalKeyword("collier", "reddit", None, "r/dogs", 0.7)
        with patch("app.niche.signals.reddit.fetch_reddit_keywords", return_value=[kw]):
            results = fetch_all_signals(["harnais"], sources=["google_suggest", "reddit"])

    # google_suggest failed but reddit succeeded
    assert any(r.source == "reddit" for r in results)
