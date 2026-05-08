"""Tests for scripts.audit.fetch_pagespeed."""

from scripts.audit.fetch_pagespeed import fetch_score


def test_fetch_score_returns_expected_keys(pagespeed_response, mocker):
    mocker.patch.dict("os.environ", {"PAGESPEED_API_KEY": "test-key"})
    mock_get = mocker.patch("requests.get")
    mock_get.return_value.status_code = 200
    mock_get.return_value.json.return_value = pagespeed_response

    result = fetch_score("https://www.leoniedelacroix.com", "mobile")

    assert result["url"] == "https://www.leoniedelacroix.com"
    assert result["strategy"] == "mobile"
    assert "performance_score" in result
    assert "lcp_ms" in result
    assert "cls" in result
    assert "tbt_ms" in result


def test_fetch_score_parses_values_correctly(pagespeed_response, mocker):
    mocker.patch.dict("os.environ", {"PAGESPEED_API_KEY": "test-key"})
    mock_get = mocker.patch("requests.get")
    mock_get.return_value.status_code = 200
    mock_get.return_value.json.return_value = pagespeed_response

    result = fetch_score("https://www.leoniedelacroix.com", "mobile")

    assert abs(result["performance_score"] - 0.72) < 0.001
    assert result["lcp_ms"] == 3200
    assert result["cls"] == 0.08
    assert result["tbt_ms"] == 450
