"""Interactive CLI dashboard — real-time SEO health view for leoniedelacroix.com."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import click
import pandas as pd
from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

console = Console()

_SITE = "leoniedelacroix.com"

# ── Data loaders ───────────────────────────────────────────────────────────


def _load_csv(path: str, columns: list[str]) -> pd.DataFrame:
    p = Path(path)
    if not p.exists():
        return pd.DataFrame(columns=columns)
    return pd.read_csv(p)


def _load_json(path: str) -> Any:
    p = Path(path)
    if not p.exists():
        return []
    with open(p, encoding="utf-8") as f:
        return json.load(f)


# ── Data aggregation ───────────────────────────────────────────────────────


def gsc_summary(gsc_path: str) -> dict[str, Any]:
    """Return aggregated GSC metrics."""
    df = _load_csv(gsc_path, ["url", "clicks", "impressions", "ctr", "position"])
    if df.empty:
        return {"clicks": None, "impressions": None, "ctr": None, "position": None, "pages": 0}
    return {
        "clicks": int(df["clicks"].sum()),
        "impressions": int(df["impressions"].sum()),
        "ctr": round(float(df["ctr"].mean()) * 100, 1),
        "position": round(float(df["position"].mean()), 1),
        "pages": len(df),
    }


def eeat_summary(eeat_path: str) -> dict[str, Any]:
    """Return average E-E-A-T score and count of weak pages."""
    data = _load_json(eeat_path)
    if not data:
        return {"avg": None, "weak": None, "total": 0}
    scores = [r.get("global_score", 0) for r in data]
    avg = round(sum(scores) / len(scores) * 100, 1)
    weak = sum(1 for s in scores if s < 0.45)
    return {"avg": avg, "weak": weak, "total": len(data)}


def cannibalization_summary(cannibal_path: str) -> dict[str, Any]:
    """Return cannibalization issue counts by severity."""
    if not Path(cannibal_path).exists():
        return {"high": None, "total": None}
    data = _load_json(cannibal_path)
    if not isinstance(data, list):
        return {"high": None, "total": None}
    high = sum(1 for r in data if r.get("severity", 0) >= 0.6)
    return {"high": high, "total": len(data)}


def pagespeed_summary(pagespeed_path: str) -> dict[str, Any]:
    """Return average mobile performance score."""
    df = _load_csv(pagespeed_path, ["url", "strategy", "performance_score"])
    if df.empty:
        return {"mobile_avg": None}
    mobile = df[df["strategy"] == "mobile"] if "strategy" in df.columns else df
    if mobile.empty:
        return {"mobile_avg": None}
    avg = round(float(mobile["performance_score"].mean()), 2)
    return {"mobile_avg": avg}


def quick_wins_list(opps_path: str, n: int = 5) -> list[dict[str, Any]]:
    """Return top N quick-win opportunities."""
    data = _load_json(opps_path)
    if not isinstance(data, list):
        return []
    wins = [o for o in data if o.get("zone") == "quick_win"]
    wins.sort(key=lambda x: -x.get("impressions", 0))
    return wins[:n]


def top_pages_list(gsc_path: str, n: int = 5) -> list[dict[str, Any]]:
    """Return top N pages by clicks."""
    df = _load_csv(gsc_path, ["url", "clicks", "impressions", "ctr", "position"])
    if df.empty:
        return []
    top = df.nlargest(n, "clicks")
    return top[["url", "clicks", "position"]].to_dict("records")


# ── Rich rendering ─────────────────────────────────────────────────────────


def _na(val: Any, fmt: str = "") -> Text:
    if val is None:
        return Text("N/A", style="dim")
    return Text(format(val, fmt) if fmt else str(val))


def _color(val: float | None, low: float, high: float, invert: bool = False) -> str:
    if val is None:
        return "dim"
    ok = val >= high if not invert else val <= low
    warn = val >= low if not invert else val <= high
    if ok:
        return "green"
    if warn:
        return "yellow"
    return "red"


def _panel_kpis(gsc: dict[str, Any]) -> Panel:
    t = Table.grid(padding=(0, 1))
    t.add_column(min_width=14)
    t.add_column(min_width=10, justify="right")

    clicks = gsc["clicks"]
    imp = gsc["impressions"]
    ctr = gsc["ctr"]
    pos = gsc["position"]

    t.add_row("Clics (90j)", Text(f"{clicks:,}" if clicks is not None else "N/A",
              style=_color(clicks, 500, 2000) if clicks is not None else "dim"))
    t.add_row("Impressions", Text(f"{imp:,}" if imp is not None else "N/A", style="cyan"))
    t.add_row("CTR moyen", Text(f"{ctr}%" if ctr is not None else "N/A",
              style=_color(ctr, 2.0, 4.0) if ctr is not None else "dim"))
    t.add_row("Position moy.", Text(str(pos) if pos is not None else "N/A",
              style=_color(pos, 10, 20, invert=True) if pos is not None else "dim"))
    t.add_row("Pages indexées", Text(str(gsc["pages"]), style="white"))

    return Panel(t, title="[bold]KPIs GSC[/bold]", border_style="blue", padding=(0, 1))


def _panel_health(eeat: dict, cannibal: dict, ps: dict) -> Panel:
    t = Table.grid(padding=(0, 1))
    t.add_column(min_width=16)
    t.add_column(min_width=10, justify="right")

    eeat_avg = eeat["avg"]
    t.add_row("E-E-A-T moyen",
              Text(f"{eeat_avg}%" if eeat_avg is not None else "N/A",
                   style=_color(eeat_avg, 25, 45) if eeat_avg is not None else "dim"))

    weak = eeat["weak"]
    t.add_row("Pages E-E-A-T < 45%",
              Text(str(weak) if weak is not None else "N/A",
                   style="red" if weak else "green"))

    high = cannibal["high"]
    t.add_row("Cannibalisation 🔴",
              Text(str(high) if high is not None else "N/A",
                   style="red" if high else "green"))

    total_c = cannibal["total"]
    t.add_row("Total cannibal.",
              Text(str(total_c) if total_c is not None else "N/A", style="white"))

    mob = ps["mobile_avg"]
    t.add_row("CWV mobile",
              Text(f"{mob:.0%}" if mob is not None else "N/A",
                   style=_color(mob, 0.5, 0.7) if mob is not None else "dim"))

    return Panel(t, title="[bold]Santé SEO[/bold]", border_style="magenta", padding=(0, 1))


def _panel_wins(wins: list[dict]) -> Panel:
    if not wins:
        return Panel(
            Text("Aucun quick win\ndisponible", style="dim"),
            title="[bold]Quick Wins[/bold]",
            border_style="yellow",
            padding=(0, 1),
        )
    t = Table(show_header=True, header_style="bold yellow", box=None, padding=(0, 1))
    t.add_column("Requête", max_width=28, no_wrap=True)
    t.add_column("Imp.", justify="right", min_width=5)
    t.add_column("Pos.", justify="right", min_width=4)
    for w in wins:
        t.add_row(
            w.get("query", "")[:28],
            str(int(w.get("impressions", 0))),
            f"{w.get('position', 0):.1f}",
        )
    return Panel(t, title="[bold]Quick Wins[/bold]", border_style="yellow", padding=(0, 1))


def _panel_top_pages(pages: list[dict]) -> Panel:
    if not pages:
        return Panel(
            Text("Données GSC non disponibles", style="dim"),
            title="[bold]Top pages[/bold]",
            border_style="cyan",
            padding=(0, 1),
        )
    t = Table(show_header=True, header_style="bold cyan", box=None, padding=(0, 1))
    t.add_column("Page", max_width=40, no_wrap=True)
    t.add_column("Clics", justify="right")
    t.add_column("Pos.", justify="right")
    for p in pages:
        slug = p["url"].split("/")[-1] or "/"
        t.add_row(slug[:40], str(int(p["clicks"])), f"{p['position']:.1f}")
    return Panel(t, title="[bold]Top 5 pages[/bold]", border_style="cyan", padding=(0, 1))


def build_layout(
    gsc: dict,
    eeat: dict,
    cannibal: dict,
    ps: dict,
    wins: list,
    pages: list,
    timestamp: str,
) -> Layout:
    layout = Layout()

    header_text = Text(justify="center")
    header_text.append(f" {_SITE} ", style="bold white on dark_blue")
    header_text.append("  SEO Dashboard  ", style="bold")
    header_text.append(f"  {timestamp}", style="dim")

    layout.split_column(
        Layout(Panel(header_text, border_style="dark_blue"), size=3, name="header"),
        Layout(name="top", size=10),
        Layout(name="bottom"),
    )

    layout["top"].split_row(
        Layout(_panel_kpis(gsc), name="kpis"),
        Layout(_panel_health(eeat, cannibal, ps), name="health"),
        Layout(_panel_wins(wins), name="wins"),
    )

    layout["bottom"].split_row(
        Layout(_panel_top_pages(pages), name="pages"),
    )

    return layout


# ── CLI ────────────────────────────────────────────────────────────────────


@click.command()
@click.option("--gsc", default="data/raw/gsc_performance.csv", show_default=True)
@click.option("--opportunities", default="data/raw/gsc_opportunities.json", show_default=True)
@click.option("--cannibalization", default="data/raw/cannibalization.json", show_default=True)
@click.option("--eeat", default="data/raw/eeat_scores.json", show_default=True)
@click.option("--pagespeed", default="data/raw/pagespeed.csv", show_default=True)
@click.option("--watch", is_flag=True, default=False, help="Refresh every 30s (Ctrl+C to exit)")
@click.option("--refresh", default=30, show_default=True, help="Refresh interval in seconds")
def main(
    gsc: str,
    opportunities: str,
    cannibalization: str,
    eeat: str,
    pagespeed: str,
    watch: bool,
    refresh: int,
) -> None:
    """Display real-time SEO health dashboard for leoniedelacroix.com."""

    def _snapshot() -> Layout:
        from datetime import datetime
        ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
        return build_layout(
            gsc_summary(gsc),
            eeat_summary(eeat),
            cannibalization_summary(cannibalization),
            pagespeed_summary(pagespeed),
            quick_wins_list(opportunities),
            top_pages_list(gsc),
            ts,
        )

    if watch:
        with Live(refresh_per_second=1, screen=True) as live:
            while True:
                live.update(_snapshot())
                time.sleep(refresh)
    else:
        console.print(_snapshot())


if __name__ == "__main__":
    main()
