# Scripts Layer

`scripts/` remains the reusable SEO engine for CLI and scheduled workflows.
It is not a disposable legacy folder.

Canonical modules to keep:
- `scripts/audit/` for crawl, GSC, PageSpeed and issue detection.
- `scripts/report/` for Markdown/HTML exports used by CLI and weekly jobs.
- `scripts/_config.py`, `scripts/_paths.py`, `scripts/models.py` and `scripts/cli.py`.

Legacy or transitional modules:
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
