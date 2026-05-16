"""leonie-seo — top-level CLI aggregator.

Entry point: ``leonie-seo <group> <command> [options]``
"""

from __future__ import annotations

import click

from scripts.apply.add_schema import main as schema_main
from scripts.apply.create_redirects import main as redirects_main
from scripts.apply.generate_suggestions import main as suggestions_main
from scripts.apply.rewrite_descriptions import main as rewrite_main
from scripts.apply.rollback import main as rollback_main
from scripts.apply.update_alt_text import main as alt_main
from scripts.apply.update_meta import main as meta_main
from scripts.audit.analyze_longtail import main as longtail_main
from scripts.audit.crawl_shopify import main as crawl_main
from scripts.audit.detect_cannibalization import main as cannibalization_main
from scripts.audit.detect_gsc_opportunities import main as gsc_opp_main
from scripts.audit.fetch_gsc import main as fetch_gsc_main
from scripts.audit.fetch_pagespeed import main as pagespeed_main
from scripts.audit.parse_screaming_frog import main as screaming_frog_main
from scripts.license import cli as license_cli
from scripts.pilot_smoke import smoke_public
from scripts.report.analyze_semantics import main as semantics_main
from scripts.report.dashboard import main as dashboard_main
from scripts.report.detect_internal_links import main as links_main
from scripts.report.generate_blog_briefs import main as briefs_main
from scripts.report.generate_delta_report import main as delta_main
from scripts.report.generate_faq import main as faq_main
from scripts.report.generate_hreflang import main as hreflang_main
from scripts.report.generate_monthly_report import main as monthly_main
from scripts.report.generate_report import main as report_main
from scripts.report.ice_matrix import main as ice_main
from scripts.report.score_eeat import main as eeat_main
from scripts.report.send_alerts import main as alerts_main
from scripts.setup import cli as setup_cli


@click.group()
@click.version_option(package_name="leonie-seo")
def cli() -> None:
    """leonie-seo — SEO automation pipeline for Shopify boutiques."""


# ── setup & license ───────────────────────────────────────────────────────────

cli.add_command(setup_cli, name="setup")
cli.add_command(license_cli, name="license")

# ── audit ─────────────────────────────────────────────────────────────────────


@cli.group()
def audit() -> None:
    """Read-only audit commands — snapshot Shopify, GSC, PageSpeed."""


audit.add_command(crawl_main, name="crawl-shopify")
audit.add_command(fetch_gsc_main, name="fetch-gsc")
audit.add_command(pagespeed_main, name="fetch-pagespeed")
audit.add_command(screaming_frog_main, name="parse-screaming-frog")
audit.add_command(gsc_opp_main, name="detect-gsc-opportunities")
audit.add_command(longtail_main, name="analyze-longtail")
audit.add_command(cannibalization_main, name="detect-cannibalization")

# ── report ────────────────────────────────────────────────────────────────────


@cli.group()
def report() -> None:
    """Reporting commands — generate Markdown/HTML reports and dashboards."""


report.add_command(report_main, name="generate")
report.add_command(ice_main, name="ice-matrix")
report.add_command(delta_main, name="delta")
report.add_command(monthly_main, name="monthly")
report.add_command(semantics_main, name="semantics")
report.add_command(eeat_main, name="eeat")
report.add_command(faq_main, name="faq")
report.add_command(briefs_main, name="blog-briefs")
report.add_command(hreflang_main, name="hreflang")
report.add_command(links_main, name="internal-links")
report.add_command(alerts_main, name="send-alerts")
report.add_command(dashboard_main, name="dashboard")

# ── apply ─────────────────────────────────────────────────────────────────────


@cli.group()
def apply() -> None:
    """Write commands — push changes to Shopify (dry-run by default)."""


apply.add_command(suggestions_main, name="generate-suggestions")
apply.add_command(meta_main, name="update-meta")
apply.add_command(alt_main, name="update-alt-text")
apply.add_command(redirects_main, name="create-redirects")
apply.add_command(schema_main, name="add-schema")
apply.add_command(rewrite_main, name="rewrite-descriptions")
apply.add_command(rollback_main, name="rollback")


# ── pilot ─────────────────────────────────────────────────────────────────────


@cli.group()
def pilot() -> None:
    """Real-store pilot checks and operator commands."""


pilot.add_command(smoke_public, name="smoke-public")


if __name__ == "__main__":
    cli()
