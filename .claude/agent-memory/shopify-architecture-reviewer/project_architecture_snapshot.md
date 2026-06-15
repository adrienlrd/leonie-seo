---
name: project-architecture-snapshot
description: Giulio Geo Shopify app layout, env var naming split between Remix and Python services, and a node_modules version-resolution quirk found during the 2026-06-15 audit
metadata:
  type: project
---

Snapshot from a full audit on 2026-06-15 (commit range ending at 5117b4a). Useful as a map for future reviews — re-verify specifics before relying on them, this decays fast.

## Two-service split (render.yaml)
- `leonie-seo-pilot-web` (Remix, `shopify-app/`): env vars `SHOPIFY_API_KEY` / `SHOPIFY_API_SECRET` (legacy Shopify CLI naming).
- `leonie-seo-pilot-api` (Python, `app/`): env vars `SHOPIFY_CLIENT_ID` / `SHOPIFY_CLIENT_SECRET`.
- `shopify.server.ts` reads `SHOPIFY_CLIENT_ID ?? SHOPIFY_API_KEY` and `SHOPIFY_CLIENT_SECRET ?? SHOPIFY_API_SECRET ?? ""` so it tolerates either naming — but `shopify-app/app/routes/webhooks.tsx` only checks `process.env.SHOPIFY_API_SECRET` directly (no fallback). In current render.yaml this happens to be set for the web service, so it works today, but it's a latent footgun if `SHOPIFY_API_SECRET` is ever dropped in favor of `SHOPIFY_CLIENT_SECRET` on that service.

## node_modules version resolution quirk (shopify-app/)
- Top-level `node_modules/@shopify/shopify-api` resolves to **10.0.0** (`LATEST_API_VERSION = April24` / 2024-04) — this is a stale/hoisted copy, likely pulled in by `shopify-app-session-storage-*` packages (`^9.7.2 || ^10.0.0` peer range).
- `@shopify/shopify-app-remix` resolves to **3.8.5** (not the `^3.3.3` declared in package.json — package-lock has moved ahead) and ships its OWN nested `node_modules/@shopify/shopify-app-remix/node_modules/@shopify/shopify-api@11.14.1`, where `LATEST_API_VERSION = July25` (2025-07) and `RELEASE_CANDIDATE_API_VERSION = October25`.
- Because `shopify-app-remix/dist/cjs/server/index.js` does `require('@shopify/shopify-api')`, Node resolves the NESTED 11.14.1 copy first. So `shopify.server.ts`'s `apiVersion: LATEST_API_VERSION` actually evaluates to **2025-07 at runtime**, not 2024-04 and not the 2025-01 used elsewhere (toml webhooks, theme extension, Python admin GraphQL calls).
- Net effect: a 3-way (not 2-way) version split — Remix Admin API client = 2025-07 (implicit/unpinned), webhooks.toml + extension + Python = 2025-01 (hardcoded). As of 2026-06, 2025-07 is likely near/past the edge of Shopify's ~4-quarter supported window and 2025-01 may already be unsupported — needs date-check against Shopify's release calendar at review time.

## Known/already-tracked open items (per docs/AI_HANDOFF.md)
- `render.yaml` scopes include `read_orders` on both services; `shopify.app.toml access_scopes` does NOT include `read_orders`. This drift is already flagged in `docs/app-store-submission-checklist.md` and multiple `docs/AI_HANDOFF.md` entries as pending alignment — not a new finding, just confirm still open.
- `write_themes` scope is intentionally retained (justified in `docs/shopify-write-themes-review-justification.md`) for the llms.txt/llms-full.txt theme template writer (`app/apply/shopify_theme_files.py`), gated by `LEONIE_THEME_WRITE_MODE`.

## Billing webhook gap
- `app/oauth/webhooks.py` has a working, tested `/app_subscriptions/update` handler (HMAC-verified, calls `update_subscription_status`), but `APP_SUBSCRIPTIONS_UPDATE` is NOT declared in `shopify.app.toml [[webhooks.subscriptions]]` nor in `shopify.server.ts` `webhooks: {...}`. No polling/reconciliation exists either (`get_active_subscriptions` is only called from `/billing/confirm`). So Shopify-side subscription status changes (merchant cancels in Shopify admin, auto-freeze for non-payment) never reach the DB — confirmed during 2026-06-15 audit, not yet fixed.

## Webhook relay architecture
- `shopify-app/app/routes/webhooks.tsx` hand-rolls HMAC verification (does not use `authenticate.webhook()`) and relays raw body to the Python backend at `/shopify/webhooks/{topic}`, which re-verifies HMAC again with `SHOPIFY_CLIENT_SECRET`. Webhooks are declared both in `shopify.app.toml` (app-managed/declarative) and in `shopify.server.ts` `webhooks: {...}` + `registerWebhooks({session})` in `afterAuth` (shop-specific API registration) — potential double-registration, confirm Shopify's current guidance on mixing TOML-declared and API-registered webhooks for apps using `unstable_newEmbeddedAuthStrategy`.

## Session lifecycle
- No `sessionStorage.deleteSession` / `deleteOfflineSession` call anywhere in `shopify-app/app/`. On `app/uninstalled`, only the Python-side token (`app/oauth/token_store.py` `delete_token`) is removed; the Remix session storage (Redis/Postgres/SQLite per `shopify.server.ts`) entry is orphaned.
