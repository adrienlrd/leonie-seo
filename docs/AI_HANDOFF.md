# AI_HANDOFF.md — Léonie SEO

## Current project state

- **Summary:** Léonie SEO est un outil d'audit et d'optimisation SEO pour boutiques Shopify. Le dépôt combine un backend Python/FastAPI, un moteur CLI Click, des scripts SEO, des jobs asynchrones, des intégrations Shopify/Google/LLM, et une app Shopify embedded Remix dans `shopify-app/`.
- **Main stack:** Python 3.11+, FastAPI, Click, pytest, ruff, Remix, React, TypeScript, Shopify App Bridge, Shopify Polaris, npm.
- **Main working areas:** `app/`, `scripts/`, `shopify-app/`, `config/`, `docs/`, `tests/`.
- **Known limitations:** Phase 10 encore en cours. Prochaine tâche documentée dans `PROGRESS.md` : tâche 86 — ajouter un import crawl technique dans l'app. Les mesures pilote ont encore des lacunes sur IDs/durées de jobs, compteurs exacts, coût LLM et récupération des jobs `running`.

## Last completed task

- **Date:** 2026-05-16
- **Agent:** Claude Code (claude-sonnet-4-6)
- **Goal:** Task 86 — Add a technical crawl import in the embedded Shopify app.
- **Summary:** Added `app/crawl/` Python module with CSV parsing and issue detection, two FastAPI endpoints (`GET /crawl/status`, `POST /crawl/upload`), a multipart upload helper in `api.server.ts`, and a full Crawl technique card in the Onboarding page. Added `python-multipart` to `pyproject.toml`.
- **Files created:**
  - `app/crawl/__init__.py`
  - `app/crawl/client.py`
  - `app/api/crawl.py`
  - `tests/test_crawl/__init__.py`
  - `tests/test_crawl/test_client.py`
  - `tests/test_api/test_crawl.py`
- **Files modified:**
  - `app/main.py` (router import + include)
  - `shopify-app/app/lib/api.server.ts` (callBackendMultipartForShop)
  - `shopify-app/app/routes/app.onboarding.tsx` (CrawlStatus types, loader, action, UI card)
  - `pyproject.toml` (python-multipart dependency)
  - `PROGRESS.md`, `ROADMAP.md`
- **Decisions made:**
  - Crawl upload is synchronous (no background job) — CSV parsing is fast enough for direct response.
  - `python-multipart` added as a standard FastAPI peer dependency for file uploads.
- **Tests run:** `ruff check .` ✅, `pytest` 1101/1101 ✅, `npm run typecheck` ✅, `npm run build` ✅.
- **Next recommended step:** Task 87 — Étendre l'audit UI (afficher toutes les issues `detect_issues.py` dans l'app avec filtres, gravité, ressource touchée).

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
