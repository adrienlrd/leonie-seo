# Codex Task: Align Giulio Geo (leonie-seo) with the target merchant journey

## 0. How to work

- Read `AGENTS.md` fully before any edit and follow it strictly (it is the contract).
- Read `docs/AI_HANDOFF.md` and `PROGRESS.md` for current state.
- Work task by task, in the order below. One focused commit per task. Small diffs.
- After each task run the relevant validations: `ruff check .`, `pytest` for Python;
  `cd shopify-app && npm run typecheck && npm run build` for frontend. Do not move on if they fail.
- All UI copy must be added to `shopify-app/app/lib/i18n.ts` in BOTH French and English (`t(locale, "key")`).
- All frontend→backend calls go through `callBackendForShop()` in `shopify-app/app/lib/api.server.ts`. Never call the Python backend directly from a component.
- Dry-run stays the default for every Shopify write. Never weaken `confirm_live_write` / `confirm=true` guards.
- Do NOT touch Shopify OAuth, billing, webhooks registration, or API scopes.
- Update `docs/AI_HANDOFF.md` and `PROGRESS.md` after each completed task.

## 1. Product vision (the target merchant journey)

1. First login: the ONLY action asked of the merchant is connecting Google (GSC + GA4).
2. First analysis: the app shows what it understood about the business — niche, brand,
   personas, competitors, and a labeled product list. The merchant adjusts/validates to improve precision.
3. Second, deep analysis: using the validated profile + GSC + GA4 + DataForSEO + internal
   scoring, generate per-product proposals: meta title, meta description, FAQ, blog ideas,
   JSON-LD, llms.txt content, internal linking.
4. The merchant lands on a Dashboard with only the essentials. Navigation is exactly:
   Dashboard / Produits / Blog / Mesure / Réglages.
5. On Dashboard, Produits and Blog he can apply each proposal manually, OR enable auto-publish.
6. Every 14 or 28 days (merchant choice), the app automatically: refreshes the Shopify snapshot,
   re-imports GSC/GA4, re-runs the market analysis WITH full knowledge of past applied changes
   and their measured impact, and produces new concrete proposals — either as approvals
   (semi-auto) or auto-applied/published (auto mode). Everything is interconnected: measurement
   feeds the next analysis.

## 2. Current state (verified in code — trust this over older docs)

Backend (FastAPI, routers mounted in `app/main.py`):

- Two-phase analysis exists and works: `app/api/business_profile.py` (analyze → merchant saves
  validated profile) then `app/api/market_analysis.py` (`POST /identify`, `POST /jobs`,
  `GET /jobs/{id}`, `GET /latest`), engine in `app/market_analysis/engine.py` (2 LLM passes,
  consumes snapshot + GSC + GA4 + DataForSEO via `app/market_analysis/providers/dataforseo_provider.py`).
- Measurement backend is rich but headless: `app/api/geo.py` exposes `/geo/progress-curve`,
  `/geo/impact-report`, `/geo/retention-milestones`, `/geo/validation-timeline`,
  `/geo/confidence-scores`, `/geo/control-groups`, ledger `geo_impact_events`
  (planned→applied→measured), snapshots `geo_optimization_snapshots`.
- Automation: `app/agent_schedule/scheduler.py` ticks and only calls
  `run_learning_cycle` (`app/learning/scheduler.py`) = create observations from mature events
  + update weights + `run_continuous_improvement_agent` (re-prioritizes EXISTING proposals,
  auto-applies only meta/alt). It NEVER re-runs market analysis, never re-imports GSC/GA4,
  and skips shops with `no_market_analysis`.
- Writes to Shopify: `/market-analysis/proposals/{id}/apply-to-shopify` (meta/description/alts),
  `/blog/publish`, `/proposals/{id}/schema-facts/sync` (FAQ metafield), `/llms-txt/publish` (theme files).

Frontend (Remix, `shopify-app/app/routes/`):

- Nav (`app.tsx`): Dashboard, Analyse marché (`app.market-analysis.tsx` = de-facto Products page),
  Blog (`app.blog.tsx`), GEO llms.txt (`app.geo-llms-txt.tsx`), Amélioration continue
  (`app.continuous-improvement.tsx`), Compte (`app.account.tsx` hub → billing/settings/jobs/privacy).
- `app.onboarding.tsx` is OUTDATED: it calls the legacy `/niche/understand` endpoint and links
  to `/app/niche-understanding` and `/app/priorities` which DO NOT EXIST. The real two-phase
  flow lives inside `app._index.tsx` (2,981 lines: analysis control panel, profile editing,
  competitors, products list — overloaded).
- Dead links (404 in app): `/app/niche-understanding` (`app._index.tsx:940,1241`,
  `app.onboarding.tsx:402`), `/app/safe-apply` (`app._index.tsx:982`), `/app/impact`
  (`app._index.tsx:1217`), `/app/priorities` (`app.onboarding.tsx:419`), `/app/ga4`
  (`app.account.tsx:137`, `app.market-analysis.tsx:953`).
- There is NO measurement page despite the full `/geo/*` backend.

## 3. Tasks (in this order)

### Task 1 — Rebuild onboarding around the real two-phase flow

Goal: first-run merchant does Google connect → first analysis → adjust → deep analysis, all in one wizard.

- Rewrite `app.onboarding.tsx` as a 4-step wizard reusing the EXISTING dashboard intents/endpoints
  (do not duplicate logic — extract the analysis control panel from `app._index.tsx` into shared
  components under `shopify-app/app/components/`, e.g. `BusinessProfilePanel`, `ProductIdentificationPanel`):
  1. Connect Google (keep current GSC/GA4 popup flow + `gsc/import`, `ga4` status checks).
  2. "Première analyse" → `POST /api/shops/{shop}/business-profile/analyze`, poll
     `GET /business-profile/job/{id}`, render the profile (niche, personas, brand voice,
     competitors) in editable form.
  3. Merchant adjusts & validates → `POST /business-profile`, then
     `POST /market-analysis/identify`, show product labels for correction,
     save via `POST /market-analysis/identifications`.
  4. "Analyse approfondie" → `POST /market-analysis/jobs`, poll `GET /market-analysis/jobs/{id}`
     with progress, then redirect to `/app` (dashboard).
- Remove every call to the legacy `/niche/understand` flow from onboarding.
- Auto-redirect: in `app._index.tsx` loader, if no validated business profile exists
  (`GET /business-profile/latest`), redirect to `/app/onboarding`.

### Task 2 — Fix all dead links and slim down the dashboard

- Replace `/app/niche-understanding` links with the profile section (onboarding step 2/3 or a
  dashboard anchor). Replace `/app/safe-apply?highlight=...` with
  `/app/products?product=...` (see Task 3). Replace `/app/impact` with `/app/measure`
  (Task 4). Replace `/app/priorities` with `/app` zone 2. Replace `/app/ga4` with the Google
  connect step in onboarding (`/app/onboarding`).
- Move the full analysis control panel + profile editing out of `app._index.tsx` (now shared
  components used by onboarding). Dashboard keeps: score & niche summary, top-3 priority
  actions, performance trend (link to /app/measure), pending setup, alerts, products overview,
  plus a single "Relancer l'analyse" button that reuses the shared panel in a modal or links
  to onboarding step 4.
- Target: `app._index.tsx` substantially smaller; no behavioral change to endpoints.

### Task 3 — Rename "Analyse marché" to "Produits" and restructure navigation

- Add route `app.products.tsx` that re-exports/renders the current `app.market-analysis.tsx`
  content (keep the old route as a redirect to preserve deep links).
- Update nav in `app.tsx` to exactly: Dashboard, Produits (`/app/products`), Blog (`/app/blog`),
  Mesure (`/app/measure`), Réglages (`/app/settings-hub` or reuse `/app/account`).
- Fold `app.geo-llms-txt.tsx` and `app.continuous-improvement.tsx` out of primary nav:
  llms.txt becomes a card/section inside Réglages ("Visibilité IA"), continuous-improvement
  content splits between Mesure (effectiveness, agent events) and Réglages (automation settings).
  Keep old routes as redirects.
- i18n: add FR+EN keys for all new labels.

### Task 4 — Create the "Mesure" page (`app.measure.tsx`)

New route consuming the existing `/geo/*` endpoints (all already implemented):

- Header KPIs: GSC clicks/impressions trend + GA4 sessions (use `/geo/progress-curve`).
- Timeline chart: traffic curve annotated with applied changes (events from `/geo/ledger`
  overlaid on `/geo/progress-curve` series).
- Milestones: J+14 / J+28 / J+60 from `/geo/retention-milestones` with per-event verdicts
  from `/geo/impact-report` and `/geo/confidence-scores`.
- Control comparison: `/geo/control-groups` (modified vs unmodified products).
- Next best actions: `/geo/next-best-actions`.
- Follow the async/polling pattern of `app.market-analysis.tsx` (useFetcher poll every 5 s)
  only where a job is involved; plain loaders otherwise. Polaris components, FR+EN i18n.

### Task 5 — Auto-create impact events on every apply

Goal: measurement must populate itself, with no manual ledger steps.

- In the backend apply paths — `apply-to-shopify` (market_analysis), `blog/publish`,
  `schema-facts/sync`, learning approvals apply — automatically create a
  `geo_optimization_snapshot` (before-state) and a `geo_impact_events` row
  (status `applied`, with field, old/new values, metrics_before from latest GSC/GA4)
  when a LIVE write succeeds. Reuse the existing creation logic behind
  `POST /geo/ledger/events` and `/geo/optimization-snapshots` (refactor into a service
  function in `app/geo/`, call it from the apply paths). Idempotent per (resource, field, applied_at).
- Add pytest coverage: applying a proposal live creates exactly one event + snapshot;
  dry-run creates nothing.

### Task 6 — Close the loop: feed past changes & measured impact into the analysis

- In `app/market_analysis/engine.py`, build an "optimization history context" per product:
  applied events (field, old→new, date) + measured outcomes (J+14/28 verdicts, confidence)
  from `geo_impact_events` / `learning_observations`, plus shop-level summary
  (what worked / what regressed from learning weights).
- Inject this context into Pass 1 and Pass 2 prompts with explicit instructions:
  do not re-propose unchanged values that measured positive; revise or revert what regressed;
  reference past changes when proposing increments.
- Keep prompt size bounded (cap history to last N events per product, summarize older ones).
- Add pytest: engine prompt assembly includes history when events exist, omits section when none.

### Task 7 — Real 14/28-day automatic re-analysis cycle

Goal: scheduled pipeline = refresh data → re-analyze → propose/apply.

- Extend `merchant_learning_settings` / `agent_schedules` (migration-safe, both SQLite and
  Postgres via `app/db_adapter.py`) with: `reanalysis_frequency_days` (14 or 28, default 28)
  and `auto_publish_scopes` (subset of: meta, alt_text, faq_metafield, blog).
- In `app/agent_schedule/scheduler.py`, when a shop's re-analysis is due (last completed
  market analysis older than frequency): enqueue, in order, `seo_audit` (snapshot refresh)
  and `gsc_import` jobs, then run the market analysis job
  (reuse `app/market_analysis/jobs.py` background runner) with the Task 6 history context,
  then run the learning cycle on fresh results.
- Semi-auto mode: new/changed proposals become pending approvals (existing
  `learning` approvals system) surfaced on Dashboard + Produits.
- Auto mode: auto-apply ONLY fields listed in `auto_publish_scopes`, through the existing
  guarded apply paths (which now create impact events via Task 5). Blog auto-publish only
  if explicitly in scopes; default scopes remain meta + alt_text.
- Respect existing budget gating (`check_budget`) and the 20 h cooldown; the heavy pipeline
  must run at most once per frequency window per shop.
- Add pytest: due-shop detection by frequency; pipeline ordering; auto-apply respects scopes;
  budget exhaustion degrades gracefully (analysis skipped, run logged).

### Task 8 — Consolidated Réglages page

- Build the Réglages destination (extend `app.settings.tsx` or the account hub) with sections:
  1. Automatisation: mode (manuel / semi-auto / auto), `reanalysis_frequency_days` (14/28),
     `auto_publish_scopes` checkboxes, schedule time/timezone (reuse `/agent-schedule/*`
     and `/learning/settings` endpoints, extend them for the new fields).
  2. Connexions: Google GSC/GA4 status + connect/disconnect (reuse onboarding components).
  3. Visibilité IA: llms.txt generate/publish + crawler prefs (moved from `app.geo-llms-txt.tsx`).
  4. Existing: plan/billing link, budget LLM, backend health, concurrents manuels.
- FR+EN i18n for everything.

### Task 9 — Persist analysis artifacts in the database

Goal: survive Render ephemeral disk; the long-term memory must not vanish.

- Today `market_analysis_latest.json`, `business_profile_latest.json`, `identifications.json`,
  `merchant_facts.json` live only in `data/raw/{shop}/`. Add DB-backed persistence
  (JSON columns/tables via `app/db_adapter.py`, works on SQLite AND Postgres) with
  read-through: prefer DB, fall back to file, dual-write on save. Reuse existing tables
  where they already exist (`business_profiles` is already in DB — make it the source of truth).
- Do not change endpoint contracts. Add pytest for save/load round-trip on both code paths.

## 4. Acceptance criteria (whole effort)

- A fresh shop with no data is redirected to onboarding; the merchant can go from zero to a
  completed deep analysis by only: connecting Google, clicking analyze, adjusting the profile
  and product labels, clicking the deep analysis. No dead link anywhere in the app.
- Nav shows exactly: Dashboard, Produits, Blog, Mesure, Réglages (FR locale; English equivalents in EN).
- Every live apply (manual or auto) creates a measurable impact event visible on Mesure.
- A new market analysis mentions/accounts for previously applied changes (visible in proposals context).
- With auto mode + frequency 14: scheduler triggers the full refresh→analyze→apply pipeline
  for due shops, only safe configured scopes get written, all writes logged.
- `pytest`, `ruff check .`, `npm run typecheck`, `npm run build` all pass.
- `docs/AI_HANDOFF.md` and `PROGRESS.md` updated per task.

## 5. Out of scope (do NOT do)

- No changes to Shopify OAuth, billing plans, webhook registration, or API scopes.
- No new external dependencies without documented justification.
- No repo-wide reformatting or file reorganization beyond the routes/components listed.
- No removal of existing CLI capabilities in `scripts/`.
