# AI_HANDOFF.md — Léonie SEO

## Current project state

- **Summary:** Léonie SEO est un outil d'audit et d'optimisation SEO pour boutiques Shopify. Le dépôt combine un backend Python/FastAPI, un moteur CLI Click, des scripts SEO, des jobs asynchrones, des intégrations Shopify/Google/LLM, et une app Shopify embedded Remix dans `shopify-app/`.
- **Main stack:** Python 3.11+, FastAPI, Click, pytest, ruff, Remix, React, TypeScript, Shopify App Bridge, Shopify Polaris, npm.
- **Main working areas:** `app/`, `scripts/`, `shopify-app/`, `config/`, `docs/`, `tests/`.
- **Known limitations:** Phase 10 encore en cours. Prochaine tâche documentée dans `PROGRESS.md` : tâche 86 — ajouter un import crawl technique dans l'app. Les mesures pilote ont encore des lacunes sur IDs/durées de jobs, compteurs exacts, coût LLM et récupération des jobs `running`.

## Last completed task

- **Date:** 2026-05-16
- **Agent:** ChatGPT / GitHub connector
- **Goal:** Make the repository AI-ready for Codex and Claude Code.
- **Summary:** Added Claude Code handoff through `CLAUDE.md`, created AI handoff, architecture and command docs, sanitized shared Claude settings, added Claude subagents, and completed `.gitignore` AI/local safety rules.
- **Files created:**
  - `docs/AI_HANDOFF.md`
  - `docs/ARCHITECTURE.md`
  - `docs/COMMANDS.md`
  - `.claude/agents/code-reviewer.md`
  - `.claude/agents/test-triage.md`
  - `.claude/agents/shopify-architecture-reviewer.md`
- **Files modified:**
  - `CLAUDE.md`
  - `.claude/settings.json`
  - `.gitignore`
- **Decisions made:**
  - Keep `AGENTS.md` as the shared source of truth.
  - Make `CLAUDE.md` import `@AGENTS.md` instead of duplicating rules.
  - Replace local absolute-path Claude hooks with safe shared plan-mode settings.
  - Do not add hooks because no safe shared validation script was confirmed.
- **Tests run:** Not run from the connector environment.
- **Tests skipped:**
  - `ruff check .` — skipped because the GitHub connector cannot execute repo commands.
  - `pytest` — skipped because the GitHub connector cannot execute repo commands.
  - `cd shopify-app && npm run typecheck` — skipped because the GitHub connector cannot execute repo commands.
  - `cd shopify-app && npm run build` — skipped because the GitHub connector cannot execute repo commands.
- **Issues found:**
  - `CLAUDE.md` was a legacy archive and did not import `@AGENTS.md`.
  - `.claude/settings.json` contained a local absolute path and project-personal hook.
  - `docs/AI_HANDOFF.md`, `docs/ARCHITECTURE.md`, and `docs/COMMANDS.md` were missing.
- **Next recommended step:** Run local validation commands and continue with roadmap task 86.

## Open decisions

| Decision | Status | Context | Recommended next step |
|---|---|---|---|
| Add a shared Claude Bash validation hook | Open | `.claude/settings.json` is intentionally minimal because no safe shared script was confirmed. | Add a repo-owned script such as `scripts/validate-command.sh` only if it is non-destructive and works for all contributors. |
| Keep `PROGRESS.md` and `docs/AI_HANDOFF.md` both active | Open | `PROGRESS.md` is roadmap history; `AI_HANDOFF.md` is compact agent handoff. | Keep `PROGRESS.md` for roadmap state and `AI_HANDOFF.md` for current agent state. |
| Exact validation matrix for every task | Open | Full validation exists but can be long. | Define task-specific validation groups in `docs/COMMANDS.md` over time. |

## Known risks

| Risk | Impact | Mitigation |
|---|---|---|
| Shopify writes during pilot or production work | Can mutate merchant data. | Keep dry-run default, require explicit confirmation and respect `LEONIE_PILOT_SAFE_MODE`. |
| OAuth, billing, webhooks or scopes changed casually | Can break install, billing, compliance or App Store readiness. | Require plan mode and targeted validation before changes. |
| Local Claude settings committed | Can break other machines or expose personal paths. | Keep `.claude/settings.local.json` ignored and shared settings minimal. |
| AI agents duplicate or contradict instructions | Lower reliability and accidental architecture drift. | Use `AGENTS.md` as source of truth and import it from `CLAUDE.md`. |
| Long roadmap history hides current state | Agents may work on stale tasks. | Read `PROGRESS.md` and this file before meaningful work. |

## Useful commands

| Purpose | Command |
|---|---|
| Install Python package | `pip install -e .` |
| Install Python dev dependencies | `pip install -e .[dev]` |
| CLI help | `leonie-seo --help` |
| Backend dev server | `uvicorn app.main:app --host 0.0.0.0 --port 8000` |
| Python lint | `ruff check .` |
| Python tests | `pytest` |
| Shopify app install | `cd shopify-app && npm install` |
| Shopify app dev | `cd shopify-app && npm run dev` |
| Shopify Remix dev | `cd shopify-app && npm run web` |
| Shopify typecheck | `cd shopify-app && npm run typecheck` |
| Shopify build | `cd shopify-app && npm run build` |
| Docker build | `docker build -t leonie-seo .` |
