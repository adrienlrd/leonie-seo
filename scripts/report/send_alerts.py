"""Send SEO alert emails when regressions are detected."""

from __future__ import annotations

import json
import os
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Any

import click
import pandas as pd
from dotenv import load_dotenv
from rich.console import Console

load_dotenv()

console = Console()

# Alert thresholds
_CWV_MOBILE_MIN = 0.50
_CWV_LCP_MAX_MS = 4000.0
_CWV_CLS_MAX = 0.25
_QUICK_WIN_MIN_IMPRESSIONS = 30
_LOW_CTR_MIN_IMPRESSIONS = 100
_LOW_CTR_MAX_PCT = 1.0


class AlertError(Exception):
    pass


def load_pagespeed(path: str) -> list[dict[str, Any]]:
    """Load pagespeed CSV, return empty list if file missing."""
    p = Path(path)
    if not p.exists():
        return []
    return pd.read_csv(p).to_dict("records")


def load_gsc_opportunities(path: str) -> list[dict[str, Any]]:
    """Load GSC opportunities JSON, return empty list if file missing."""
    p = Path(path)
    if not p.exists():
        return []
    with p.open(encoding="utf-8") as f:
        return json.load(f)


def detect_cwv_alerts(pagespeed: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return CWV entries that breach alert thresholds."""
    alerts = []
    for row in pagespeed:
        if row.get("strategy") != "mobile":
            continue
        reasons = []
        score = row.get("performance_score") or 0.0
        lcp = row.get("lcp_ms") or 0.0
        cls = row.get("cls") or 0.0
        if score < _CWV_MOBILE_MIN:
            reasons.append(f"score mobile {score:.0%} < {_CWV_MOBILE_MIN:.0%}")
        if lcp > _CWV_LCP_MAX_MS:
            reasons.append(f"LCP {lcp:.0f}ms > {_CWV_LCP_MAX_MS:.0f}ms")
        if cls > _CWV_CLS_MAX:
            reasons.append(f"CLS {cls:.2f} > {_CWV_CLS_MAX}")
        if reasons:
            alerts.append({"url": row["url"], "reasons": reasons, "score": score, "lcp_ms": lcp, "cls": cls})
    return alerts


def detect_position_alerts(opportunities: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return quick_win URLs worth flagging (position 11-20, high impressions)."""
    return [
        opp for opp in opportunities
        if opp.get("zone") == "quick_win"
        and opp.get("impressions", 0) >= _QUICK_WIN_MIN_IMPRESSIONS
    ]


def detect_low_ctr_alerts(opportunities: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return low-CTR URLs with significant impressions."""
    return [
        opp for opp in opportunities
        if opp.get("zone") == "low_ctr"
        and opp.get("impressions", 0) >= _LOW_CTR_MIN_IMPRESSIONS
        and opp.get("ctr_pct", 100.0) < _LOW_CTR_MAX_PCT
    ]


def build_alert_summary(
    cwv: list[dict[str, Any]],
    positions: list[dict[str, Any]],
    low_ctr: list[dict[str, Any]],
    date: str,
) -> str:
    """Build plain-text email body."""
    lines = [
        f"Rapport SEO hebdomadaire — leoniedelacroix.com — {date}",
        "=" * 60,
        "",
    ]

    if not cwv and not positions and not low_ctr:
        lines.append("Aucune alerte cette semaine. Tout est dans les clous.")
        return "\n".join(lines)

    total = len(cwv) + len(positions) + len(low_ctr)
    lines.append(f"{total} alerte(s) détectée(s) :\n")

    if cwv:
        lines.append(f"🔴 Core Web Vitals — {len(cwv)} URL(s) sous le seuil")
        lines.append("-" * 40)
        for a in cwv:
            lines.append(f"  {a['url']}")
            for r in a["reasons"]:
                lines.append(f"    → {r}")
        lines.append("")

    if positions:
        lines.append(f"🟡 Positions 11-20 — {len(positions)} opportunité(s) quick win")
        lines.append("-" * 40)
        for p in positions:
            lines.append(
                f"  {p['url']}\n"
                f"    pos {p['position']:.1f} · {p['impressions']} impressions"
                f" · +{p['estimated_gain_clicks']} clics estimés"
            )
        lines.append("")

    if low_ctr:
        lines.append(f"🟠 CTR faible — {len(low_ctr)} URL(s) à optimiser")
        lines.append("-" * 40)
        for p in low_ctr:
            lines.append(
                f"  {p['url']}\n"
                f"    pos {p['position']:.1f} · CTR {p['ctr_pct']:.1f}%"
                f" · {p['impressions']} impressions"
            )
        lines.append("")

    lines.append("—")
    lines.append("Généré automatiquement par le pipeline SEO leoniedelacroix.com")
    return "\n".join(lines)


def send_email(subject: str, body: str, sender: str, recipient: str, app_password: str) -> None:
    """Send email via Gmail SMTP."""
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = recipient
    msg.attach(MIMEText(body, "plain", "utf-8"))

    with smtplib.SMTP("smtp.gmail.com", 587) as smtp:
        smtp.ehlo()
        smtp.starttls()
        smtp.login(sender, app_password)
        smtp.sendmail(sender, recipient, msg.as_string())


@click.command()
@click.option("--pagespeed", default="data/raw/pagespeed.csv", show_default=True)
@click.option("--opportunities", default="data/raw/gsc_opportunities.json", show_default=True)
@click.option("--recipient", default=None, help="Override recipient email")
@click.option("--dry-run/--apply", default=True, show_default=True)
def main(pagespeed: str, opportunities: str, recipient: str | None, dry_run: bool) -> None:
    """Detect SEO regressions and send alert email if needed."""
    console.print("[bold cyan]► SEO Alert check[/bold cyan]")

    ps_data = load_pagespeed(pagespeed)
    opp_data = load_gsc_opportunities(opportunities)

    cwv_alerts = detect_cwv_alerts(ps_data)
    pos_alerts = detect_position_alerts(opp_data)
    ctr_alerts = detect_low_ctr_alerts(opp_data)

    total_alerts = len(cwv_alerts) + len(pos_alerts) + len(ctr_alerts)
    console.print(f"  CWV: {len(cwv_alerts)} · Positions: {len(pos_alerts)} · CTR faible: {len(ctr_alerts)}")

    date = datetime.utcnow().strftime("%Y-%m-%d")
    body = build_alert_summary(cwv_alerts, pos_alerts, ctr_alerts, date)

    subject = (
        f"[SEO Alert] leoniedelacroix.com — {total_alerts} alerte(s) — {date}"
        if total_alerts
        else f"[SEO OK] leoniedelacroix.com — aucune alerte — {date}"
    )

    if dry_run:
        console.print("\n[dim]── DRY RUN — email non envoyé ──[/dim]")
        console.print(f"[bold]Sujet :[/bold] {subject}")
        console.print("[bold]Corps :[/bold]")
        console.print(body)
        return

    sender = os.environ.get("GMAIL_SENDER")
    app_password = os.environ.get("GMAIL_APP_PASSWORD")
    to = recipient or os.environ.get("ALERT_EMAIL", "adrien.leredde@outlook.com")

    if not sender or not app_password:
        raise AlertError("GMAIL_SENDER et GMAIL_APP_PASSWORD requis pour --apply")

    send_email(subject, body, sender, to, app_password)
    console.print(f"  [green]✓[/green] Email envoyé → {to}")


if __name__ == "__main__":
    main()
