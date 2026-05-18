# AI_HANDOFF.md — Léonie SEO

## Current project state

- **Summary:** Léonie SEO est une app Shopify embedded + moteur Python/FastAPI/CLI pour audit SEO, recommandations supervisées, contenus, données structurées, jobs async, intégrations Shopify/Google/LLM et garde-fous dry-run.
- **Main stack:** Python 3.11+, FastAPI, Click, pytest, ruff, Remix, React, TypeScript, Shopify App Bridge, Shopify Polaris, npm.
- **Main working areas:** `app/`, `scripts/`, `shopify-app/`, `config/`, `docs/`, `tests/`.
- **Current roadmap:** Phase 10 est clôturée. Phase 11 est en cours avec une orientation GEO / AI Search Readiness / Revenue-Aware Shopify Intelligence. Les tâches 106 à 113 sont terminées.
- **Known limitations:** Phase 11 est avancée mais les workflows GEO restent majoritairement read-only. La mesure pilote garde des lacunes historiques sur IDs/durées de jobs, compteurs exacts, coût LLM et suivi fin de certains jobs. La Phase 11.5 existe dans `ROADMAP.md` mais doit encore être reflétée plus largement si elle devient officielle dans `PROGRESS.md`.

## Last completed task

- **Date:** 2026-05-18
- **Agent:** Codex
- **Goal:** Task 113 — FAQ & Answer Block Generator.
- **Summary:** Added fact-grounded GEO answer blocks and FAQ previews using confirmed Shopify snapshot facts only. Missing or vague sensitive facts become merchant review prompts. Added API, tests and a Remix page with JSON-LD preview.
- **Files created:**
  - `app/geo/__init__.py`
  - `app/geo/facts.py`
  - `app/geo/readiness.py`
  - `app/geo/prioritization.py`
  - `app/geo/weekly.py`
  - `app/geo/ledger.py`
  - `app/geo/risk_guard.py`
  - `app/geo/collections.py`
  - `app/geo/answers.py`
  - `app/api/geo.py`
  - `tests/test_geo/__init__.py`
  - `tests/test_geo/test_facts.py`
  - `tests/test_geo/test_readiness.py`
  - `tests/test_geo/test_prioritization.py`
  - `tests/test_geo/test_weekly.py`
  - `tests/test_geo/test_ledger.py`
  - `tests/test_geo/test_risk_guard.py`
  - `tests/test_geo/test_collections.py`
  - `tests/test_geo/test_answers.py`
  - `tests/test_api/test_geo.py`
  - `shopify-app/app/routes/app.geo-facts.tsx`
  - `shopify-app/app/routes/app.geo-readiness.tsx`
  - `shopify-app/app/routes/app.geo-priorities.tsx`
  - `shopify-app/app/routes/app.geo-weekly.tsx`
  - `shopify-app/app/routes/app.geo-ledger.tsx`
  - `shopify-app/app/routes/app.geo-risk-guard.tsx`
  - `shopify-app/app/routes/app.geo-collections.tsx`
  - `shopify-app/app/routes/app.geo-answer-blocks.tsx`
- **Files modified:**
  - `app/db.py`
  - `app/main.py`
  - `shopify-app/app/lib/i18n.ts`
  - `shopify-app/app/routes/app.content-hub.tsx`
  - `PROGRESS.md`
  - `ROADMAP.md`
  - `docs/AI_HANDOFF.md`
- **Decisions made:**
  - Facts Layer V1 and Readiness Score V1 are read-only and use only existing Shopify snapshot data.
  - Sensitive facts such as material, origin, certification, warranty, dimensions and compatibility are never invented; missing values become merchant verification prompts.
  - Existing `app.niche.ner` is reused for product entities instead of creating a duplicate extractor.
  - AI Search Readiness is explicitly an internal diagnostic score, not a ranking or AI citation guarantee.
  - Revenue estimates use GSC, CTR curve assumptions, conversion rate and AOV/price fallback; they are priority signals, not promises.
  - The endpoint does not call GA4 live in V1, to keep the workflow fast and available when GA4 is not connected.
  - Weekly actions are a read-only selection layer, not an automatic scheduler or Shopify write workflow.
  - GEO ledger uses a dedicated `geo_impact_events` table instead of overloading `seo_changes`, because the ledger tracks plans, previews and measurements as well as applied writes.
  - Risk Guard V1 is diagnostic-only; future write workflows should consult it before live Shopify mutations.
  - AI Search Collection Builder V1 is read-only: it returns previews and warnings but never creates Shopify collections.
  - Collection suggestions use catalog clustering and query-token matching first; embeddings are deferred to a later version to avoid adding dependencies and keep recommendations explainable.
  - Existing collection handles and thin candidates are flagged for merchant review.
  - FAQ/answer blocks only use confirmed facts with explicit sources; vague topic signals and missing sensitive facts are kept as review prompts.
  - Answer Block Generator V1 is dry-run and does not call an LLM or write to Shopify.
- **Validations run:**
  - `pytest tests/test_geo tests/test_api/test_geo.py tests/test_db_adapter.py` — 51/51 ✅
  - `ruff check app/geo app/api/geo.py tests/test_geo tests/test_api/test_geo.py` ✅
  - `ruff check .` ✅
  - `cd shopify-app && npm run typecheck` ✅
  - `cd shopify-app && npm run build` ✅
  - `ruff check .` ✅
  - `cd shopify-app && npm run typecheck` ✅
  - `cd shopify-app && npm run build` ✅
- **Validations skipped:** Full `pytest` was not run; the change was covered by targeted backend/API tests plus global ruff and TypeScript build validation.
- **Next recommended step:** Task 114 — llms.txt & AI Crawlability Advisor: preview AI crawl guidance and recommend pages to include/exclude without promising ranking impact.

## Open decisions

| Decision | Status | Context | Recommended next step |
|---|---|---|---|
| Phase 11.5 placement | Open | `ROADMAP.md` now includes a Phase 11.5 for impact validation and retention loop, while `PROGRESS.md` still summarizes Phase 11 and Phase 12 only. | Decide whether to make Phase 11.5 official in `PROGRESS.md` before task 116 planning. |
| Add a shared Claude Bash validation hook | Open | `.claude/settings.json` is intentionally minimal because no safe shared script was confirmed. | Add a repo-owned script such as `scripts/validate-command.sh` only if it is non-destructive and works for all contributors. |
| Exact validation matrix for every task | Open | Full validation exists but can be long. | Define task-specific validation groups in `docs/COMMANDS.md` over time. |

## Known risks

| Risk | Impact | Mitigation |
|---|---|---|
| Shopify writes during pilot or production work | Can mutate merchant data. | Keep dry-run default, require explicit confirmation and respect `LEONIE_PILOT_SAFE_MODE`. |
| GEO content hallucination | Can publish false product claims. | Use confirmed facts only, separate merchant suggestions from confirmed facts, and keep review mandatory before any future write. |
| OAuth, billing, webhooks or scopes changed casually | Can break install, billing, compliance or App Store readiness. | Require a plan and targeted validation before changes. |
| Long roadmap history hides current state | Agents may work on stale tasks. | Read `PROGRESS.md`, `ROADMAP.md` and this file before meaningful work. |

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
