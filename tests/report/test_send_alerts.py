"""Tests for scripts.report.send_alerts."""

import json

from scripts.report.send_alerts import (
    build_alert_summary,
    detect_low_ctr_alerts,
    detect_position_alerts,
    load_gsc_opportunities,
    send_email,
)

_OPP_ROWS = [
    {
        "url": "https://ex.com/a",
        "zone": "quick_win",
        "position": 14.0,
        "impressions": 80,
        "clicks": 2,
        "ctr_pct": 2.5,
        "estimated_gain_clicks": 20,
        "action": "",
    },
    {
        "url": "https://ex.com/b",
        "zone": "quick_win",
        "position": 18.0,
        "impressions": 10,
        "clicks": 0,
        "ctr_pct": 0.0,
        "estimated_gain_clicks": 5,
        "action": "",
    },
    {
        "url": "https://ex.com/c",
        "zone": "low_ctr",
        "position": 5.0,
        "impressions": 300,
        "clicks": 2,
        "ctr_pct": 0.7,
        "estimated_gain_clicks": 12,
        "action": "",
    },
    {
        "url": "https://ex.com/d",
        "zone": "low_ctr",
        "position": 7.0,
        "impressions": 50,
        "clicks": 1,
        "ctr_pct": 2.0,
        "estimated_gain_clicks": 3,
        "action": "",
    },
]


def test_load_gsc_opportunities_returns_empty_when_missing(tmp_path):
    result = load_gsc_opportunities(str(tmp_path / "missing.json"))
    assert result == []


def test_load_gsc_opportunities_reads_json(tmp_path):
    p = tmp_path / "opp.json"
    p.write_text(json.dumps(_OPP_ROWS))
    result = load_gsc_opportunities(str(p))
    assert len(result) == 4


def test_detect_position_alerts_filters_by_impressions():
    alerts = detect_position_alerts(_OPP_ROWS)
    assert len(alerts) == 1
    assert alerts[0]["url"] == "https://ex.com/a"


def test_detect_position_alerts_ignores_low_ctr_zone():
    alerts = detect_position_alerts(_OPP_ROWS)
    zones = {a["zone"] for a in alerts}
    assert zones == {"quick_win"}


def test_detect_low_ctr_alerts_filters_threshold():
    alerts = detect_low_ctr_alerts(_OPP_ROWS)
    assert len(alerts) == 1
    assert alerts[0]["url"] == "https://ex.com/c"


def test_build_alert_summary_no_alerts():
    body = build_alert_summary([], [], "2026-05-08")
    assert "Aucune alerte" in body


def test_build_alert_summary_with_positions():
    body = build_alert_summary([_OPP_ROWS[0]], [], "2026-05-08")
    assert "quick win" in body.lower() or "Positions 11-20" in body
    assert "https://ex.com/a" in body


def test_build_alert_summary_with_low_ctr():
    body = build_alert_summary([], [_OPP_ROWS[2]], "2026-05-08")
    assert "CTR" in body
    assert "https://ex.com/c" in body


def test_send_email_calls_smtp(mocker):
    mock_smtp_cls = mocker.patch("smtplib.SMTP")
    mock_smtp = mock_smtp_cls.return_value.__enter__.return_value

    send_email("Sujet", "Corps", "from@gmail.com", "to@outlook.com", "app_pw")

    mock_smtp.starttls.assert_called_once()
    mock_smtp.login.assert_called_once_with("from@gmail.com", "app_pw")
    mock_smtp.sendmail.assert_called_once()
    args = mock_smtp.sendmail.call_args[0]
    assert args[0] == "from@gmail.com"
    assert args[1] == "to@outlook.com"
