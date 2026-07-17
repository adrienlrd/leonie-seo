# AGENTS.md — GEO by Organically

## 1. Project overview

- **Name:** GEO by Organically
- **Goal:** Shopify SEO automation pipeline and public Shopify app for niche-first SEO recommendations, supervised content generation, SEO audits, and safe Shopify application.
- **App type:** Shopify public app plus self-hosted/CLI mode.
- **Short-term vision:** Complete Phase 10 parity between CLI capabilities and the embedded Shopify app, then prepare App Store go/no-go.
- **Long-term vision:** Become a Shopify-native SEO copilot that prioritizes actions by niche opportunity, measurable impact, merchant validation, and safe execution.

Before modifying code, an agent must:

1. Read this file entirely.
2. Inspect `git status --short` when working locally.
3. Read `docs/AI_HANDOFF.md` for current agent state.
4. Read `PROGRESS.md` for roadmap progress and next task.
5. Read `docs/COMMANDS.md` to identify relevant validation commands.
6. Keep diffs small and focused.

## 2. Tech stack

Detected from the repository files reviewed:

- **Primary language:** Python 3.11+ and TypeScript.
- **Backend framework:** FastAPI.
- **CLI framework:** Click.
- **Frontend framework:** Remix + React.
- **Shopify integration:** Shopify embedded app, App Bridge, Polaris, OAuth, Billing, webhooks, Theme App Extension.
- **Database:** Postgres support and legacy SQLite/history storage are documented.
- **ORM:** Not clearly detected from reviewed files.
- **Package manager:** pip for Python, npm for `shopify-app/`.
- **Lint:** Ruff.
- **Format:** Not configured as a dedicated command.
- **Type checker:** TypeScript `tsc` for `shopify-app/`; Python type checker not configured.
- **Test framework:** pytest.
- **Build tool:** Remix/Vite build in `shopify-app/`; Docker for backend image.
- **Deployment:** Docker and Render pilot deployment are documented.

## 3. Repository structure

- `app/` — Python backend, FastAPI routes, OAuth, billing, jobs, integrations and application services. Modify with tests. Avoid casual changes to Shopify auth, billing, jobs or write guards.
- `scripts/` — Click CLI and reusable SEO engines for audit, apply and reports. Preserve CLI compatibility and dry-run defaults.
- `shopify-app/` — Shopify embedded Remix app with React, App Bridge and Polaris. Validate with typecheck/build after UI changes.
- `shopify-app/extensions/` — Shopify extension surface. Modify only with Shopify compatibility checks.
- `config/` — tenant, niche and prompt configuration. Do not commit private values.
- `data/` — local data and generated exports. Do not commit sensitive or generated merchant data.
- `reports/` — generated reports. Avoid committing generated outputs unless explicitly requested.
- `tests/` — Python tests. Update with logic changes.
- `docs/` — project, pilot, architecture, commands and handoff documentation. Keep current after meaningful work.
- `.claude/` — shared Claude Code settings and subagents. Keep shareable and non-local.

## 4. Architecture rules

- Respect the existing architecture.
- Do not reorganize files or folders without explicit request.
- If a domain layer exists, it must not depend on infrastructure or presentation layers.
- If Clean Architecture is present, dependencies must point inward.
- No infrastructure imports inside domain code.
- No generic helpers for one-off use cases.
- No speculative abstraction.
- Prefer simple, readable, testable modules.
- Reuse existing `scripts/` logic from the app when possible instead of duplicating SEO engines.
- No new dependency without a documented reason.
- Do not change Shopify OAuth, billing, webhooks, scopes, or production deployment config without explicit request.

## 5. Coding standards

- Communicate with the user in French.
- Use English for code identifiers, filenames, comments, docstrings, commits and technical implementation details.
- Preserve French for merchant-facing French documentation, UI copy and product copy.
- Use type hints for Python functions and methods when Python is changed.
- Keep functions small and explicit.
- Avoid clever one-liners unless clearly readable.
- Comments should explain non-obvious intent, not restate code.
- No `except: pass`.
- No bare `except Exception` without documented justification.
- Validate inputs at system boundaries.
- Avoid changing public behavior unless the task explicitly requires it.

## 6. Testing and validation

Use `docs/COMMANDS.md` as the command reference.

| Purpose | Command |
|---|---|
| Install | `pip install -e .` / `pip install -e .[dev]` |
| Backend dev | `uvicorn app.main:app --host 0.0.0.0 --port 8000` |
| CLI help | `leonie-seo --help` |
| Python lint | `ruff check .` |
| Python tests | `pytest` |
| Shopify install | `cd shopify-app && npm install` |
| Shopify dev | `cd shopify-app && npm run dev` |
| Shopify typecheck | `cd shopify-app && npm run typecheck` |
| Shopify build | `cd shopify-app && npm run build` |
| Docker build | `docker build -t leonie-seo .` |

Rule: before marking a task done, run the relevant validation commands or explicitly explain why they were not run.

## 7. Git workflow for AI agents

- Start with `git status --short` when working locally.
- Never overwrite user changes.
- Never mix unrelated changes.
- Never reformat the whole project unless explicitly requested.
- Keep diffs small.
- In every final summary, list files created, files modified, commands run, commands failed, tests run, tests not run with reason, and open risks.

## 8. Codex-specific workflow

- Read `AGENTS.md` before editing.
- For simple tasks: edit directly, then validate.
- For complex tasks: produce a short plan before editing.
- Use only relevant files as context.
- Avoid dumping long logs into the conversation.
- Use sub-tasks only for exploration, testing, analysis and triage.
- Do not run multiple agents that write to the same files in parallel.
- Codex normally reads `~/.codex/AGENTS.md`, then repo `AGENTS.md` files from root to current folder. `CODEX_HOME` may change the home path.
- Use nested `AGENTS.md` only when a subdirectory has genuinely different rules.
- Do not create `AGENTS.override.md` unless a temporary override is explicitly needed and documented.

## 9. Claude Code-specific workflow

Claude Code reads `CLAUDE.md`, which imports this file via `@AGENTS.md`.

Use plan mode before:

- Large refactors
- Architecture changes
- Database schema or migration changes
- Shopify OAuth changes
- Shopify billing changes
- Webhook changes
- API scope changes
- Deployment or production config changes

Prefer read-only exploration before editing.

Use subagents for code review, test triage, Shopify architecture review, security review and UI/UX review when relevant.

Hooks are allowed only for validation or safety. Hooks must not be destructive and must not bypass confirmations. Do not add project hooks unless the called script already exists and is safe.

Never let Claude Code and Codex modify the same files simultaneously.

## 10. AI handoff protocol

After every meaningful task, update `docs/AI_HANDOFF.md` with:

- Date
- Agent name
- Task goal
- Summary of changes
- Files created
- Files modified
- Decisions made
- Validations run
- Validations skipped, with reason
- Open issues
- Next recommended action

Continue using `PROGRESS.md` for detailed roadmap status and `docs/AI_HANDOFF.md` for compact agent handoff.

## 11. Safety rules

- Never expose secrets.
- Never hardcode credentials.
- Never modify production config without explicit request.
- Never run destructive commands without confirmation.
- Never delete migrations, data files or schemas without justification.
- Never commit `.env`, `.env.*`, `.claude/settings.local.json`, or `CLAUDE.local.md`.
- Treat generated folders and dependency folders as non-editable unless the task explicitly requires otherwise.
- Dry-run is the default for Shopify write behavior.
- Real Shopify writes require explicit confirmation and existing write guards.
- Billing, OAuth, webhooks and deployment changes require a plan and explicit approval.
