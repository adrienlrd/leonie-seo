# Scripts Layer

`scripts/` remains the reusable SEO engine for CLI and scheduled workflows.
It is not a disposable legacy folder.

Canonical modules to keep:
- `scripts/audit/` for crawl, GSC, PageSpeed and issue detection.
- `scripts/report/` for Markdown/HTML exports used by CLI and weekly jobs.
- `scripts/_config.py`, `scripts/_paths.py`, `scripts/models.py` and `scripts/cli.py`.

## CLI-only commands (no Shopify app equivalent)

These commands are available only via `leonie-seo` CLI. They are useful for
self-hosted operators, scheduled workflows, or non-Shopify contexts:

| Command | Script |
|---|---|
| `leonie-seo audit crawl-shopify` | `scripts/audit/crawl_shopify.py` |
| `leonie-seo audit fetch-gsc` | `scripts/audit/fetch_gsc.py` |
| `leonie-seo audit fetch-pagespeed` | `scripts/audit/fetch_pagespeed.py` |
| `leonie-seo audit parse-screaming-frog` | `scripts/audit/parse_screaming_frog.py` |
| `leonie-seo report generate` | `scripts/report/generate_report.py` |
| `leonie-seo report delta` | `scripts/report/generate_delta_report.py` |
| `leonie-seo report monthly` | `scripts/report/generate_monthly_report.py` |
| `leonie-seo report dashboard` | `scripts/report/dashboard.py` |
| `leonie-seo apply generate-suggestions` | `scripts/apply/generate_suggestions.py` |
| `leonie-seo apply rewrite-descriptions` | `scripts/apply/rewrite_descriptions.py` |

## Commands with app equivalents (Phase 10, tasks 83–103)

These CLI commands still work for batch/scheduled use but have UI counterparts
in the embedded Shopify app. Prefer the app for merchant-facing workflows.

| CLI command | Script | App route |
|---|---|---|
| `leonie-seo report faq` | `scripts/report/generate_faq.py` | `app.content` (FAQ tab) |
| `leonie-seo report blog-briefs` | `scripts/report/generate_blog_briefs.py` | `app.content` (Briefs tab) |
| `leonie-seo report hreflang` | `scripts/report/generate_hreflang.py` | `app.hreflang` |
| `leonie-seo report send-alerts` | `scripts/report/send_alerts.py` | `app.alerts` |
| `leonie-seo report ice-matrix` | `scripts/report/ice_matrix.py` | `app.ice` |
| `leonie-seo report semantics` | `scripts/report/analyze_semantics.py` | `app.semantics` |
| `leonie-seo report eeat` | `scripts/report/score_eeat.py` | `app.semantics` |
| `leonie-seo report internal-links` | `scripts/report/detect_internal_links.py` | `app.internal-links` |
| `leonie-seo apply update-meta` | `scripts/apply/update_meta.py` | `app._index` (apply) |
| `leonie-seo apply update-alt-text` | `scripts/apply/update_alt_text.py` | `app.alt-text` |
| `leonie-seo apply create-redirects` | `scripts/apply/create_redirects.py` | `app.redirects` |
| `leonie-seo apply add-schema` | `scripts/apply/add_schema.py` | `app.jsonld` |
| `leonie-seo apply rollback` | `scripts/apply/rollback.py` | `app.rollback` |

## Legacy or transitional modules

- `scripts/apply/update_meta.py`, `update_alt_text.py`, `add_schema.py` are CLI writers.
  New App Store code should prefer `app/apply/`.
- `scripts/apply/generate_suggestions.py` and `rewrite_descriptions.py` are pre-LLM
  generators. New generation code should prefer `app/llm/`.
- `scripts/license.py` is self-hosted/agency tooling. App Store billing uses
  Shopify Billing in `app/billing/`.

Dependency direction rule:
- CLI scripts may call the application engine where needed.
- New `app/` code should not import `scripts/apply/` or `scripts/license.py`.
- The remaining `app/api/audit.py -> scripts/audit + scripts/report` bridge is
  transitional because those modules are still the canonical audit engine.
