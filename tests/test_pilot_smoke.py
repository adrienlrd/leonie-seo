"""Tests for public pilot smoke checks."""

from __future__ import annotations

from click.testing import CliRunner

from scripts.cli import cli
from scripts.pilot_smoke import run_public_smoke_checks


class _Response:
    def __init__(self, status_code: int, text: str = "", json_payload: dict | None = None) -> None:
        self.status_code = status_code
        self.text = text
        self._json_payload = json_payload or {}
        self.content = text.encode("utf-8") if text else b"{}"

    def json(self) -> dict:
        return self._json_payload


def test_run_public_smoke_checks_passes_when_all_public_endpoints_are_healthy(mocker) -> None:
    def _get(url: str, timeout: float) -> _Response:
        if url.endswith("/healthz"):
            return _Response(200, "ok")
        if url.endswith("/health"):
            return _Response(200, json_payload={"status": "ok", "missing_env": []})
        if url.endswith("/privacy"):
            return _Response(200, "<html></html>")
        raise AssertionError(url)

    mocker.patch("scripts.pilot_smoke.requests.get", side_effect=_get)

    results = run_public_smoke_checks(web_url="https://web.example", api_url="https://api.example")

    assert [result.name for result in results] == ["web_health", "api_health", "privacy"]
    assert all(result.ok for result in results)


def test_run_public_smoke_checks_fails_when_api_reports_missing_env(mocker) -> None:
    def _get(url: str, timeout: float) -> _Response:
        if url.endswith("/healthz"):
            return _Response(200, "ok")
        if url.endswith("/health"):
            return _Response(
                200,
                json_payload={"status": "ok", "missing_env": ["LEONIE_MASTER_KEY"]},
            )
        if url.endswith("/privacy"):
            return _Response(200, "<html></html>")
        raise AssertionError(url)

    mocker.patch("scripts.pilot_smoke.requests.get", side_effect=_get)

    results = run_public_smoke_checks(web_url="https://web.example", api_url="https://api.example")

    assert results[1].name == "api_health"
    assert results[1].ok is False
    assert "LEONIE_MASTER_KEY" in results[1].detail


def test_smoke_public_cli_exits_non_zero_when_a_check_fails(mocker) -> None:
    mocker.patch(
        "scripts.pilot_smoke.run_public_smoke_checks",
        return_value=[
            type(
                "Result",
                (),
                {
                    "name": "api_health",
                    "url": "https://api.example/health",
                    "ok": False,
                    "detail": "status=503",
                },
            )()
        ],
    )

    result = CliRunner().invoke(cli, ["pilot", "smoke-public"])

    assert result.exit_code != 0
    assert "FAIL api_health" in result.output
