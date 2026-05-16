"""Smoke tests for scripts.cli — verify all groups and sub-commands are reachable."""

from __future__ import annotations

import pytest
from click.testing import CliRunner

from scripts.cli import cli


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


# ── top-level ─────────────────────────────────────────────────────────────────


def test_cli_help_exits_zero(runner: CliRunner) -> None:
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0


def test_cli_version_exits_zero(runner: CliRunner) -> None:
    result = runner.invoke(cli, ["--version"])
    assert result.exit_code == 0


def test_cli_lists_all_groups(runner: CliRunner) -> None:
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    for group in ("setup", "license", "audit", "report", "apply", "pilot"):
        assert group in result.output


# ── audit group ───────────────────────────────────────────────────────────────


def test_audit_group_help(runner: CliRunner) -> None:
    result = runner.invoke(cli, ["audit", "--help"])
    assert result.exit_code == 0


def test_audit_lists_commands(runner: CliRunner) -> None:
    result = runner.invoke(cli, ["audit", "--help"])
    assert result.exit_code == 0
    for cmd in (
        "crawl-shopify",
        "fetch-gsc",
        "fetch-pagespeed",
        "parse-screaming-frog",
        "detect-gsc-opportunities",
        "analyze-longtail",
        "detect-cannibalization",
    ):
        assert cmd in result.output


def test_audit_crawl_shopify_help(runner: CliRunner) -> None:
    result = runner.invoke(cli, ["audit", "crawl-shopify", "--help"])
    assert result.exit_code == 0


def test_audit_fetch_gsc_help(runner: CliRunner) -> None:
    result = runner.invoke(cli, ["audit", "fetch-gsc", "--help"])
    assert result.exit_code == 0


def test_audit_fetch_pagespeed_help(runner: CliRunner) -> None:
    result = runner.invoke(cli, ["audit", "fetch-pagespeed", "--help"])
    assert result.exit_code == 0


def test_audit_parse_screaming_frog_help(runner: CliRunner) -> None:
    result = runner.invoke(cli, ["audit", "parse-screaming-frog", "--help"])
    assert result.exit_code == 0


def test_audit_detect_gsc_opportunities_help(runner: CliRunner) -> None:
    result = runner.invoke(cli, ["audit", "detect-gsc-opportunities", "--help"])
    assert result.exit_code == 0


def test_audit_analyze_longtail_help(runner: CliRunner) -> None:
    result = runner.invoke(cli, ["audit", "analyze-longtail", "--help"])
    assert result.exit_code == 0


def test_audit_detect_cannibalization_help(runner: CliRunner) -> None:
    result = runner.invoke(cli, ["audit", "detect-cannibalization", "--help"])
    assert result.exit_code == 0


# ── report group ──────────────────────────────────────────────────────────────


def test_report_group_help(runner: CliRunner) -> None:
    result = runner.invoke(cli, ["report", "--help"])
    assert result.exit_code == 0


def test_report_lists_commands(runner: CliRunner) -> None:
    result = runner.invoke(cli, ["report", "--help"])
    assert result.exit_code == 0
    for cmd in (
        "generate",
        "ice-matrix",
        "delta",
        "monthly",
        "semantics",
        "eeat",
        "faq",
        "blog-briefs",
        "hreflang",
        "internal-links",
        "send-alerts",
        "dashboard",
    ):
        assert cmd in result.output


def test_report_generate_help(runner: CliRunner) -> None:
    result = runner.invoke(cli, ["report", "generate", "--help"])
    assert result.exit_code == 0


def test_report_ice_matrix_help(runner: CliRunner) -> None:
    result = runner.invoke(cli, ["report", "ice-matrix", "--help"])
    assert result.exit_code == 0


def test_report_delta_help(runner: CliRunner) -> None:
    result = runner.invoke(cli, ["report", "delta", "--help"])
    assert result.exit_code == 0


def test_report_monthly_help(runner: CliRunner) -> None:
    result = runner.invoke(cli, ["report", "monthly", "--help"])
    assert result.exit_code == 0


def test_report_semantics_help(runner: CliRunner) -> None:
    result = runner.invoke(cli, ["report", "semantics", "--help"])
    assert result.exit_code == 0


def test_report_eeat_help(runner: CliRunner) -> None:
    result = runner.invoke(cli, ["report", "eeat", "--help"])
    assert result.exit_code == 0


def test_report_faq_help(runner: CliRunner) -> None:
    result = runner.invoke(cli, ["report", "faq", "--help"])
    assert result.exit_code == 0


def test_report_blog_briefs_help(runner: CliRunner) -> None:
    result = runner.invoke(cli, ["report", "blog-briefs", "--help"])
    assert result.exit_code == 0


def test_report_hreflang_help(runner: CliRunner) -> None:
    result = runner.invoke(cli, ["report", "hreflang", "--help"])
    assert result.exit_code == 0


def test_report_internal_links_help(runner: CliRunner) -> None:
    result = runner.invoke(cli, ["report", "internal-links", "--help"])
    assert result.exit_code == 0


def test_report_send_alerts_help(runner: CliRunner) -> None:
    result = runner.invoke(cli, ["report", "send-alerts", "--help"])
    assert result.exit_code == 0


def test_report_dashboard_help(runner: CliRunner) -> None:
    result = runner.invoke(cli, ["report", "dashboard", "--help"])
    assert result.exit_code == 0


# ── apply group ───────────────────────────────────────────────────────────────


def test_apply_group_help(runner: CliRunner) -> None:
    result = runner.invoke(cli, ["apply", "--help"])
    assert result.exit_code == 0


def test_apply_lists_commands(runner: CliRunner) -> None:
    result = runner.invoke(cli, ["apply", "--help"])
    assert result.exit_code == 0
    for cmd in (
        "generate-suggestions",
        "update-meta",
        "update-alt-text",
        "create-redirects",
        "add-schema",
        "rewrite-descriptions",
        "rollback",
    ):
        assert cmd in result.output


def test_apply_generate_suggestions_help(runner: CliRunner) -> None:
    result = runner.invoke(cli, ["apply", "generate-suggestions", "--help"])
    assert result.exit_code == 0


def test_apply_update_meta_help(runner: CliRunner) -> None:
    result = runner.invoke(cli, ["apply", "update-meta", "--help"])
    assert result.exit_code == 0


def test_apply_update_alt_text_help(runner: CliRunner) -> None:
    result = runner.invoke(cli, ["apply", "update-alt-text", "--help"])
    assert result.exit_code == 0


def test_apply_create_redirects_help(runner: CliRunner) -> None:
    result = runner.invoke(cli, ["apply", "create-redirects", "--help"])
    assert result.exit_code == 0


def test_apply_add_schema_help(runner: CliRunner) -> None:
    result = runner.invoke(cli, ["apply", "add-schema", "--help"])
    assert result.exit_code == 0


def test_apply_rewrite_descriptions_help(runner: CliRunner) -> None:
    result = runner.invoke(cli, ["apply", "rewrite-descriptions", "--help"])
    assert result.exit_code == 0


def test_apply_rollback_help(runner: CliRunner) -> None:
    result = runner.invoke(cli, ["apply", "rollback", "--help"])
    assert result.exit_code == 0


# ── setup & license ───────────────────────────────────────────────────────────


def test_setup_group_help(runner: CliRunner) -> None:
    result = runner.invoke(cli, ["setup", "--help"])
    assert result.exit_code == 0


def test_license_group_help(runner: CliRunner) -> None:
    result = runner.invoke(cli, ["license", "--help"])
    assert result.exit_code == 0


def test_license_issue_help(runner: CliRunner) -> None:
    result = runner.invoke(cli, ["license", "issue", "--help"])
    assert result.exit_code == 0


def test_license_check_help(runner: CliRunner) -> None:
    result = runner.invoke(cli, ["license", "check", "--help"])
    assert result.exit_code == 0


# ── pilot ────────────────────────────────────────────────────────────────────


def test_pilot_group_help(runner: CliRunner) -> None:
    result = runner.invoke(cli, ["pilot", "--help"])
    assert result.exit_code == 0


def test_pilot_lists_commands(runner: CliRunner) -> None:
    result = runner.invoke(cli, ["pilot", "--help"])
    assert result.exit_code == 0
    assert "smoke-public" in result.output


def test_pilot_smoke_public_help(runner: CliRunner) -> None:
    result = runner.invoke(cli, ["pilot", "smoke-public", "--help"])
    assert result.exit_code == 0
