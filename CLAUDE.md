# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

@AGENTS.md

## Claude Code specific instructions

Use `permissionMode: plan` or switch to plan mode before:
- Large refactors or architecture changes
- Database schema or migration changes
- Shopify OAuth, billing, webhook, or API scope changes
- Deployment or production config changes

Prefer read-only exploration before editing.

Use project subagents from `.claude/agents/` when relevant:
- `code-reviewer`
- `test-triage`
- `shopify-architecture-reviewer`

Do not duplicate rules from `AGENTS.md` here.
If a rule conflicts with `AGENTS.md`, `AGENTS.md` wins unless the user explicitly says otherwise.

Update `docs/AI_HANDOFF.md` after every meaningful change.

## Commands

```bash
# Python backend
pip install -e .[dev]
uvicorn app.main:app --host 0.0.0.0 --port 8000
ruff check . && ruff format .
pytest                        # full suite
pytest tests/path/test_foo.py # single file
pytest -k "test_name"         # single test

# Shopify app (always from shopify-app/)
cd shopify-app
npm install
npm run dev          # local dev with tunnel
npm run typecheck    # must pass before commit
npm run build        # must pass before commit
```

## Architecture

Two independent processes that communicate over HTTP:

**Python backend** (`app/`, `scripts/`)
- FastAPI app mounted at `app/main.py` — routers registered there.
- Each domain has its own router in `app/api/` (e.g. `market_analysis.py`, `gsc.py`, `ga4.py`).
- Background jobs: FastAPI `BackgroundTasks` + an in-memory dict (`_jobs`) in each `*/jobs.py`. Results are persisted to `data/raw/{shop}/` as JSON. On Render Free the disk is ephemeral — results disappear on sleep/restart.
- Shop context resolved via `X-Leonie-Shop` + `X-Internal-Secret` headers (`app/api/deps.py`).
- Shopify snapshot (products, collections, shop info) stored in `data/raw/{shop}/snapshot_*.json` and loaded by `_load_snapshot()` in `app/api/audit.py`.

**Remix frontend** (`shopify-app/`)
- Every page is a route file `shopify-app/app/routes/app.*.tsx`.
- All backend calls go through `callBackendForShop()` in `shopify-app/app/lib/api.server.ts`, which injects `X-Leonie-Shop` and `X-Internal-Secret`. Never call the Python backend directly from a component.
- i18n lives entirely in `shopify-app/app/lib/i18n.ts` — add FR + EN keys together, use `t(locale, "key")`.
- Async job pattern: loader starts a job (POST `/jobs`), page polls (POST with `intent=poll`) every 5 s via `useFetcher`, results appear progressively. See `app.market-analysis.tsx` as the reference implementation.

**Data flow for a typical analysis page:**
1. Remix loader → `callBackendForShop` → FastAPI endpoint
2. FastAPI loads snapshot + optional GSC/GA4/Trends data → LLM prompt → structured JSON
3. Result saved to `data/raw/{shop}/*.json`
4. Loader returns data to Remix component → rendered with Polaris components
