"""Tests for scripts.report.send_alerts."""

import json

from scripts.report.send_alerts import (
    build_alert_summary,
    detect_cwv_alerts,
    detect_low_ctr_alerts,
    detect_position_alerts,
    load_gsc_opportunities,
    load_pagespeed,
    send_email,
)

_PS_ROWS = [
    {
        "url": "https://ex.com",
        "strategy": "mobile",
        "performance_score": 0.45,
        "lcp_ms": 5000.0,
        "cls": 0.30,
        "tbt_ms": 300,
        "fcp_ms": 1200,
    },
    {
        "url": "https://ex.com",
        "strategy": "desktop",
        "performance_score": 0.90,
        "lcp_ms": 1200.0,
        "cls": 0.05,
        "tbt_ms": 100,
        "fcp_ms": 800,
    },
    {
        "url": "https://ex.com/ok",
        "strategy": "mobile",
        "performance_score": 0.80,
        "lcp_ms": 2000.0,
        "cls": 0.05,
        "tbt_ms": 100,
        "fcp_ms": 900,
    },
]

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


def test_load_pagespeed_returns_empty_when_missing(tmp_path):
    result = load_pagespeed(str(tmp_path / "missing.csv"))
    assert result == []


def test_load_pagespeed_reads_csv(tmp_path):
    p = tmp_path / "ps.csv"
    p.write_text("url,strategy,performance_score\nhttps://ex.com,mobile,0.80\n")
    result = load_pagespeed(str(p))
    assert len(result) == 1
    assert result[0]["performance_score"] == 0.80


def test_load_gsc_opportunities_returns_empty_when_missing(tmp_path):
    result = load_gsc_opportunities(str(tmp_path / "missing.json"))
    assert result == []


def test_load_gsc_opportunities_reads_json(tmp_path):
    p = tmp_path / "opp.json"
    p.write_text(json.dumps(_OPP_ROWS))
    result = load_gsc_opportunities(str(p))
    assert len(result) == 4


def test_detect_cwv_alerts_flags_bad_mobile():
    alerts = detect_cwv_alerts(_PS_ROWS)
    assert len(alerts) == 1
    assert alerts[0]["url"] == "https://ex.com"
    reasons_text = " ".join(alerts[0]["reasons"])
    assert "score mobile" in reasons_text
    assert "LCP" in reasons_text
    assert "CLS" in reasons_text


def test_detect_cwv_alerts_ignores_desktop():
    desktop_only = [r for r in _PS_ROWS if r["strategy"] == "desktop"]
    assert detect_cwv_alerts(desktop_only) == []


def test_detect_cwv_alerts_no_alert_when_all_ok():
    ok = [
        {"url": "u", "strategy": "mobile", "performance_score": 0.80, "lcp_ms": 2000.0, "cls": 0.10}
    ]
    assert detect_cwv_alerts(ok) == []


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
    body = build_alert_summary([], [], [], "2026-05-08")
    assert "Aucune alerte" in body


def test_build_alert_summary_with_cwv():
    cwv = [
        {
            "url": "https://ex.com",
            "reasons": ["score mobile 45% < 50%"],
            "score": 0.45,
            "lcp_ms": 5000,
            "cls": 0.30,
        }
    ]
    body = build_alert_summary(cwv, [], [], "2026-05-08")
    assert "Core Web Vitals" in body
    assert "https://ex.com" in body
    assert "score mobile" in body


def test_build_alert_summary_with_positions():
    body = build_alert_summary([], [_OPP_ROWS[0]], [], "2026-05-08")
    assert "quick win" in body.lower() or "Positions 11-20" in body
    assert "https://ex.com/a" in body


def test_build_alert_summary_with_low_ctr():
    body = build_alert_summary([], [], [_OPP_ROWS[2]], "2026-05-08")
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
