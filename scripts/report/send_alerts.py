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

from scripts._config import get_config

load_dotenv()

console = Console()


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


def detect_cwv_alerts(pagespeed: list[dict[str, Any]], cfg=None) -> list[dict[str, Any]]:
    """Return CWV entries that breach alert thresholds."""
    t = (cfg or get_config()).alert_thresholds
    alerts = []
    for row in pagespeed:
        if row.get("strategy") != "mobile":
            continue
        reasons = []
        score = row.get("performance_score") or 0.0
        lcp = row.get("lcp_ms") or 0.0
        cls_val = row.get("cls") or 0.0
        if score < t.cwv_mobile_min:
            reasons.append(f"score mobile {score:.0%} < {t.cwv_mobile_min:.0%}")
        if lcp > t.cwv_lcp_max_ms:
            reasons.append(f"LCP {lcp:.0f}ms > {t.cwv_lcp_max_ms:.0f}ms")
        if cls_val > t.cwv_cls_max:
            reasons.append(f"CLS {cls_val:.2f} > {t.cwv_cls_max}")
        if reasons:
            alerts.append({"url": row["url"], "reasons": reasons, "score": score, "lcp_ms": lcp, "cls": cls_val})
    return alerts


def detect_position_alerts(opportunities: list[dict[str, Any]], cfg=None) -> list[dict[str, Any]]:
    """Return quick_win URLs worth flagging (position 11-20, high impressions)."""
    t = (cfg or get_config()).alert_thresholds
    return [
        opp for opp in opportunities
        if opp.get("zone") == "quick_win"
        and opp.get("impressions", 0) >= t.quick_win_min_impressions
    ]


def detect_low_ctr_alerts(opportunities: list[dict[str, Any]], cfg=None) -> list[dict[str, Any]]:
    """Return low-CTR URLs with significant impressions."""
    t = (cfg or get_config()).alert_thresholds
    return [
        opp for opp in opportunities
        if opp.get("zone") == "low_ctr"
        and opp.get("impressions", 0) >= t.low_ctr_min_impressions
        and opp.get("ctr_pct", 100.0) < t.low_ctr_max_pct
    ]


def build_alert_summary(
    cwv: list[dict[str, Any]],
    positions: list[dict[str, Any]],
    low_ctr: list[dict[str, Any]],
    date: str,
    site_name: str = "",
) -> str:
    """Build plain-text email body."""
    _site = site_name or get_config().domain
    lines = [
        f"Rapport SEO hebdomadaire — {_site} — {date}",
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
@click.option("--tenant", default=None, help="Tenant ID (default: TENANT_ID env var)")
def main(pagespeed: str, opportunities: str, recipient: str | None, dry_run: bool, tenant: str | None) -> None:
    """Detect SEO regressions and send alert email if needed."""
    cfg = get_config(tenant)
    console.print("[bold cyan]► SEO Alert check[/bold cyan]")

    ps_data = load_pagespeed(pagespeed)
    opp_data = load_gsc_opportunities(opportunities)

    cwv_alerts = detect_cwv_alerts(ps_data, cfg)
    pos_alerts = detect_position_alerts(opp_data, cfg)
    ctr_alerts = detect_low_ctr_alerts(opp_data, cfg)

    total_alerts = len(cwv_alerts) + len(pos_alerts) + len(ctr_alerts)
    console.print(f"  CWV: {len(cwv_alerts)} · Positions: {len(pos_alerts)} · CTR faible: {len(ctr_alerts)}")

    date = datetime.utcnow().strftime("%Y-%m-%d")
    body = build_alert_summary(cwv_alerts, pos_alerts, ctr_alerts, date, site_name=cfg.domain)

    subject = (
        f"[SEO Alert] {cfg.domain} — {total_alerts} alerte(s) — {date}"
        if total_alerts
        else f"[SEO OK] {cfg.domain} — aucune alerte — {date}"
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
